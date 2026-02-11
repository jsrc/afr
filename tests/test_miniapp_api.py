from pathlib import Path

import pytest

from afr_pusher.miniapp_api import _parse_cors_origins, _resolve_api_key, build_app
from afr_pusher.miniapp_api import MiniAppArticleStore
from afr_pusher.models import Article, DeliveryResult
from afr_pusher.store import SQLiteStore


def _article(idx: int) -> Article:
    ts = f"2026-02-{idx:02d}T00:00:00+00:00"
    return Article(
        article_id=f"p{idx:06d}",
        record_key=f"p{idx:06d}:{ts}",
        url=f"https://www.afr.com/test-{idx}",
        title=f"Title {idx}",
        summary=f"Summary {idx}",
        published_at=ts,
        updated_at=ts,
    )


def test_miniapp_store_list_articles_with_status_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "miniapp.db"
    store = SQLiteStore(db_path)
    a1 = _article(1)
    a2 = _article(2)

    store.upsert_event(a1, translated_title="T1", translated_summary="S1")
    store.mark_sent(a1.record_key, "telegram")

    store.upsert_event(a2, translated_title="T2", translated_summary="S2")
    store.mark_failed(a2.record_key, "network timeout")

    api_store = MiniAppArticleStore(db_path)

    sent_items = api_store.list_articles(limit=20, status="sent")
    assert len(sent_items) == 1
    assert sent_items[0]["record_key"] == a1.record_key
    assert sent_items[0]["translated_title"] == "T1"

    failed_items = api_store.list_articles(limit=20, status="failed")
    assert len(failed_items) == 1
    assert failed_items[0]["record_key"] == a2.record_key
    assert failed_items[0]["last_error"] == "network timeout"


def test_miniapp_store_get_article_returns_delivery_history(tmp_path: Path) -> None:
    db_path = tmp_path / "miniapp-detail.db"
    store = SQLiteStore(db_path)
    article = _article(3)

    store.upsert_event(article, translated_title="Detail Title", translated_summary="Detail Summary")
    store.record_delivery_attempt(
        article.record_key,
        "target-room",
        DeliveryResult(channel="telegram-bot", success=True, response_excerpt="ok"),
    )

    api_store = MiniAppArticleStore(db_path)
    item = api_store.get_article(article.record_key)

    assert item is not None
    assert item["record_key"] == article.record_key
    assert item["translated_summary"] == "Detail Summary"

    deliveries = item["deliveries"]
    assert isinstance(deliveries, list)
    assert len(deliveries) == 1
    assert deliveries[0]["channel"] == "telegram-bot"
    assert deliveries[0]["success"] is True


def test_miniapp_store_get_article_returns_none_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "miniapp-missing.db"
    SQLiteStore(db_path)
    api_store = MiniAppArticleStore(db_path)

    assert api_store.get_article("missing") is None


def test_build_app_requires_api_key(tmp_path: Path) -> None:
    db_path = tmp_path / "miniapp-requires-key.db"
    with pytest.raises(ValueError):
        build_app(db_path=db_path, api_key="")


def test_parse_cors_origins_supports_comma_separated_values() -> None:
    origins = _parse_cors_origins("https://a.example.com, https://b.example.com")
    assert origins == ("https://a.example.com", "https://b.example.com")


def test_resolve_api_key_prefers_explicit_value() -> None:
    assert _resolve_api_key("  abc123  ") == "abc123"


def test_resolve_api_key_raises_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("MINIAPP_API_KEY", raising=False)
    with pytest.raises(ValueError):
        _resolve_api_key(None)
