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
