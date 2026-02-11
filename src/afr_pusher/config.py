from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WECHAT_SCRIPT = PROJECT_ROOT / "scripts" / "send.sh"


def _as_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_ini(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(path, encoding="utf-8")

    values: dict[str, str] = {}
    for key, value in parser.defaults().items():
        values[key.upper()] = value
    for section in parser.sections():
        for key, value in parser.items(section):
            values[key.upper()] = value
    return values


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        if key:
            values[key.upper()] = value
    return values


def _pick(
    values: Mapping[str, str],
    key: str,
    default: Optional[str] = None,
) -> Optional[str]:
    value = values.get(key)
    if value is None:
        return default
    return str(value)


def _split_csv(value: Optional[str]) -> tuple[str, ...]:
    raw = (value or "").strip()
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


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
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    telegram_api_base: str
    desktop_send_script: Optional[Path]
    desktop_send_timeout_sec: int
    miniapp_api_key: Optional[str]
    miniapp_api_cors_origins: tuple[str, ...]
    preview_enabled: bool
    preview_output_dir: Path
    preview_max_titles: int

    run_interval_sec: int
    dry_run: bool

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str]) -> "Settings":
        values = {key.upper(): str(value) for key, value in mapping.items() if value is not None}
        desktop_script_raw = _pick(values, "DESKTOP_SEND_SCRIPT", str(DEFAULT_WECHAT_SCRIPT))
        desktop_script_raw = (desktop_script_raw or "").strip()
        desktop_script = None
        if desktop_script_raw:
            candidate = Path(desktop_script_raw).expanduser()
            if not candidate.is_absolute():
                cwd_candidate = (Path.cwd() / candidate).resolve()
                project_candidate = (PROJECT_ROOT / candidate).resolve()
                candidate = cwd_candidate if cwd_candidate.exists() else project_candidate
            desktop_script = candidate

        return cls(
            afr_homepage_url=(_pick(values, "AFR_HOMEPAGE_URL", "https://www.afr.com") or "").strip(),
            afr_article_path_prefix=(_pick(values, "AFR_ARTICLE_PATH_PREFIX") or "").strip() or None,
            afr_max_articles=int(_pick(values, "AFR_MAX_ARTICLES", "10") or "10"),
            request_timeout_sec=float(_pick(values, "REQUEST_TIMEOUT_SEC", "12") or "12"),
            request_user_agent=(_pick(
                values,
                "REQUEST_USER_AGENT",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36",
            ) or "").strip(),
            db_path=Path(_pick(values, "DB_PATH", "./data/afr_pusher.db") or "./data/afr_pusher.db").expanduser(),
            translator_provider=(_pick(values, "TRANSLATOR_PROVIDER", "deepl") or "deepl").strip().lower(),
            source_lang=(_pick(values, "SOURCE_LANG") or "").strip() or None,
            target_lang=(_pick(values, "TARGET_LANG", "EN-US") or "EN-US").strip(),
            deepl_api_key=(_pick(values, "DEEPL_API_KEY") or "").strip() or None,
            deepl_endpoint=(
                _pick(values, "DEEPL_ENDPOINT", "https://api-free.deepl.com/v2/translate")
                or "https://api-free.deepl.com/v2/translate"
            ).strip(),
            deepl_glossary_id=(_pick(values, "DEEPL_GLOSSARY_ID") or "").strip() or None,
            deepl_formality=(_pick(values, "DEEPL_FORMALITY") or "").strip() or None,
            wechat_target=(_pick(values, "WECHAT_TARGET", "File Transfer") or "File Transfer").strip(),
            telegram_bot_token=(_pick(values, "TELEGRAM_BOT_TOKEN") or "").strip() or None,
            telegram_chat_id=(_pick(values, "TELEGRAM_CHAT_ID") or "").strip() or None,
            telegram_api_base=(_pick(values, "TELEGRAM_API_BASE", "https://api.telegram.org") or "").strip(),
            desktop_send_script=desktop_script,
            desktop_send_timeout_sec=int(_pick(values, "DESKTOP_SEND_TIMEOUT_SEC", "45") or "45"),
            miniapp_api_key=(_pick(values, "MINIAPP_API_KEY") or "").strip() or None,
            miniapp_api_cors_origins=_split_csv(_pick(values, "MINIAPP_API_CORS_ORIGINS")),
            preview_enabled=_as_bool(_pick(values, "PREVIEW_ENABLED", "false"), default=False),
            preview_output_dir=Path(_pick(values, "PREVIEW_OUTPUT_DIR", "./data/previews") or "").expanduser(),
            preview_max_titles=int(_pick(values, "PREVIEW_MAX_TITLES", "3") or "3"),
            run_interval_sec=int(_pick(values, "RUN_INTERVAL_SEC", "600") or "600"),
            dry_run=_as_bool(_pick(values, "DRY_RUN", "false"), default=False),
        )

    @classmethod
    def from_files(
        cls,
        *,
        config_file: Path | str = "config.ini",
        env_file: Path | str = ".env",
        base_env: Optional[Mapping[str, str]] = None,
    ) -> "Settings":
        merged_values: dict[str, str] = {}
        merged_values.update(_parse_ini(Path(config_file)))
        merged_values.update(_parse_dotenv(Path(env_file)))
        if base_env is None:
            base_env = os.environ
        for key, value in base_env.items():
            if value is not None:
                merged_values[key.upper()] = str(value)
        return cls.from_mapping(merged_values)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.from_mapping(os.environ)

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.preview_enabled:
            self.preview_output_dir.mkdir(parents=True, exist_ok=True)
