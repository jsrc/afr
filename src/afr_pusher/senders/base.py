from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import DeliveryResult


class Sender(ABC):
    name: str

    @abstractmethod
    def send(self, target: str, message: str) -> DeliveryResult:
        raise NotImplementedError
