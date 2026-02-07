from __future__ import annotations

from typing import Optional

from .base import Translator


class NoopTranslator(Translator):
    name = "noop"

    def translate(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        return text
