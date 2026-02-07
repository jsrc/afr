import base64
import hashlib
from pathlib import Path

from afr_pusher.senders.wecom import WeComWebhookSender


class FakeResponse:
    def __init__(self, body: dict, text: str = "", status_code: int = 200):
        self._body = body
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict] = []

    def post(self, url: str, json: dict, timeout: float):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self.response


def test_wecom_send_image_builds_image_payload(tmp_path: Path) -> None:
    image_bytes = b"fake-png-data"
    image_path = tmp_path / "preview.png"
    image_path.write_bytes(image_bytes)

    session = FakeSession(FakeResponse(body={"errcode": 0, "errmsg": "ok"}, text="ok"))
    sender = WeComWebhookSender(
        webhook_url="https://example.com/webhook",
        timeout_sec=5,
        session=session,
    )

    result = sender.send_image("unused-target", image_path)

    assert result.success is True
    assert len(session.calls) == 1

    payload = session.calls[0]["json"]
    assert payload["msgtype"] == "image"
    assert payload["image"]["md5"] == hashlib.md5(image_bytes).hexdigest()
    assert base64.b64decode(payload["image"]["base64"].encode("ascii")) == image_bytes
