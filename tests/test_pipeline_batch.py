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


class FailingTranslator(Translator):
    name = "failing"

    def translate(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        raise AssertionError("translator should not be called when cache is hit")


class CapturingSender(Sender):
    name = "capturing"

    def __init__(self, success: bool = True, image_success: bool = True):
        self.success = success
        self.image_success = image_success
        self.calls: list[tuple[str, str]] = []
        self.image_calls: list[tuple[str, Path]] = []
        self.events: list[str] = []

    def send(self, target: str, message: str) -> DeliveryResult:
        self.events.append("text")
        self.calls.append((target, message))
        return DeliveryResult(
            channel=self.name,
            success=self.success,
            error_message=None if self.success else "send failed",
        )

    def send_image(self, target: str, image_path: Path) -> DeliveryResult:
        self.events.append("image")
        self.image_calls.append((target, image_path))
        return DeliveryResult(
            channel=self.name,
            success=self.image_success,
            error_message=None if self.image_success else "image send failed",
        )


def _settings(db_path: Path, max_articles: int = 10) -> Settings:
    return Settings(
        afr_homepage_url="https://www.afr.com",
        afr_article_path_prefix=None,
        afr_max_articles=max_articles,
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
        preview_enabled=False,
        preview_output_dir=db_path.parent / "previews",
        preview_max_titles=3,
        run_interval_sec=60,
        dry_run=False,
    )


def _article(article_id: str, title: str, content: Optional[str] = None) -> Article:
    return Article(
        article_id=article_id,
        record_key=f"{article_id}:2026-02-07T00:00:00+00:00",
        url=f"https://www.afr.com/test-{article_id}",
        title=title,
        summary="summary",
        published_at="2026-02-07T00:00:00+00:00",
        updated_at="2026-02-07T00:00:00+00:00",
        content=content,
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


def test_pipeline_single_article_sends_title_and_content(tmp_path: Path) -> None:
    article = _article(
        "pone001",
        "Single Title",
        content="This is full article content with enough details.",
    )
    sender = CapturingSender(success=True)

    pipeline = NewsPipeline(
        settings=_settings(tmp_path / "single.db", max_articles=1),
        fetcher=FakeFetcher([article]),
        translator=PrefixTranslator(),
        sender_router=SenderRouter(primary=sender, fallback=None),
        store=SQLiteStore(tmp_path / "single.db"),
    )

    stats = pipeline.run_once()

    assert len(sender.calls) == 1
    assert sender.calls[0][1] == "标题：ZH:Single Title\n\n内容：ZH:This is full article content with enough details."
    assert stats.sent == 1
    assert stats.failed == 0


def test_pipeline_single_article_uses_cached_translation_when_title_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "single-cache.db"
    store = SQLiteStore(db_path)
    sender = CapturingSender(success=True)
    cached_article = _article(
        "pcache001",
        "Same Title",
        content="Old cached content",
    )
    store.upsert_event(
        cached_article,
        translated_title="ZH:缓存标题",
        translated_summary="ZH:缓存正文",
    )
    store.mark_sent(cached_article.record_key, "capturing")

    incoming_article = _article(
        "pincoming001",
        "Same Title",
        content="Fresh content should not trigger translation",
    )
    pipeline = NewsPipeline(
        settings=_settings(db_path, max_articles=1),
        fetcher=FakeFetcher([incoming_article]),
        translator=FailingTranslator(),
        sender_router=SenderRouter(primary=sender, fallback=None),
        store=store,
    )

    stats = pipeline.run_once()

    assert len(sender.calls) == 1
    assert sender.calls[0][1] == "标题：ZH:缓存标题\n\n内容：ZH:缓存正文"
    assert stats.sent == 1
    assert stats.failed == 0


class FakePreviewRenderer:
    def __init__(self, preview_path: Path):
        self.preview_path = preview_path
        self.captured_titles: list[str] = []

    def render(self, translated_titles: list[str]) -> Path:
        self.captured_titles = translated_titles
        return self.preview_path


def test_pipeline_sends_preview_image_before_text(tmp_path: Path) -> None:
    articles = [_article("pabc001", "Title One"), _article("pabc002", "Title Two")]
    sender = CapturingSender(success=True, image_success=True)
    preview_path = tmp_path / "previews" / "preview.png"
    preview_path.parent.mkdir(parents=True)
    preview_path.write_bytes(b"fake-png")

    settings = _settings(tmp_path / "preview.db")
    settings.preview_enabled = True
    preview_renderer = FakePreviewRenderer(preview_path)

    pipeline = NewsPipeline(
        settings=settings,
        fetcher=FakeFetcher(articles),
        translator=PrefixTranslator(),
        sender_router=SenderRouter(primary=sender, fallback=None),
        store=SQLiteStore(tmp_path / "preview.db"),
        preview_renderer=preview_renderer,
    )

    stats = pipeline.run_once()

    assert sender.events == ["image", "text"]
    assert sender.image_calls[0] == ("江上", preview_path)
    assert sender.calls[0][1] == "1. ZH:Title One；2. ZH:Title Two"
    assert preview_renderer.captured_titles == ["ZH:Title One", "ZH:Title Two"]
    assert stats.sent == 2
