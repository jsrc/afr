from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from ..models import DeliveryResult
from .base import Sender


class DesktopScriptSender(Sender):
    name = "desktop-script"

    def __init__(self, script_path: Path, timeout_sec: int = 45):
        self.script_path = Path(script_path)
        self.timeout_sec = timeout_sec

    def send(self, target: str, message: str) -> DeliveryResult:
        if not self.script_path.exists():
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"Script not found: {self.script_path}",
            )

        return self._run(command=["bash", str(self.script_path), target], input_text=message)

    def send_image(self, target: str, image_path: Path) -> DeliveryResult:
        if not self.script_path.exists():
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"Script not found: {self.script_path}",
            )
        image = Path(image_path)
        if not image.exists():
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"Image not found: {image}",
            )

        return self._run(
            command=["bash", str(self.script_path), target, "--image", str(image)],
            input_text=None,
        )

    def _run(self, command: list[str], input_text: Optional[str]) -> DeliveryResult:
        env = os.environ.copy()
        env.setdefault("LANG", "en_US.UTF-8")

        try:
            proc = subprocess.run(
                command,
                check=False,
                timeout=self.timeout_sec,
                capture_output=True,
                input=input_text,
                text=True,
                env=env,
            )
        except Exception as exc:
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"Script execution failed: {exc}",
            )

        output = "\n".join(part for part in [proc.stdout, proc.stderr] if part).strip()
        if proc.returncode != 0:
            return DeliveryResult(
                channel=self.name,
                success=False,
                error_message=f"Script exit code {proc.returncode}",
                response_excerpt=output[:400] if output else None,
            )

        return DeliveryResult(
            channel=self.name,
            success=True,
            response_excerpt=output[:400] if output else None,
        )
