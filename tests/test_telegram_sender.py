from __future__ import annotations

from pathlib import Path

from afr_pusher.senders.telegram import TelegramBotSender


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

    def post(
        self,
        url: str,
        timeout: float,
        json: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
    ):
        call: dict = {"url": url, "timeout": timeout, "json": json, "data": data}
        if files and "photo" in files:
            image = files["photo"]
            call["photo_bytes"] = image.read()
        self.calls.append(call)
        return self.response


def test_telegram_send_message_builds_payload() -> None:
    session = FakeSession(FakeResponse(body={"ok": True, "result": {"message_id": 1}}, text="ok"))
    sender = TelegramBotSender(
        bot_token="abc123",
        chat_id="-1000001",
        timeout_sec=5,
        session=session,
    )

    result = sender.send("unused", "hello world")

    assert result.success is True
    assert len(session.calls) == 1
    assert session.calls[0]["url"] == "https://api.telegram.org/botabc123/sendMessage"
    assert session.calls[0]["json"] == {"chat_id": "-1000001", "text": "hello world"}


def test_telegram_send_image_posts_multipart(tmp_path: Path) -> None:
    image_path = tmp_path / "preview.png"
    image_path.write_bytes(b"fake-png")

    session = FakeSession(FakeResponse(body={"ok": True, "result": {"message_id": 2}}, text="ok"))
    sender = TelegramBotSender(
        bot_token="abc123",
        chat_id="-1000001",
        timeout_sec=5,
        session=session,
    )

    result = sender.send_image("unused", image_path)

    assert result.success is True
    assert len(session.calls) == 1
    assert session.calls[0]["url"] == "https://api.telegram.org/botabc123/sendPhoto"
    assert session.calls[0]["data"] == {"chat_id": "-1000001"}
    assert session.calls[0]["photo_bytes"] == b"fake-png"


def test_telegram_send_handles_api_error() -> None:
    session = FakeSession(
        FakeResponse(
            body={"ok": False, "description": "Bad Request: chat not found"},
            text='{"ok":false}',
        )
    )
    sender = TelegramBotSender(
        bot_token="abc123",
        chat_id="-1000001",
        timeout_sec=5,
        session=session,
    )

    result = sender.send("unused", "hello world")

    assert result.success is False
    assert "chat not found" in (result.error_message or "")
