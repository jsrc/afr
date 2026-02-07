from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Optional

import requests

from ..models import DeliveryResult
from .base import Sender


class WeComWebhookSender(Sender):
    name = "wecom-webhook"

    def __init__(self, webhook_url: str, timeout_sec: float, session: Optional[requests.Session] = None):
        if not webhook_url:
            raise ValueError("WECOM_WEBHOOK_URL is required for WeCom webhook sender")
        self.webhook_url = webhook_url
        self.timeout_sec = timeout_sec
        self.session = session or requests.Session()

    def send(self, target: str, message: str) -> DeliveryResult:
        payload = {
            "msgtype": "text",
            "text": {
                "content": message,
            },
        }
        return self._post_payload(payload)

    def send_image(self, target: str, image_path: Path) -> DeliveryResult:
        try:
            image_bytes = Path(image_path).read_bytes()
        except Exception as exc:
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"read image failed: {exc}",
            )

        payload = {
            "msgtype": "image",
            "image": {
                "base64": base64.b64encode(image_bytes).decode("ascii"),
                "md5": hashlib.md5(image_bytes).hexdigest(),
            },
        }
        return self._post_payload(payload)

    def _post_payload(self, payload: dict) -> DeliveryResult:
        try:
            response = self.session.post(
                self.webhook_url,
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

        body: dict
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = {}

        if body.get("errcode") not in (None, 0):
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"WeCom error: {body.get('errmsg', 'unknown')}",
                response_excerpt=json.dumps(body, ensure_ascii=True)[:400],
            )

        return DeliveryResult(
            channel=self.name,
            success=True,
            response_excerpt=(response.text or "")[:400],
        )
