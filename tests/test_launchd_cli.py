from pathlib import Path

from afr_pusher.cli import _build_launchd_plist


def test_build_launchd_plist_contains_schedule_and_args(tmp_path: Path) -> None:
    workdir = tmp_path / "repo"
    workdir.mkdir(parents=True)
    env_file = workdir / ".env"
    env_file.write_text("X=1\n", encoding="utf-8")

    xml = _build_launchd_plist(
        label="com.afr.pusher",
        python_executable="/usr/bin/python3",
        workdir=workdir,
        env_file=env_file,
        hour=16,
        minute=30,
        max_articles=10,
        log_level="INFO",
    )

    assert "<string>com.afr.pusher</string>" in xml
    assert "<key>Hour</key>" in xml and "<integer>16</integer>" in xml
    assert "<key>Minute</key>" in xml and "<integer>30</integer>" in xml
    assert "<string>--env-file</string>" in xml
    assert f"<string>{env_file}</string>" in xml
    assert "<string>--max-articles</string>" in xml
    assert "<string>10</string>" in xml
    assert "<key>PYTHONPATH</key>" in xml
    assert f"<string>{workdir / 'src'}</string>" in xml
