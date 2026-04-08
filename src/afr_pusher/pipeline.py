from __future__ import annotations

import logging
from typing import Optional

from .config import Settings
from .fetchers.afr import AFRFetcher
from .message import (
    format_batch_message,
    format_single_article_message,
    parse_content_blocks,
    serialize_content_blocks,
)
from .models import Article, ArticleBlock, PipelineStats
from .preview import SummaryCardRenderer
from .senders.router import SenderRouter
from .store import SQLiteStore
from .translators.base import Translator


class NewsPipeline:
    def __init__(
        self,
        settings: Settings,
        fetcher: AFRFetcher,
        translator: Translator,
        sender_router: SenderRouter,
        store: SQLiteStore,
        logger: Optional[logging.Logger] = None,
        preview_renderer: Optional[SummaryCardRenderer] = None,
        feed_name: str = "afr",
        batch_message_title: str = "AFR 要闻速览",
    ):
        self.settings = settings
        self.fetcher = fetcher
        self.translator = translator
        self.sender_router = sender_router
        self.store = store
        self.logger = logger or logging.getLogger(__name__)
        self.feed_name = feed_name
        self.batch_message_title = batch_message_title
        if preview_renderer is not None:
            self.preview_renderer = preview_renderer
        elif settings.preview_enabled:
            self.preview_renderer = SummaryCardRenderer(
                output_dir=settings.preview_output_dir,
                max_titles=settings.preview_max_titles,
                logger=self.logger,
            )
        else:
            self.preview_renderer = None

    def run_once(self) -> PipelineStats:
        stats = PipelineStats()
        delivery_target = self.settings.telegram_chat_id or ""
        articles = self.fetcher.fetch_recent(limit=self.settings.afr_max_articles)
        stats = PipelineStats(
            fetched=len(articles),
            sent=0,
            failed=0,
            skipped=0,
        )
        include_article_content = self.settings.afr_max_articles == 1
        ready_for_delivery: list[tuple[Article, str, str, tuple[ArticleBlock, ...]]] = []

        for article in articles:
            if self.store.is_sent(article.record_key):
                stats = PipelineStats(
                    fetched=stats.fetched,
                    sent=stats.sent,
                    failed=stats.failed,
                    skipped=stats.skipped + 1,
                )
                self.logger.info("skipping already-sent article: record_key=%s url=%s", article.record_key, article.url)
                continue

            # Persist raw content first so a failed translation/delivery can be retried later.
            self.store.upsert_event(article, article.title, article.summary)

            try:
                cached_translation = (
                    self.store.get_sent_translation_by_title(article.title) if include_article_content else None
                )
                content_source = article.content or article.summary
                use_cached_translation = False
                if cached_translation is not None:
                    translated_title, translated_summary = cached_translation
                    # Guard against stale cache where translated title is still raw source text.
                    if translated_title.strip() != article.title.strip():
                        use_cached_translation = True
                    else:
                        self.logger.info(
                            "translation cache bypassed (looks untranslated): title=%s",
                            article.title,
                        )
                if use_cached_translation:
                    self.logger.info("translation cache hit: title=%s", article.title)
                    translated_blocks = parse_content_blocks(translated_summary) if include_article_content else ()
                else:
                    translated_title = self.translator.translate(
                        article.title,
                        source_lang=self.settings.source_lang,
                        target_lang=self.settings.target_lang,
                    )
                    if include_article_content:
                        translated_blocks = self._translate_content_blocks(article)
                        translated_summary = serialize_content_blocks(translated_blocks) or self.translator.translate(
                            content_source,
                            source_lang=self.settings.source_lang,
                            target_lang=self.settings.target_lang,
                        )
                    else:
                        translated_summary = article.summary
                        translated_blocks = ()
                    if include_article_content:
                        self.logger.info("translation cache miss: title=%s", article.title)
                self.store.upsert_event(article, translated_title, translated_summary)
                ready_for_delivery.append((article, translated_title, translated_summary, translated_blocks))

            except Exception as exc:
                self.store.mark_failed(article.record_key, str(exc))
                stats = PipelineStats(
                    fetched=stats.fetched,
                    sent=stats.sent,
                    failed=stats.failed + 1,
                    skipped=stats.skipped,
                )
                self.logger.exception("pipeline failed for article=%s", article.url)

        if not ready_for_delivery:
            return stats

        preview_path = None
        if self.preview_renderer is not None:
            translated_titles = [title for _, title, _, _ in ready_for_delivery]
            preview_path = self.preview_renderer.render(translated_titles)
            if preview_path:
                preview_result = self.sender_router.send_image(delivery_target, preview_path)
                if preview_result.final_result.success:
                    self.logger.info(
                        "preview image sent: path=%s channel=%s",
                        preview_path,
                        preview_result.final_result.channel,
                    )
                else:
                    self.logger.warning(
                        "preview image send failed: path=%s error=%s",
                        preview_path,
                        preview_result.final_result.error_message,
                    )

        if include_article_content and len(ready_for_delivery) == 1:
            article, title, content, blocks = ready_for_delivery[0]
            batch_message = format_single_article_message(
                title,
                content,
                article_url=article.url,
                content_blocks=blocks,
            )
            mode = "single-with-content"
        else:
            batch_message = format_batch_message(
                [title for _, title, _, _ in ready_for_delivery],
                article_urls=[article.url for article, _, _, _ in ready_for_delivery],
                header=self.batch_message_title,
            )
            mode = "batch-titles"
        self.logger.info(
            "sending message: feed=%s mode=%s items=%s chars=%s",
            self.feed_name,
            mode,
            len(ready_for_delivery),
            len(batch_message),
        )
        routed = self.sender_router.send(delivery_target, batch_message)

        for article, _, _, _ in ready_for_delivery:
            for attempt in routed.attempts:
                self.store.record_delivery_attempt(article.record_key, delivery_target, attempt)

        if routed.final_result.success:
            for article, _, _, _ in ready_for_delivery:
                self.store.mark_sent(article.record_key, routed.final_result.channel)
            stats = PipelineStats(
                fetched=stats.fetched,
                sent=stats.sent + len(ready_for_delivery),
                failed=stats.failed,
                skipped=stats.skipped,
            )
        else:
            error = routed.final_result.error_message or "unknown send failure"
            for article, _, _, _ in ready_for_delivery:
                self.store.mark_failed(article.record_key, error)
            stats = PipelineStats(
                fetched=stats.fetched,
                sent=stats.sent,
                failed=stats.failed + len(ready_for_delivery),
                skipped=stats.skipped,
            )
            self.logger.warning("batch delivery failed: count=%s error=%s", len(ready_for_delivery), error)

        return stats

    def _translate_content_blocks(self, article: Article) -> tuple[ArticleBlock, ...]:
        source_blocks = article.content_blocks or parse_content_blocks(article.content or article.summary)
        translated: list[ArticleBlock] = []
        for block in source_blocks:
            if not block.text.strip():
                continue
            translated_text = self.translator.translate(
                block.text,
                source_lang=self.settings.source_lang,
                target_lang=self.settings.target_lang,
            )
            translated.append(ArticleBlock(kind=block.kind, text=translated_text.strip()))
        return tuple(translated)
