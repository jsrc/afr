from __future__ import annotations

import logging
from typing import Optional

from .config import Settings
from .fetchers.afr import AFRFetcher
from .message import format_batch_message, format_single_article_message
from .models import Article, PipelineStats
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
    ):
        self.settings = settings
        self.fetcher = fetcher
        self.translator = translator
        self.sender_router = sender_router
        self.store = store
        self.logger = logger or logging.getLogger(__name__)

    def run_once(self) -> PipelineStats:
        stats = PipelineStats()
        articles = self.fetcher.fetch_recent(limit=self.settings.afr_max_articles)
        stats = PipelineStats(
            fetched=len(articles),
            sent=0,
            failed=0,
            skipped=0,
        )
        include_article_content = self.settings.afr_max_articles == 1
        ready_for_delivery: list[tuple[Article, str, str]] = []

        for article in articles:
            # Persist raw content first so a failed translation/delivery can be retried later.
            self.store.upsert_event(article, article.title, article.summary)

            try:
                translated_title = self.translator.translate(
                    article.title,
                    source_lang=self.settings.source_lang,
                    target_lang=self.settings.target_lang,
                )
                content_source = article.content or article.summary
                translated_summary = (
                    self.translator.translate(
                        content_source,
                        source_lang=self.settings.source_lang,
                        target_lang=self.settings.target_lang,
                    )
                    if include_article_content
                    else article.summary
                )
                self.store.upsert_event(article, translated_title, translated_summary)
                ready_for_delivery.append((article, translated_title, translated_summary))

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

        if include_article_content and len(ready_for_delivery) == 1:
            _, title, content = ready_for_delivery[0]
            batch_message = format_single_article_message(title, content)
            mode = "single-with-content"
        else:
            batch_message = format_batch_message([title for _, title, _ in ready_for_delivery])
            mode = "batch-titles"
        self.logger.info(
            "sending message: mode=%s items=%s chars=%s",
            mode,
            len(ready_for_delivery),
            len(batch_message),
        )
        routed = self.sender_router.send(self.settings.wechat_target, batch_message)

        for article, _, _ in ready_for_delivery:
            for attempt in routed.attempts:
                self.store.record_delivery_attempt(article.record_key, self.settings.wechat_target, attempt)

        if routed.final_result.success:
            for article, _, _ in ready_for_delivery:
                self.store.mark_sent(article.record_key, routed.final_result.channel)
            stats = PipelineStats(
                fetched=stats.fetched,
                sent=stats.sent + len(ready_for_delivery),
                failed=stats.failed,
                skipped=stats.skipped,
            )
        else:
            error = routed.final_result.error_message or "unknown send failure"
            for article, _, _ in ready_for_delivery:
                self.store.mark_failed(article.record_key, error)
            stats = PipelineStats(
                fetched=stats.fetched,
                sent=stats.sent,
                failed=stats.failed + len(ready_for_delivery),
                skipped=stats.skipped,
            )
            self.logger.warning("batch delivery failed: count=%s error=%s", len(ready_for_delivery), error)

        return stats
