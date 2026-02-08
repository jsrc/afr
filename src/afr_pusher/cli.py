from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .config import Settings
from .fetchers.afr import AFRFetcher
from .pipeline import NewsPipeline
from .senders.desktop_script import DesktopScriptSender
from .senders.router import SenderRouter
from .senders.telegram import TelegramBotSender
from .senders.wecom import WeComWebhookSender
from .store import SQLiteStore
from .translators import build_translator

DEFAULT_LAUNCHD_LABEL = "com.afr.pusher"
SEND_CHANNEL_CHOICES = ("telegram", "wecom", "desktop")


def _build_router(
    settings: Settings,
    session: requests.Session,
    send_channel: str | None = None,
) -> SenderRouter:
    selected_channel = (send_channel or "").strip().lower() or None
    if selected_channel and selected_channel not in SEND_CHANNEL_CHOICES:
        choices = ", ".join(SEND_CHANNEL_CHOICES)
        raise SystemExit(f"Unsupported --send-channel '{selected_channel}'. Available: {choices}.")

    telegram_sender = None
    telegram_any = bool(settings.telegram_bot_token or settings.telegram_chat_id)
    if settings.telegram_bot_token and settings.telegram_chat_id:
        telegram_sender = TelegramBotSender(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            timeout_sec=settings.request_timeout_sec,
            api_base=settings.telegram_api_base,
            session=session,
        )
    elif telegram_any and selected_channel in (None, "telegram"):
        raise SystemExit("Telegram sender requires both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    wecom_sender = None
    if settings.wecom_webhook_url:
        wecom_sender = WeComWebhookSender(
            webhook_url=settings.wecom_webhook_url,
            timeout_sec=settings.request_timeout_sec,
            session=session,
        )

    desktop_sender = None
    if settings.desktop_send_script:
        desktop_sender = DesktopScriptSender(
            script_path=settings.desktop_send_script,
            timeout_sec=settings.desktop_send_timeout_sec,
        )

    if selected_channel == "telegram":
        if not telegram_sender:
            raise SystemExit("--send-channel telegram requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
        settings.wechat_target = settings.telegram_chat_id or settings.wechat_target
        return SenderRouter(primary=telegram_sender, fallback=None, dry_run=settings.dry_run)
    if selected_channel == "wecom":
        if not wecom_sender:
            raise SystemExit("--send-channel wecom requires WECOM_WEBHOOK_URL.")
        return SenderRouter(primary=wecom_sender, fallback=None, dry_run=settings.dry_run)
    if selected_channel == "desktop":
        if not desktop_sender:
            raise SystemExit("--send-channel desktop requires DESKTOP_SEND_SCRIPT.")
        return SenderRouter(primary=desktop_sender, fallback=None, dry_run=settings.dry_run)

    primary = None
    fallback = None
    if telegram_sender:
        primary = telegram_sender
        settings.wechat_target = settings.telegram_chat_id or settings.wechat_target
    if wecom_sender:
        if primary is None:
            primary = wecom_sender
        elif fallback is None:
            fallback = wecom_sender
    if desktop_sender:
        if primary is None:
            primary = desktop_sender
        elif fallback is None:
            fallback = desktop_sender

    return SenderRouter(primary=primary, fallback=fallback, dry_run=settings.dry_run)


def _parse_daily_at(value: str) -> tuple[int, int]:
    text = value.strip()
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text)
    if not match:
        raise argparse.ArgumentTypeError("daily time must be HH:MM (24-hour), e.g. 16:30")
    return int(match.group(1)), int(match.group(2))


def _next_daily_run(now: datetime, hour: int, minute: int) -> datetime:
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _build_launchd_plist(
    *,
    label: str,
    python_executable: str,
    workdir: Path,
    config_file: Path,
    env_file: Path,
    hour: int,
    minute: int,
    max_articles: int,
    log_level: str,
    send_channel: str | None = None,
) -> str:
    logs_dir = workdir / "logs"
    stdout_log = logs_dir / "launchd.out.log"
    stderr_log = logs_dir / "launchd.err.log"
    pythonpath = workdir / "src"

    args = [
        python_executable,
        "-m",
        "afr_pusher",
        "--config-file",
        str(config_file),
        "--env-file",
        str(env_file),
        "--max-articles",
        str(max_articles),
        "--log-level",
        log_level,
    ]
    if send_channel:
        args.extend(["--send-channel", send_channel])
    program_args_xml = "\n".join(f"    <string>{arg}</string>" for arg in args)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{program_args_xml}
  </array>
  <key>WorkingDirectory</key>
  <string>{workdir}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>{pythonpath}</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>{hour}</integer>
    <key>Minute</key>
    <integer>{minute}</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>{stdout_log}</string>
  <key>StandardErrorPath</key>
  <string>{stderr_log}</string>
</dict>
</plist>
"""


def _launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def _install_launchd_job(
    *,
    label: str,
    config_file: Path,
    env_file: Path,
    hour: int,
    minute: int,
    max_articles: int,
    log_level: str,
    send_channel: str | None = None,
) -> Path:
    workdir = Path.cwd().resolve()
    logs_dir = workdir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist_path = agents_dir / f"{label}.plist"

    plist_content = _build_launchd_plist(
        label=label,
        python_executable=sys.executable,
        workdir=workdir,
        config_file=config_file.resolve(),
        env_file=env_file.resolve(),
        hour=hour,
        minute=minute,
        max_articles=max_articles,
        log_level=log_level,
        send_channel=send_channel,
    )
    plist_path.write_text(plist_content, encoding="utf-8")

    domain = _launchd_domain()
    subprocess.run(
        ["launchctl", "bootout", domain, str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], check=True)
    subprocess.run(["launchctl", "enable", f"{domain}/{label}"], check=False)
    return plist_path


def _uninstall_launchd_job(*, label: str) -> Path:
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    if plist_path.exists():
        domain = _launchd_domain()
        subprocess.run(
            ["launchctl", "bootout", domain, str(plist_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        plist_path.unlink()
    return plist_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AFR translator and WeChat delivery pipeline")
    parser.add_argument("--config-file", default="config.ini", help="Path to config.ini file")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--loop", action="store_true", help="Run forever with interval")
    parser.add_argument("--interval-sec", type=int, default=None, help="Loop interval in seconds")
    parser.add_argument(
        "--daily-at",
        type=_parse_daily_at,
        default=None,
        metavar="HH:MM",
        help="Run once every day at local time HH:MM, e.g. 16:30",
    )
    parser.add_argument("--max-articles", type=int, default=None, help="Override max articles per run")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline without sending messages")
    parser.add_argument(
        "--send-channel",
        choices=SEND_CHANNEL_CHOICES,
        default=None,
        help="Explicitly select a sender channel: telegram, wecom, or desktop",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument(
        "--install-launchd",
        action="store_true",
        help="Install macOS launchd job using --daily-at",
    )
    parser.add_argument(
        "--uninstall-launchd",
        action="store_true",
        help="Uninstall macOS launchd job",
    )
    parser.add_argument(
        "--launchd-label",
        default=DEFAULT_LAUNCHD_LABEL,
        help=f"launchd label (default: {DEFAULT_LAUNCHD_LABEL})",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("afr_pusher")

    settings = Settings.from_files(
        config_file=Path(args.config_file),
        env_file=Path(args.env_file),
    )
    if args.dry_run:
        settings.dry_run = True
    if args.max_articles is not None:
        settings.afr_max_articles = args.max_articles
    if args.interval_sec is not None:
        settings.run_interval_sec = args.interval_sec

    settings.ensure_dirs()

    if args.install_launchd:
        if args.daily_at is None:
            raise SystemExit("--install-launchd requires --daily-at HH:MM")
        hour, minute = args.daily_at
        plist_path = _install_launchd_job(
            label=args.launchd_label,
            config_file=Path(args.config_file),
            env_file=Path(args.env_file),
            hour=hour,
            minute=minute,
            max_articles=settings.afr_max_articles,
            log_level=args.log_level,
            send_channel=args.send_channel,
        )
        logger.info(
            "launchd installed: label=%s plist=%s schedule=%02d:%02d",
            args.launchd_label,
            plist_path,
            hour,
            minute,
        )
        return

    if args.uninstall_launchd:
        plist_path = _uninstall_launchd_job(label=args.launchd_label)
        logger.info("launchd uninstalled: label=%s plist=%s", args.launchd_label, plist_path)
        return

    session = requests.Session()
    session.headers.update({"User-Agent": settings.request_user_agent})

    store = SQLiteStore(settings.db_path)
    fetcher = AFRFetcher(
        homepage_url=settings.afr_homepage_url,
        timeout_sec=settings.request_timeout_sec,
        user_agent=settings.request_user_agent,
        article_path_prefix=settings.afr_article_path_prefix,
        session=session,
    )
    translator = build_translator(settings, session=session)
    router = _build_router(settings, session=session, send_channel=args.send_channel)

    if not settings.dry_run and not (router.primary or router.fallback):
        raise SystemExit(
            "No sender configured. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, "
            "WECOM_WEBHOOK_URL, or DESKTOP_SEND_SCRIPT, or use --dry-run."
        )

    pipeline = NewsPipeline(
        settings=settings,
        fetcher=fetcher,
        translator=translator,
        sender_router=router,
        store=store,
        logger=logger,
    )

    if args.daily_at is not None:
        daily_hour, daily_minute = args.daily_at
        if args.loop:
            logger.warning("--loop is ignored because --daily-at is set")
        if args.interval_sec is not None:
            logger.warning("--interval-sec is ignored because --daily-at is set")

        while True:
            now = datetime.now().astimezone()
            next_run = _next_daily_run(now, daily_hour, daily_minute)
            wait_seconds = max((next_run - now).total_seconds(), 0.0)
            logger.info(
                "daily schedule enabled: next run at %s (in %.0f seconds)",
                next_run.strftime("%Y-%m-%d %H:%M:%S %Z"),
                wait_seconds,
            )
            time.sleep(wait_seconds)

            stats = pipeline.run_once()
            logger.info(
                "run complete: fetched=%s sent=%s failed=%s skipped=%s",
                stats.fetched,
                stats.sent,
                stats.failed,
                stats.skipped,
            )
        return

    while True:
        stats = pipeline.run_once()
        logger.info(
            "run complete: fetched=%s sent=%s failed=%s skipped=%s",
            stats.fetched,
            stats.sent,
            stats.failed,
            stats.skipped,
        )

        if not args.loop:
            break

        time.sleep(settings.run_interval_sec)


if __name__ == "__main__":
    main()
