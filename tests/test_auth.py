import json
from pathlib import Path

import pytest
import requests

from afr_pusher.auth import has_afr_login_state, load_afr_storage_state


def test_load_afr_storage_state_injects_afr_cookies(tmp_path: Path) -> None:
    session = requests.Session()
    storage_state = tmp_path / "afr_storage_state.json"
    storage_state.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "afrsession",
                        "value": "secret",
                        "domain": ".afr.com",
                        "path": "/",
                        "secure": True,
                        "expires": 1893456000,
                    },
                    {
                        "name": "other",
                        "value": "ignored",
                        "domain": ".example.com",
                        "path": "/",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = load_afr_storage_state(session, storage_state)

    assert loaded == 1
    assert session.cookies.get("afrsession", domain=".afr.com", path="/") == "secret"


def test_load_afr_storage_state_rejects_invalid_payload(tmp_path: Path) -> None:
    session = requests.Session()
    storage_state = tmp_path / "afr_storage_state.json"
    storage_state.write_text('{"cookies": "bad"}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_afr_storage_state(session, storage_state)


def test_has_afr_login_state_detects_member_storage(tmp_path: Path) -> None:
    storage_state = tmp_path / "afr_storage_state.json"
    storage_state.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {
                        "origin": "https://www.afr.com",
                        "localStorage": [
                            {"name": "ffx:ffx-member-details", "value": '{"email":"member@example.com"}'},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert has_afr_login_state(storage_state) is True


def test_has_afr_login_state_returns_false_without_member_storage(tmp_path: Path) -> None:
    storage_state = tmp_path / "afr_storage_state.json"
    storage_state.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    assert has_afr_login_state(storage_state) is False
