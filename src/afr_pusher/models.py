from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Article:
    article_id: str
    record_key: str
    url: str
    title: str
    summary: str
    published_at: Optional[str]
    updated_at: Optional[str]
    content: Optional[str] = None


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    success: bool
    error_message: Optional[str] = None
    response_excerpt: Optional[str] = None


@dataclass(frozen=True)
class PipelineStats:
    fetched: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
