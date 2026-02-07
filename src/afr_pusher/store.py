from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

from .models import Article, DeliveryResult, utc_now_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS article_events (
    record_key TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    published_at TEXT,
    updated_at TEXT,
    translated_title TEXT NOT NULL,
    translated_summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    sent_channel TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    last_attempt_at TEXT,
    sent_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_article_events_status ON article_events(status);
CREATE INDEX IF NOT EXISTS idx_article_events_article_id ON article_events(article_id);

CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_key TEXT NOT NULL,
    channel TEXT NOT NULL,
    target TEXT NOT NULL,
    success INTEGER NOT NULL,
    error_message TEXT,
    response_excerpt TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(record_key) REFERENCES article_events(record_key)
);

CREATE INDEX IF NOT EXISTS idx_deliveries_record_key ON deliveries(record_key);
"""


class SQLiteStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def is_sent(self, record_key: str) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT status FROM article_events WHERE record_key = ?",
                (record_key,),
            ).fetchone()
            return bool(row and row["status"] == "sent")

    def upsert_event(
        self,
        article: Article,
        translated_title: str,
        translated_summary: str,
    ) -> None:
        now = utc_now_iso()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO article_events (
                    record_key, article_id, url, title, summary,
                    published_at, updated_at, translated_title, translated_summary,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                ON CONFLICT(record_key) DO UPDATE SET
                    title = excluded.title,
                    summary = excluded.summary,
                    published_at = excluded.published_at,
                    updated_at = excluded.updated_at,
                    translated_title = excluded.translated_title,
                    translated_summary = excluded.translated_summary,
                    status = CASE
                        WHEN article_events.status = 'sent' THEN 'sent'
                        ELSE 'pending'
                    END
                """,
                (
                    article.record_key,
                    article.article_id,
                    article.url,
                    article.title,
                    article.summary,
                    article.published_at,
                    article.updated_at,
                    translated_title,
                    translated_summary,
                    now,
                ),
            )
            conn.commit()

    def mark_sent(self, record_key: str, channel: str) -> None:
        now = utc_now_iso()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE article_events
                SET status = 'sent', sent_channel = ?, sent_at = ?, last_attempt_at = ?, last_error = NULL
                WHERE record_key = ?
                """,
                (channel, now, now, record_key),
            )
            conn.commit()

    def mark_failed(self, record_key: str, error_message: str) -> None:
        now = utc_now_iso()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE article_events
                SET status = 'failed', last_error = ?, last_attempt_at = ?
                WHERE record_key = ?
                """,
                (error_message[:1000], now, record_key),
            )
            conn.commit()

    def record_delivery_attempt(self, record_key: str, target: str, result: DeliveryResult) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO deliveries (
                    record_key, channel, target, success,
                    error_message, response_excerpt, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_key,
                    result.channel,
                    target,
                    1 if result.success else 0,
                    (result.error_message or "")[:1000] or None,
                    (result.response_excerpt or "")[:1000] or None,
                    utc_now_iso(),
                ),
            )
            conn.commit()

    def get_event_status(self, record_key: str) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT status FROM article_events WHERE record_key = ?",
                (record_key,),
            ).fetchone()
            if not row:
                return None
            return str(row["status"])
