import subprocess
import sys
from pathlib import Path

import afr_pusher.cli as cli
from afr_pusher.cli import _build_launchd_plist


def test_build_launchd_plist_contains_schedule_and_args(tmp_path: Path) -> None:
    workdir = tmp_path / "repo"
    workdir.mkdir(parents=True)
    config_file = workdir / "config.ini"
    config_file.write_text("[settings]\nAFR_MAX_ARTICLES=10\n", encoding="utf-8")
    env_file = workdir / ".env"
    env_file.write_text("X=1\n", encoding="utf-8")

    xml = _build_launchd_plist(
        label="com.afr.pusher",
        python_executable="/usr/bin/python3",
        workdir=workdir,
        config_file=config_file,
        env_file=env_file,
        hour=16,
        minute=30,
        max_articles=10,
        log_level="INFO",
    )

    assert "<string>com.afr.pusher</string>" in xml
    assert "<key>Hour</key>" in xml and "<integer>16</integer>" in xml
    assert "<key>Minute</key>" in xml and "<integer>30</integer>" in xml
    assert "<string>--config-file</string>" in xml
    assert f"<string>{config_file}</string>" in xml
    assert "<string>--env-file</string>" in xml
    assert f"<string>{env_file}</string>" in xml
    assert "<string>--max-articles</string>" in xml
    assert "<string>10</string>" in xml
    assert "<key>PYTHONPATH</key>" in xml
    assert f"<string>{workdir / 'src'}</string>" in xml


def test_install_launchd_job_writes_plist_and_bootstraps(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    config_file = repo / "config.ini"
    config_file.write_text("[settings]\nAFR_MAX_ARTICLES=10\n", encoding="utf-8")
    env_file = repo / ".env"
    env_file.write_text("X=1\n", encoding="utf-8")

    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(repo)

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    plist_path = cli._install_launchd_job(
        label="com.afr.pusher",
        config_file=config_file,
        env_file=env_file,
        hour=16,
        minute=30,
        max_articles=10,
        log_level="INFO",
    )

    assert plist_path == home_dir / "Library" / "LaunchAgents" / "com.afr.pusher.plist"
    xml = plist_path.read_text(encoding="utf-8")
    assert f"<string>{sys.executable}</string>" in xml
    assert f"<string>{config_file.resolve()}</string>" in xml
    assert f"<string>{env_file.resolve()}</string>" in xml
    assert calls[0][:2] == ["launchctl", "bootout"]
    assert calls[1][:2] == ["launchctl", "bootstrap"]
    assert calls[2][:2] == ["launchctl", "enable"]
