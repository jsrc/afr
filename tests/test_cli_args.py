import sys

from afr_pusher.cli import _parse_args


def test_parse_args_uses_expected_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["afr_pusher"])
    args = _parse_args()

    assert args.config_file == "config.ini"
    assert args.env_file == ".env"
    assert args.loop is False
    assert args.interval_sec is None
    assert args.daily_at is None
    assert args.max_articles is None
    assert args.dry_run is False
    assert args.send_channel is None
    assert args.log_level == "INFO"
    assert args.install_launchd is False
    assert args.uninstall_launchd is False
