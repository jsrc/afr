from pathlib import Path
from typing import Optional

from afr_pusher.cli import _run_pipelines
from afr_pusher.config import Settings
from afr_pusher.models import Article, ArticleBlock, DeliveryResult
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
        afr_source=None,
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
        telegram_bot_token=None,
        telegram_chat_id="@jsrcpush",
        telegram_api_base="https://api.telegram.org",
        telegram_parse_mode="HTML",
        miniapp_api_key="api-key",
        miniapp_api_cors_origins=("https://mini.example.com",),
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
    assert sender.calls[0][0] == "@jsrcpush"
    assert sender.calls[0][1] == (
        "<b>AFR 要闻速览</b>\n\n"
        '1. <a href="https://www.afr.com/test-pabc001">ZH:Title One</a>\n'
        '2. <a href="https://www.afr.com/test-pabc002">ZH:Title Two</a>'
    )
    assert stats.sent == 2
    assert stats.failed == 0
    assert stats.skipped == 0


def test_pipeline_supports_custom_batch_title(tmp_path: Path) -> None:
    articles = [_article("pabc001", "Title One"), _article("pabc002", "Title Two")]
    sender = CapturingSender(success=True)

    pipeline = NewsPipeline(
        settings=_settings(tmp_path / "street.db"),
        fetcher=FakeFetcher(articles),
        translator=PrefixTranslator(),
        sender_router=SenderRouter(primary=sender, fallback=None),
        store=SQLiteStore(tmp_path / "street.db"),
        batch_message_title="Street Talk 文章速览",
    )

    pipeline.run_once()

    assert sender.calls[0][1] == (
        "<b>Street Talk 文章速览</b>\n\n"
        '1. <a href="https://www.afr.com/test-pabc001">ZH:Title One</a>\n'
        '2. <a href="https://www.afr.com/test-pabc002">ZH:Title Two</a>'
    )


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
    assert sender.calls[0][1] == (
        '<a href="https://www.afr.com/test-pone001"><b>ZH:Single Title</b></a>\n\n'
        "ZH:This is full article content with enough details."
    )
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
    assert sender.calls[0][1] == (
        '<a href="https://www.afr.com/test-pincoming001"><b>ZH:缓存标题</b></a>\n\n'
        "ZH:缓存正文"
    )
    assert stats.sent == 1
    assert stats.failed == 0


def test_pipeline_single_article_bypasses_untranslated_cache(tmp_path: Path) -> None:
    db_path = tmp_path / "single-cache-bypass.db"
    store = SQLiteStore(db_path)
    sender = CapturingSender(success=True)
    cached_article = _article(
        "pcache002",
        "Same Title",
        content="Same content",
    )
    # Simulate stale cache from an older run where translation matched source text.
    store.upsert_event(
        cached_article,
        translated_title="Same Title",
        translated_summary="Same content",
    )
    store.mark_sent(cached_article.record_key, "capturing")

    incoming_article = _article(
        "pincoming002",
        "Same Title",
        content="Same content",
    )
    pipeline = NewsPipeline(
        settings=_settings(db_path, max_articles=1),
        fetcher=FakeFetcher([incoming_article]),
        translator=PrefixTranslator(),
        sender_router=SenderRouter(primary=sender, fallback=None),
        store=store,
    )

    stats = pipeline.run_once()

    assert len(sender.calls) == 1
    assert sender.calls[0][1] == (
        '<a href="https://www.afr.com/test-pincoming002"><b>ZH:Same Title</b></a>\n\n'
        "ZH:Same content"
    )
    assert stats.sent == 1
    assert stats.failed == 0


def test_pipeline_single_article_preserves_block_layout(tmp_path: Path) -> None:
    article = Article(
        article_id="pblocks001",
        record_key="pblocks001:2026-02-07T00:00:00+00:00",
        url="https://www.afr.com/test-pblocks001",
        title="Structured Title",
        summary="summary",
        published_at="2026-02-07T00:00:00+00:00",
        updated_at="2026-02-07T00:00:00+00:00",
        content="Lead paragraph\n\n• first item\n\n• second item",
        content_blocks=(
            ArticleBlock(kind="paragraph", text="Lead paragraph"),
            ArticleBlock(kind="list_item", text="first item"),
            ArticleBlock(kind="list_item", text="second item"),
        ),
    )
    sender = CapturingSender(success=True)

    pipeline = NewsPipeline(
        settings=_settings(tmp_path / "structured.db", max_articles=1),
        fetcher=FakeFetcher([article]),
        translator=PrefixTranslator(),
        sender_router=SenderRouter(primary=sender, fallback=None),
        store=SQLiteStore(tmp_path / "structured.db"),
    )

    stats = pipeline.run_once()

    assert sender.calls[0][1] == (
        '<a href="https://www.afr.com/test-pblocks001"><b>ZH:Structured Title</b></a>\n\n'
        "ZH:Lead paragraph\n\n"
        "• ZH:first item\n"
        "• ZH:second item"
    )
    assert stats.sent == 1


def test_run_pipelines_sends_primary_and_street_talk_feeds(tmp_path: Path) -> None:
    sender = CapturingSender(success=True)
    db_path = tmp_path / "dual.db"
    router = SenderRouter(primary=sender, fallback=None)
    store = SQLiteStore(db_path)

    primary_pipeline = NewsPipeline(
        settings=_settings(db_path, max_articles=1),
        fetcher=FakeFetcher([_article("pone001", "Primary Title", content="Primary content")]),
        translator=PrefixTranslator(),
        sender_router=router,
        store=store,
        batch_message_title="AFR 要闻速览",
    )
    street_talk_pipeline = NewsPipeline(
        settings=_settings(db_path, max_articles=1),
        fetcher=FakeFetcher([_article("ptwo001", "Street Talk Title", content="Street Talk content")]),
        translator=PrefixTranslator(),
        sender_router=router,
        store=store,
        batch_message_title="Street Talk 文章速览",
        feed_name="street-talk",
    )

    stats = _run_pipelines([primary_pipeline, street_talk_pipeline])

    assert len(sender.calls) == 2
    assert sender.calls[0][1] == (
        '<a href="https://www.afr.com/test-pone001"><b>ZH:Primary Title</b></a>\n\n'
        "ZH:Primary content"
    )
    assert sender.calls[1][1] == (
        '<a href="https://www.afr.com/test-ptwo001"><b>ZH:Street Talk Title</b></a>\n\n'
        "ZH:Street Talk content"
    )
    assert stats.fetched == 2
    assert stats.sent == 2


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
    assert sender.image_calls[0] == ("@jsrcpush", preview_path)
    assert sender.calls[0][1] == (
        "<b>AFR 要闻速览</b>\n\n"
        '1. <a href="https://www.afr.com/test-pabc001">ZH:Title One</a>\n'
        '2. <a href="https://www.afr.com/test-pabc002">ZH:Title Two</a>'
    )
    assert preview_renderer.captured_titles == ["ZH:Title One", "ZH:Title Two"]
    assert stats.sent == 2
