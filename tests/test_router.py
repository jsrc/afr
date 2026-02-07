from afr_pusher.models import DeliveryResult
from afr_pusher.senders.base import Sender
from afr_pusher.senders.router import SenderRouter


class FakeSender(Sender):
    def __init__(self, name: str, success: bool, image_success=None):
        self.name = name
        self._success = success
        self._image_success = image_success if image_success is not None else success

    def send(self, target: str, message: str) -> DeliveryResult:
        return DeliveryResult(
            channel=self.name,
            success=self._success,
            error_message=None if self._success else f"{self.name} failed",
        )

    def send_image(self, target: str, image_path) -> DeliveryResult:
        return DeliveryResult(
            channel=self.name,
            success=self._image_success,
            error_message=None if self._image_success else f"{self.name} image failed",
        )


def test_router_fallback_on_primary_failure() -> None:
    router = SenderRouter(primary=FakeSender("primary", False), fallback=FakeSender("fallback", True))
    routed = router.send("Alice", "hello")

    assert len(routed.attempts) == 2
    assert routed.attempts[0].channel == "primary"
    assert routed.attempts[1].channel == "fallback"
    assert routed.final_result.success is True
    assert routed.final_result.channel == "fallback"


def test_router_short_circuit_when_primary_succeeds() -> None:
    router = SenderRouter(primary=FakeSender("primary", True), fallback=FakeSender("fallback", True))
    routed = router.send("Alice", "hello")

    assert len(routed.attempts) == 1
    assert routed.final_result.channel == "primary"
    assert routed.final_result.success is True


def test_router_send_image_fallback_on_primary_failure(tmp_path) -> None:
    image_path = tmp_path / "preview.png"
    image_path.write_bytes(b"fake")

    router = SenderRouter(
        primary=FakeSender("primary", True, image_success=False),
        fallback=FakeSender("fallback", True, image_success=True),
    )
    routed = router.send_image("Alice", image_path)

    assert len(routed.attempts) == 2
    assert routed.attempts[0].channel == "primary"
    assert routed.attempts[1].channel == "fallback"
    assert routed.final_result.channel == "fallback"
    assert routed.final_result.success is True
