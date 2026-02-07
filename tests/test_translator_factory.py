import pytest

from afr_pusher.config import Settings
from afr_pusher.translators.factory import build_translator


def _settings(provider: str) -> Settings:
    return Settings(
        afr_homepage_url="https://www.afr.com",
        afr_article_path_prefix=None,
        afr_max_articles=5,
        request_timeout_sec=5,
        request_user_agent="ua",
        db_path=__import__("pathlib").Path("/tmp/afr-pusher-test.db"),
        translator_provider=provider,
        source_lang=None,
        target_lang="EN-US",
        deepl_api_key=None,
        deepl_endpoint="https://api-free.deepl.com/v2/translate",
        deepl_glossary_id=None,
        deepl_formality=None,
        wechat_target="Alice",
        wecom_webhook_url=None,
        desktop_send_script=None,
        desktop_send_timeout_sec=30,
        preview_enabled=False,
        preview_output_dir=__import__("pathlib").Path("/tmp/afr-pusher-previews"),
        preview_max_titles=3,
        run_interval_sec=60,
        dry_run=True,
    )


def test_noop_translator() -> None:
    translator = build_translator(_settings("noop"))
    assert translator.translate("hello", source_lang=None, target_lang="EN-US") == "hello"


def test_unknown_translator_raises() -> None:
    with pytest.raises(ValueError):
        build_translator(_settings("unknown-provider"))
