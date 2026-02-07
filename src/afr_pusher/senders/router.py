from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..models import DeliveryResult
from .base import Sender


@dataclass(frozen=True)
class RoutedDelivery:
    final_result: DeliveryResult
    attempts: list[DeliveryResult]


class SenderRouter:
    def __init__(
        self,
        primary: Optional[Sender],
        fallback: Optional[Sender],
        dry_run: bool = False,
    ):
        self.primary = primary
        self.fallback = fallback
        self.dry_run = dry_run

    def send(self, target: str, message: str) -> RoutedDelivery:
        return self._route(
            primary_call=lambda sender: sender.send(target, message),
            fallback_call=lambda sender: sender.send(target, message),
        )

    def send_image(self, target: str, image_path: Path) -> RoutedDelivery:
        return self._route(
            primary_call=lambda sender: sender.send_image(target, image_path),
            fallback_call=lambda sender: sender.send_image(target, image_path),
        )

    def _route(self, primary_call, fallback_call) -> RoutedDelivery:
        if self.dry_run:
            result = DeliveryResult(channel="dry-run", success=True, response_excerpt="dry run mode")
            return RoutedDelivery(final_result=result, attempts=[result])

        attempts: list[DeliveryResult] = []

        if self.primary:
            primary_result = primary_call(self.primary)
            attempts.append(primary_result)
            if primary_result.success:
                return RoutedDelivery(final_result=primary_result, attempts=attempts)

        if self.fallback and (not self.primary or self.fallback.name != self.primary.name):
            fallback_result = fallback_call(self.fallback)
            attempts.append(fallback_result)
            return RoutedDelivery(final_result=fallback_result, attempts=attempts)

        if attempts:
            return RoutedDelivery(final_result=attempts[-1], attempts=attempts)

        failed = DeliveryResult(
            channel="none",
            success=False,
            error_message="No sender configured",
        )
        return RoutedDelivery(final_result=failed, attempts=[failed])
