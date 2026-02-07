from __future__ import annotations

from collections.abc import Sequence


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def format_batch_message(translated_titles: Sequence[str]) -> str:
    cleaned_titles = [title.strip() for title in translated_titles if title and title.strip()]
    if not cleaned_titles:
        return ""

    return "；".join(f"{idx}. {title}" for idx, title in enumerate(cleaned_titles, start=1))


def format_single_article_message(translated_title: str, translated_content: str, content_limit: int = 2600) -> str:
    title = translated_title.strip()
    body = _truncate((translated_content or "").strip(), content_limit)
    if not body:
        return title
    return f"标题：{title}\n\n内容：{body}"
