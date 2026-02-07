from __future__ import annotations

from pathlib import Path
from typing import Optional

import requests

from ..models import DeliveryResult
from .base import Sender


class TelegramBotSender(Sender):
    name = "telegram-bot"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout_sec: float,
        api_base: str = "https://api.telegram.org",
        session: Optional[requests.Session] = None,
    ):
        token = bot_token.strip()
        target_chat = chat_id.strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required for Telegram sender")
        if not target_chat:
            raise ValueError("TELEGRAM_CHAT_ID is required for Telegram sender")
        base = api_base.strip() if api_base else "https://api.telegram.org"
        if not base:
            base = "https://api.telegram.org"

        self.bot_token = token
        self.chat_id = target_chat
        self.timeout_sec = timeout_sec
        self.api_base = base.rstrip("/")
        self.session = session or requests.Session()

    def send(self, target: str, message: str) -> DeliveryResult:
        payload = {
            "chat_id": self.chat_id,
            "text": message,
        }
        return self._post_json("sendMessage", payload)

    def send_image(self, target: str, image_path: Path) -> DeliveryResult:
        path = Path(image_path)
        if not path.exists():
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"Image not found: {path}",
            )

        url = self._method_url("sendPhoto")
        try:
            with path.open("rb") as image_file:
                response = self.session.post(
                    url,
                    data={"chat_id": self.chat_id},
                    files={"photo": image_file},
                    timeout=self.timeout_sec,
                )
                response.raise_for_status()
        except Exception as exc:
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"HTTP request failed: {exc}",
            )

        return self._parse_response(response)

    def _method_url(self, method: str) -> str:
        return f"{self.api_base}/bot{self.bot_token}/{method}"

    def _post_json(self, method: str, payload: dict) -> DeliveryResult:
        try:
            response = self.session.post(
                self._method_url(method),
                json=payload,
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
        except Exception as exc:
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"HTTP request failed: {exc}",
            )

        return self._parse_response(response)

    def _parse_response(self, response: requests.Response) -> DeliveryResult:
        body: dict
        try:
            body = response.json()
        except Exception:
            body = {}

        if not body.get("ok", False):
            description = body.get("description") or "unknown"
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"Telegram error: {description}",
                response_excerpt=(response.text or "")[:400],
            )

        return DeliveryResult(
            channel=self.name,
            success=True,
            response_excerpt=(response.text or "")[:400],
        )
