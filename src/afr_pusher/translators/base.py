from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Translator(ABC):
    name: str

    @abstractmethod
    def translate(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        raise NotImplementedError
