from __future__ import annotations

from collections.abc import Sequence


def format_batch_message(translated_titles: Sequence[str]) -> str:
    cleaned_titles = [title.strip() for title in translated_titles if title and title.strip()]
    if not cleaned_titles:
        return ""

    return "；".join(f"{idx}. {title}" for idx, title in enumerate(cleaned_titles, start=1))
