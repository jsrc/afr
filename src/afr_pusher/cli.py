from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

import requests

from .config import Settings
from .fetchers.afr import AFRFetcher
from .pipeline import NewsPipeline
from .senders.desktop_script import DesktopScriptSender
from .senders.router import SenderRouter
from .senders.wecom import WeComWebhookSender
from .store import SQLiteStore
from .translators import build_translator


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def _build_router(settings: Settings, session: requests.Session) -> SenderRouter:
    primary = None
    fallback = None

    if settings.wecom_webhook_url:
        primary = WeComWebhookSender(
            webhook_url=settings.wecom_webhook_url,
            timeout_sec=settings.request_timeout_sec,
            session=session,
        )

    if settings.desktop_send_script:
        fallback = DesktopScriptSender(
            script_path=settings.desktop_send_script,
            timeout_sec=settings.desktop_send_timeout_sec,
        )

    return SenderRouter(primary=primary, fallback=fallback, dry_run=settings.dry_run)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AFR translator and WeChat delivery pipeline")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--loop", action="store_true", help="Run forever with interval")
    parser.add_argument("--interval-sec", type=int, default=None, help="Loop interval in seconds")
    parser.add_argument("--max-articles", type=int, default=None, help="Override max articles per run")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline without sending messages")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    _load_dotenv(Path(args.env_file))

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("afr_pusher")

    settings = Settings.from_env()
    if args.dry_run:
        settings.dry_run = True
    if args.max_articles is not None:
        settings.afr_max_articles = args.max_articles
    if args.interval_sec is not None:
        settings.run_interval_sec = args.interval_sec

    settings.ensure_dirs()

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
    router = _build_router(settings, session=session)

    if not settings.dry_run and not (router.primary or router.fallback):
        raise SystemExit(
            "No sender configured. Set WECOM_WEBHOOK_URL or DESKTOP_SEND_SCRIPT, or use --dry-run."
        )

    pipeline = NewsPipeline(
        settings=settings,
        fetcher=fetcher,
        translator=translator,
        sender_router=router,
        store=store,
        logger=logger,
    )

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
