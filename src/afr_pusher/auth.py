from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import requests

AFR_DOMAIN_SUFFIX = "afr.com"
AFR_MEMBER_DETAILS_KEY = "ffx:ffx-member-details"
AFR_PIANO_JWT_HASH_KEY = "ffx:hash:pianoExternalJWT"


def load_afr_storage_state(
    session: requests.Session,
    storage_state_path: Path | str,
    logger: Optional[logging.Logger] = None,
) -> int:
    logger = logger or logging.getLogger(__name__)
    path = Path(storage_state_path).expanduser()
    if not path.exists():
        logger.info("AFR storage state not found: path=%s", path)
        return 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    cookies = payload.get("cookies")
    if not isinstance(cookies, list):
        raise ValueError(f"Invalid AFR storage state file: {path}")

    loaded = 0
    for item in cookies:
        if not isinstance(item, dict):
            continue

        domain = str(item.get("domain") or "")
        if AFR_DOMAIN_SUFFIX not in domain:
            continue

        name = str(item.get("name") or "").strip()
        if not name:
            continue

        value = str(item.get("value") or "")
        cookie_path = str(item.get("path") or "/") or "/"
        expires = item.get("expires")
        expires_value = int(expires) if isinstance(expires, (int, float)) and expires > 0 else None

        session.cookies.set(
            name,
            value,
            domain=domain,
            path=cookie_path,
            secure=bool(item.get("secure", False)),
            expires=expires_value,
        )
        loaded += 1

    logger.info("AFR storage state loaded: path=%s cookies=%s", path, loaded)
    return loaded


def has_afr_login_state(storage_state_path: Path | str) -> bool:
    path = Path(storage_state_path).expanduser()
    if not path.exists():
        return False

    payload = json.loads(path.read_text(encoding="utf-8"))
    origins = payload.get("origins")
    if not isinstance(origins, list):
        return False

    for origin in origins:
        if not isinstance(origin, dict):
            continue
        origin_url = str(origin.get("origin") or "")
        if "afr.com" not in origin_url:
            continue
        local_storage = origin.get("localStorage")
        if not isinstance(local_storage, list):
            continue

        for item in local_storage:
            if not isinstance(item, dict):
                continue
            key = str(item.get("name") or "")
            value = str(item.get("value") or "").strip()
            if key in {AFR_MEMBER_DETAILS_KEY, AFR_PIANO_JWT_HASH_KEY} and value:
                return True

    return False


def refresh_afr_storage_state(
    storage_state_path: Path | str,
    start_url: str,
    user_agent: str,
    logger: Optional[logging.Logger] = None,
) -> Path:
    logger = logger or logging.getLogger(__name__)
    if not sys.stdin.isatty():
        raise SystemExit("--refresh-afr-session requires an interactive terminal.")

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright is not installed. Run `pip install -e '.[browser]'` "
            "and `python -m playwright install chromium` first."
        ) from exc

    path = Path(storage_state_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("opening AFR browser session: url=%s", start_url)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            context_kwargs = {"user_agent": user_agent}
            if path.exists():
                context_kwargs["storage_state"] = str(path)

            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.goto(start_url, wait_until="domcontentloaded")

            print(
                "AFR browser opened. Complete login in the browser window, "
                "then come back here and press Enter to save the session.",
                flush=True,
            )
            input()

            cookies = [
                cookie
                for cookie in context.cookies()
                if AFR_DOMAIN_SUFFIX in str(cookie.get("domain") or "")
            ]
            if not cookies:
                raise SystemExit(
                    "No AFR cookies were found. Make sure login completed before pressing Enter."
                )

            context.storage_state(path=str(path))
            browser.close()
    except PlaywrightError as exc:
        raise SystemExit(f"Failed to capture AFR browser session: {exc}") from exc

    logger.info("AFR browser session saved: path=%s cookies=%s", path, len(cookies))
    return path
