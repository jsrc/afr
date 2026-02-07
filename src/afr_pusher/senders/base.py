from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import DeliveryResult


class Sender(ABC):
    name: str

    @abstractmethod
    def send(self, target: str, message: str) -> DeliveryResult:
        raise NotImplementedError

    def send_image(self, target: str, image_path: Path) -> DeliveryResult:
        return DeliveryResult(
            channel=self.name,
            success=False,
            error_message=f"image send not supported by {self.name}",
        )
