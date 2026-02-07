import pytest
import requests

from afr_pusher.cli import _build_router
from afr_pusher.config import Settings


def _settings() -> Settings:
    return Settings(
        afr_homepage_url="https://www.afr.com",
        afr_article_path_prefix=None,
        afr_max_articles=10,
        request_timeout_sec=5,
        request_user_agent="ua",
        db_path=__import__("pathlib").Path("/tmp/afr-pusher-test.db"),
        translator_provider="noop",
        source_lang="EN",
        target_lang="ZH",
        deepl_api_key=None,
        deepl_endpoint="https://api-free.deepl.com/v2/translate",
        deepl_glossary_id=None,
        deepl_formality=None,
        wechat_target="File Transfer",
        wecom_webhook_url="https://example.com/wecom",
        telegram_bot_token="token-1",
        telegram_chat_id="-100123456",
        telegram_api_base="https://api.telegram.org",
        desktop_send_script=__import__("pathlib").Path("/tmp/send.sh"),
        desktop_send_timeout_sec=30,
        preview_enabled=False,
        preview_output_dir=__import__("pathlib").Path("/tmp/previews"),
        preview_max_titles=3,
        run_interval_sec=60,
        dry_run=False,
    )


def test_build_router_uses_telegram_as_primary() -> None:
    settings = _settings()
    router = _build_router(settings, session=requests.Session())

    assert router.primary is not None
    assert router.primary.name == "telegram-bot"
    assert router.fallback is not None
    assert router.fallback.name == "wecom-webhook"
    assert settings.wechat_target == "-100123456"


def test_build_router_rejects_partial_telegram_config() -> None:
    settings = _settings()
    settings.telegram_chat_id = None

    with pytest.raises(SystemExit):
        _build_router(settings, session=requests.Session())


def test_build_router_can_force_wecom_channel() -> None:
    settings = _settings()
    router = _build_router(settings, session=requests.Session(), send_channel="wecom")

    assert router.primary is not None
    assert router.primary.name == "wecom-webhook"
    assert router.fallback is None
    assert settings.wechat_target == "File Transfer"


def test_build_router_can_force_desktop_channel() -> None:
    settings = _settings()
    router = _build_router(settings, session=requests.Session(), send_channel="desktop")

    assert router.primary is not None
    assert router.primary.name == "desktop-script"
    assert router.fallback is None


def test_build_router_can_force_telegram_channel() -> None:
    settings = _settings()
    router = _build_router(settings, session=requests.Session(), send_channel="telegram")

    assert router.primary is not None
    assert router.primary.name == "telegram-bot"
    assert router.fallback is None
    assert settings.wechat_target == "-100123456"


def test_build_router_force_wecom_ignores_partial_telegram_config() -> None:
    settings = _settings()
    settings.telegram_chat_id = None
    router = _build_router(settings, session=requests.Session(), send_channel="wecom")

    assert router.primary is not None
    assert router.primary.name == "wecom-webhook"


def test_build_router_force_wecom_requires_config() -> None:
    settings = _settings()
    settings.wecom_webhook_url = None

    with pytest.raises(SystemExit):
        _build_router(settings, session=requests.Session(), send_channel="wecom")
