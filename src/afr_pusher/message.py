from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import Optional

from .models import ArticleBlock

_LIST_ITEM_RE = re.compile(r"^(?:[-*•]\s+)(.+)$")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def serialize_content_blocks(blocks: Sequence[ArticleBlock]) -> str:
    parts: list[str] = []
    for block in blocks:
        text = _normalize_text(block.text)
        if not text:
            continue
        prefix = "• " if block.kind == "list_item" else ""
        parts.append(f"{prefix}{text}")
    return "\n\n".join(parts)


def parse_content_blocks(text: str) -> tuple[ArticleBlock, ...]:
    raw = (text or "").strip()
    if not raw:
        return ()

    pieces = [piece.strip() for piece in re.split(r"\n\s*\n+", raw) if piece.strip()]
    if len(pieces) <= 1:
        pieces = [piece.strip() for piece in raw.splitlines() if piece.strip()]

    blocks: list[ArticleBlock] = []
    for piece in pieces:
        match = _LIST_ITEM_RE.match(piece)
        if match:
            item = _normalize_text(match.group(1))
            if item:
                blocks.append(ArticleBlock(kind="list_item", text=item))
            continue

        paragraph = _normalize_text(piece)
        if paragraph:
            blocks.append(ArticleBlock(kind="paragraph", text=paragraph))

    return tuple(blocks)


def truncate_content_blocks(blocks: Sequence[ArticleBlock], max_chars: int) -> tuple[ArticleBlock, ...]:
    truncated: list[ArticleBlock] = []
    total = 0
    separator = 2

    for block in blocks:
        text = _normalize_text(block.text)
        if not text:
            continue

        extra = len(text) if not truncated else len(text) + separator
        if total + extra <= max_chars:
            truncated.append(ArticleBlock(kind=block.kind, text=text))
            total += extra
            continue

        remaining = max_chars - total - (separator if truncated else 0)
        if remaining > 3:
            truncated.append(ArticleBlock(kind=block.kind, text=_truncate(text, remaining)))
        break

    return tuple(truncated)


def format_batch_message(
    translated_titles: Sequence[str],
    article_urls: Optional[Sequence[Optional[str]]] = None,
    *,
    header: str = "AFR 要闻速览",
) -> str:
    cleaned_titles = [title.strip() for title in translated_titles if title and title.strip()]
    if not cleaned_titles:
        return ""

    lines = [f"<b>{html.escape(header)}</b>", ""]
    for idx, title in enumerate(cleaned_titles, start=1):
        safe_title = html.escape(title)
        url = article_urls[idx - 1] if article_urls and idx - 1 < len(article_urls) else None
        if url:
            safe_url = html.escape(url, quote=True)
            lines.append(f'{idx}. <a href="{safe_url}">{safe_title}</a>')
        else:
            lines.append(f"{idx}. {safe_title}")
    return "\n".join(lines)


def format_single_article_message(
    translated_title: str,
    translated_content: str,
    *,
    article_url: Optional[str] = None,
    content_blocks: Optional[Sequence[ArticleBlock]] = None,
    content_limit: int = 2600,
) -> str:
    title = translated_title.strip()
    safe_title = html.escape(title)

    normalized_blocks = content_blocks or parse_content_blocks(translated_content)
    body_blocks = truncate_content_blocks(normalized_blocks, content_limit)

    if article_url:
        safe_url = html.escape(article_url, quote=True)
        lines = [f'<a href="{safe_url}"><b>{safe_title}</b></a>']
    else:
        lines = [f"<b>{safe_title}</b>"]

    if not body_blocks:
        return "\n".join(lines)

    lines.append("")
    for block in body_blocks:
        safe_text = html.escape(block.text)
        if block.kind == "list_item":
            lines.append(f"• {safe_text}")
        else:
            lines.append(safe_text)
            lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
