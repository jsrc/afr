from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WECHAT_SCRIPT = PROJECT_ROOT / "scripts" / "send.sh"


def _as_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass
class Settings:
    afr_homepage_url: str
    afr_article_path_prefix: Optional[str]
    afr_max_articles: int
    request_timeout_sec: float
    request_user_agent: str

    db_path: Path

    translator_provider: str
    source_lang: Optional[str]
    target_lang: str

    deepl_api_key: Optional[str]
    deepl_endpoint: str
    deepl_glossary_id: Optional[str]
    deepl_formality: Optional[str]

    wechat_target: str
    wecom_webhook_url: Optional[str]
    desktop_send_script: Optional[Path]
    desktop_send_timeout_sec: int
    preview_enabled: bool
    preview_output_dir: Path
    preview_max_titles: int

    run_interval_sec: int
    dry_run: bool

    @classmethod
    def from_env(cls) -> "Settings":
        desktop_script_raw = os.getenv("DESKTOP_SEND_SCRIPT", str(DEFAULT_WECHAT_SCRIPT)).strip()
        desktop_script = None
        if desktop_script_raw:
            candidate = Path(desktop_script_raw).expanduser()
            if not candidate.is_absolute():
                cwd_candidate = (Path.cwd() / candidate).resolve()
                project_candidate = (PROJECT_ROOT / candidate).resolve()
                candidate = cwd_candidate if cwd_candidate.exists() else project_candidate
            desktop_script = candidate

        return cls(
            afr_homepage_url=os.getenv("AFR_HOMEPAGE_URL", "https://www.afr.com").strip(),
            afr_article_path_prefix=(os.getenv("AFR_ARTICLE_PATH_PREFIX") or "").strip() or None,
            afr_max_articles=int(os.getenv("AFR_MAX_ARTICLES", "10")),
            request_timeout_sec=float(os.getenv("REQUEST_TIMEOUT_SEC", "12")),
            request_user_agent=os.getenv(
                "REQUEST_USER_AGENT",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36",
            ).strip(),
            db_path=Path(os.getenv("DB_PATH", "./data/afr_pusher.db")).expanduser(),
            translator_provider=os.getenv("TRANSLATOR_PROVIDER", "deepl").strip().lower(),
            source_lang=(os.getenv("SOURCE_LANG") or "").strip() or None,
            target_lang=os.getenv("TARGET_LANG", "EN-US").strip(),
            deepl_api_key=(os.getenv("DEEPL_API_KEY") or "").strip() or None,
            deepl_endpoint=os.getenv("DEEPL_ENDPOINT", "https://api-free.deepl.com/v2/translate").strip(),
            deepl_glossary_id=(os.getenv("DEEPL_GLOSSARY_ID") or "").strip() or None,
            deepl_formality=(os.getenv("DEEPL_FORMALITY") or "").strip() or None,
            wechat_target=os.getenv("WECHAT_TARGET", "File Transfer").strip(),
            wecom_webhook_url=(os.getenv("WECOM_WEBHOOK_URL") or "").strip() or None,
            desktop_send_script=desktop_script,
            desktop_send_timeout_sec=int(os.getenv("DESKTOP_SEND_TIMEOUT_SEC", "45")),
            preview_enabled=_as_bool(os.getenv("PREVIEW_ENABLED", "false"), default=False),
            preview_output_dir=Path(os.getenv("PREVIEW_OUTPUT_DIR", "./data/previews")).expanduser(),
            preview_max_titles=int(os.getenv("PREVIEW_MAX_TITLES", "3")),
            run_interval_sec=int(os.getenv("RUN_INTERVAL_SEC", "600")),
            dry_run=_as_bool(os.getenv("DRY_RUN", "false"), default=False),
        )

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.preview_enabled:
            self.preview_output_dir.mkdir(parents=True, exist_ok=True)
