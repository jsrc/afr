import argparse
from datetime import datetime, timezone

import pytest

from afr_pusher.cli import _next_daily_run, _parse_daily_at


def test_parse_daily_at_valid() -> None:
    assert _parse_daily_at("16:30") == (16, 30)
    assert _parse_daily_at("6:05") == (6, 5)


def test_parse_daily_at_invalid() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_daily_at("24:00")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_daily_at("16:60")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_daily_at("4pm")


def test_next_daily_run_same_day() -> None:
    now = datetime(2026, 2, 7, 15, 0, 0, tzinfo=timezone.utc)
    assert _next_daily_run(now, 16, 30) == datetime(2026, 2, 7, 16, 30, 0, tzinfo=timezone.utc)


def test_next_daily_run_next_day_when_passed_or_equal() -> None:
    now_equal = datetime(2026, 2, 7, 16, 30, 0, tzinfo=timezone.utc)
    assert _next_daily_run(now_equal, 16, 30) == datetime(2026, 2, 8, 16, 30, 0, tzinfo=timezone.utc)

    now_late = datetime(2026, 2, 7, 20, 0, 0, tzinfo=timezone.utc)
    assert _next_daily_run(now_late, 16, 30) == datetime(2026, 2, 8, 16, 30, 0, tzinfo=timezone.utc)
