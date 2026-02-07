from __future__ import annotations

from dataclasses import dataclass
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
        if self.dry_run:
            result = DeliveryResult(channel="dry-run", success=True, response_excerpt="dry run mode")
            return RoutedDelivery(final_result=result, attempts=[result])

        attempts: list[DeliveryResult] = []

        if self.primary:
            primary_result = self.primary.send(target, message)
            attempts.append(primary_result)
            if primary_result.success:
                return RoutedDelivery(final_result=primary_result, attempts=attempts)

        if self.fallback and (not self.primary or self.fallback.name != self.primary.name):
            fallback_result = self.fallback.send(target, message)
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
