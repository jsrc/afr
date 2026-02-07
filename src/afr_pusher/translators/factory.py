from __future__ import annotations

from collections.abc import Callable
from typing import Optional

import requests

from ..config import Settings
from .base import Translator
from .deepl import DeepLTranslator
from .noop import NoopTranslator

TranslatorBuilder = Callable[[Settings, Optional[requests.Session]], Translator]

_TRANSLATOR_REGISTRY: dict[str, TranslatorBuilder] = {}


def register_translator(name: str, builder: TranslatorBuilder) -> None:
    _TRANSLATOR_REGISTRY[name.strip().lower()] = builder


def _build_deepl(settings: Settings, session: Optional[requests.Session]) -> Translator:
    return DeepLTranslator(
        api_key=settings.deepl_api_key or "",
        endpoint=settings.deepl_endpoint,
        timeout_sec=settings.request_timeout_sec,
        glossary_id=settings.deepl_glossary_id,
        formality=settings.deepl_formality,
        session=session,
    )


def _build_noop(settings: Settings, session: Optional[requests.Session]) -> Translator:
    return NoopTranslator()


def build_translator(settings: Settings, session: Optional[requests.Session] = None) -> Translator:
    if not _TRANSLATOR_REGISTRY:
        register_translator("deepl", _build_deepl)
        register_translator("noop", _build_noop)
        register_translator("none", _build_noop)

    provider = settings.translator_provider.strip().lower()
    builder = _TRANSLATOR_REGISTRY.get(provider)
    if not builder:
        options = ", ".join(sorted(_TRANSLATOR_REGISTRY.keys()))
        raise ValueError(f"Unsupported translator provider '{provider}'. Available: {options}")
    return builder(settings, session)
