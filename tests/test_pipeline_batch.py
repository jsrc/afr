from pathlib import Path
from typing import Optional

from afr_pusher.config import Settings
from afr_pusher.models import Article, DeliveryResult
from afr_pusher.pipeline import NewsPipeline
from afr_pusher.senders.base import Sender
from afr_pusher.senders.router import SenderRouter
from afr_pusher.store import SQLiteStore
from afr_pusher.translators.base import Translator


class FakeFetcher:
    def __init__(self, articles: list[Article]):
        self._articles = articles

    def fetch_recent(self, limit: int = 10) -> list[Article]:
        return self._articles[:limit]


class PrefixTranslator(Translator):
    name = "prefix"

    def translate(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        return f"ZH:{text}"


class CapturingSender(Sender):
    name = "capturing"

    def __init__(self, success: bool = True):
        self.success = success
        self.calls: list[tuple[str, str]] = []

    def send(self, target: str, message: str) -> DeliveryResult:
        self.calls.append((target, message))
        return DeliveryResult(
            channel=self.name,
            success=self.success,
            error_message=None if self.success else "send failed",
        )


def _settings(db_path: Path) -> Settings:
    return Settings(
        afr_homepage_url="https://www.afr.com",
        afr_article_path_prefix=None,
        afr_max_articles=10,
        request_timeout_sec=5,
        request_user_agent="ua",
        db_path=db_path,
        translator_provider="noop",
        source_lang="EN",
        target_lang="ZH",
        deepl_api_key=None,
        deepl_endpoint="https://api-free.deepl.com/v2/translate",
        deepl_glossary_id=None,
        deepl_formality=None,
        wechat_target="江上",
        wecom_webhook_url=None,
        desktop_send_script=None,
        desktop_send_timeout_sec=30,
        run_interval_sec=60,
        dry_run=False,
    )


def _article(article_id: str, title: str) -> Article:
    return Article(
        article_id=article_id,
        record_key=f"{article_id}:2026-02-07T00:00:00+00:00",
        url=f"https://www.afr.com/test-{article_id}",
        title=title,
        summary="summary",
        published_at="2026-02-07T00:00:00+00:00",
        updated_at="2026-02-07T00:00:00+00:00",
    )


def test_pipeline_sends_titles_in_one_message(tmp_path: Path) -> None:
    articles = [_article("pabc001", "Title One"), _article("pabc002", "Title Two")]
    sender = CapturingSender(success=True)

    pipeline = NewsPipeline(
        settings=_settings(tmp_path / "batch.db"),
        fetcher=FakeFetcher(articles),
        translator=PrefixTranslator(),
        sender_router=SenderRouter(primary=sender, fallback=None),
        store=SQLiteStore(tmp_path / "batch.db"),
    )

    stats = pipeline.run_once()

    assert len(sender.calls) == 1
    assert sender.calls[0][0] == "江上"
    assert sender.calls[0][1] == "1. ZH:Title One；2. ZH:Title Two"
    assert stats.sent == 2
    assert stats.failed == 0
    assert stats.skipped == 0
