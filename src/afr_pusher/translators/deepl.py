from __future__ import annotations

from typing import Optional

import requests

from .base import Translator


class DeepLTranslator(Translator):
    name = "deepl"

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        timeout_sec: float,
        glossary_id: Optional[str] = None,
        formality: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        if not api_key:
            raise ValueError("DEEPL_API_KEY is required for DeepL translator")
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.glossary_id = glossary_id
        self.formality = formality
        self.session = session or requests.Session()

    def translate(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        if not text.strip():
            return text

        payload: dict[str, str] = {
            "text": text,
            "target_lang": target_lang,
        }
        if source_lang:
            payload["source_lang"] = source_lang
        if self.glossary_id:
            payload["glossary_id"] = self.glossary_id
        if self.formality:
            payload["formality"] = self.formality

        response = self.session.post(
            self.endpoint,
            data=payload,
            headers={"Authorization": f"DeepL-Auth-Key {self.api_key}"},
            timeout=self.timeout_sec,
        )
        response.raise_for_status()

        body = response.json()
        translations = body.get("translations")
        if not translations:
            raise RuntimeError(f"DeepL response missing translations: {body}")

        translated = translations[0].get("text")
        if not translated:
            raise RuntimeError(f"DeepL response missing translated text: {body}")
        return str(translated)
