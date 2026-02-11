from pathlib import Path

import pytest
import requests

import afr_pusher.cli as cli
from afr_pusher.cli import _build_router
from afr_pusher.config import Settings


def _settings() -> Settings:
    return Settings(
        afr_homepage_url="https://www.afr.com",
        afr_article_path_prefix=None,
        afr_max_articles=10,
        request_timeout_sec=5,
        request_user_agent="ua",
        db_path=Path("/tmp/afr-pusher-test.db"),
        translator_provider="noop",
        source_lang="EN",
        target_lang="ZH",
        deepl_api_key=None,
        deepl_endpoint="https://api-free.deepl.com/v2/translate",
        deepl_glossary_id=None,
        deepl_formality=None,
        wechat_target="File Transfer",
        telegram_bot_token="token-1",
        telegram_chat_id="-100123456",
        telegram_api_base="https://api.telegram.org",
        desktop_send_script=Path("/tmp/send.sh"),
        desktop_send_timeout_sec=30,
        miniapp_api_key="api-key",
        miniapp_api_cors_origins=("https://mini.example.com",),
        preview_enabled=False,
        preview_output_dir=Path("/tmp/previews"),
        preview_max_titles=3,
        run_interval_sec=60,
        dry_run=False,
    )


def test_build_router_uses_telegram_as_primary_with_desktop_fallback_when_supported(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_desktop_sender_supported", lambda: True)
    settings = _settings()
    router = _build_router(settings, session=requests.Session())

    assert router.primary is not None
    assert router.primary.name == "telegram-bot"
    assert router.fallback is not None
    assert router.fallback.name == "desktop-script"
    assert settings.wechat_target == "-100123456"


def test_build_router_rejects_partial_telegram_config(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_desktop_sender_supported", lambda: True)
    settings = _settings()
    settings.telegram_chat_id = None

    with pytest.raises(SystemExit):
        _build_router(settings, session=requests.Session())


def test_build_router_can_force_desktop_channel(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_desktop_sender_supported", lambda: True)
    settings = _settings()
    router = _build_router(settings, session=requests.Session(), send_channel="desktop")

    assert router.primary is not None
    assert router.primary.name == "desktop-script"
    assert router.fallback is None


def test_build_router_can_force_telegram_channel(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_desktop_sender_supported", lambda: True)
    settings = _settings()
    router = _build_router(settings, session=requests.Session(), send_channel="telegram")

    assert router.primary is not None
    assert router.primary.name == "telegram-bot"
    assert router.fallback is None
    assert settings.wechat_target == "-100123456"


def test_build_router_force_desktop_rejected_on_non_macos(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_desktop_sender_supported", lambda: False)
    settings = _settings()

    with pytest.raises(SystemExit):
        _build_router(settings, session=requests.Session(), send_channel="desktop")


def test_build_router_non_macos_disables_desktop(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_desktop_sender_supported", lambda: False)
    settings = _settings()
    settings.telegram_bot_token = None
    settings.telegram_chat_id = None

    router = _build_router(settings, session=requests.Session())

    assert router.primary is None
    assert router.fallback is None
