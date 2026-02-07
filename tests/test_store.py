from pathlib import Path

from afr_pusher.models import Article
from afr_pusher.store import SQLiteStore


def _article() -> Article:
    return Article(
        article_id="p123abc",
        record_key="p123abc:2026-02-07T00:00:00+00:00",
        url="https://www.afr.com/test-20260207-p123abc",
        title="Title",
        summary="Summary",
        published_at="2026-02-07T00:00:00+00:00",
        updated_at="2026-02-07T00:00:00+00:00",
    )


def test_store_sent_state_is_stable_after_upsert(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    store = SQLiteStore(db_path)
    article = _article()

    store.upsert_event(article, translated_title="T", translated_summary="S")
    assert store.get_event_status(article.record_key) == "pending"

    store.mark_sent(article.record_key, "desktop-script")
    assert store.is_sent(article.record_key) is True

    store.upsert_event(article, translated_title="T2", translated_summary="S2")
    assert store.get_event_status(article.record_key) == "sent"
