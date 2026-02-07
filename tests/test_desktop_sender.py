from pathlib import Path

from afr_pusher.senders.desktop_script import DesktopScriptSender


def test_desktop_sender_passes_full_message_via_stdin(tmp_path: Path, monkeypatch) -> None:
    script_path = tmp_path / "capture.sh"
    output_path = tmp_path / "captured.txt"

    script_path.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "target=\"$1\"\n"
        "payload=\"$(cat)\"\n"
        "printf 'target=%s\\n' \"$target\" > \"$OUTPUT_PATH\"\n"
        "printf 'payload=%s' \"$payload\" >> \"$OUTPUT_PATH\"\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)

    monkeypatch.setenv("OUTPUT_PATH", str(output_path))

    sender = DesktopScriptSender(script_path=script_path, timeout_sec=5)
    message = "1. 第一条标题；2. 第二条标题\n3. Third title with punctuation ;:,."
    result = sender.send("江上", message)

    assert result.success is True
    captured = output_path.read_text(encoding="utf-8")
    assert "target=江上" in captured
    assert "payload=1. 第一条标题；2. 第二条标题\n3. Third title with punctuation ;:,." in captured


def test_desktop_sender_send_image_uses_image_mode(tmp_path: Path, monkeypatch) -> None:
    script_path = tmp_path / "capture_image.sh"
    output_path = tmp_path / "captured-image.txt"
    image_path = tmp_path / "preview.png"
    image_path.write_bytes(b"fake-png")

    script_path.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "target=\"$1\"\n"
        "mode=\"$2\"\n"
        "image=\"$3\"\n"
        "printf 'target=%s\\n' \"$target\" > \"$OUTPUT_PATH\"\n"
        "printf 'mode=%s\\n' \"$mode\" >> \"$OUTPUT_PATH\"\n"
        "printf 'image=%s\\n' \"$image\" >> \"$OUTPUT_PATH\"\n"
        "if [[ ! -f \"$image\" ]]; then\n"
        "  echo 'missing-image' >> \"$OUTPUT_PATH\"\n"
        "  exit 2\n"
        "fi\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)

    monkeypatch.setenv("OUTPUT_PATH", str(output_path))

    sender = DesktopScriptSender(script_path=script_path, timeout_sec=5)
    result = sender.send_image("江上", image_path)

    assert result.success is True
    captured = output_path.read_text(encoding="utf-8")
    assert "target=江上" in captured
    assert "mode=--image" in captured
    assert f"image={image_path}" in captured
