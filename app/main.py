#!/usr/bin/env python3
"""
CI/CD Homework App — with Google OAuth 2.0 Device Flow.

Local run : authenticates via Device Flow, fetches user profile, writes result.txt.
CI run    : skips OAuth (CI=true is set automatically by GitHub Actions).

Token cache: .token_cache.json (gitignored) — delete to force re-authentication.
"""

import datetime
import json
import os
import pathlib
import time

import requests
from dotenv import load_dotenv

# Load .env from the repo root (two levels up from this file: app/ → repo root).
# This works correctly regardless of which directory the script is run from.
_REPO_ROOT = pathlib.Path(__file__).parent.parent
load_dotenv(_REPO_ROOT / ".env")

# ── Google OAuth 2.0 Device Flow constants ────────────────────────────────────
DEVICE_AUTH_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
SCOPES = "openid email profile"
TOKEN_CACHE_PATH = pathlib.Path(".token_cache.json")


def _load_cached_token() -> dict | None:
    """Return a cached token dict if it exists and has not expired, else None."""
    if not TOKEN_CACHE_PATH.exists():
        return None
    try:
        data = json.loads(TOKEN_CACHE_PATH.read_text())
        # Check expiry: stored_at + expires_in (with 60 s buffer)
        stored_at = data.get("stored_at", 0)
        expires_in = data.get("expires_in", 0)
        if time.time() < stored_at + expires_in - 60:
            return data
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _save_token(token_data: dict) -> None:
    """Persist the token response to disk, stamped with the current time."""
    token_data["stored_at"] = time.time()
    TOKEN_CACHE_PATH.write_text(json.dumps(token_data, indent=2))


def authenticate() -> dict:
    """
    Run the OAuth 2.0 Device Flow and return a token dict with an access_token.
    Uses cached token if still valid; otherwise prompts the user.
    """
    cached = _load_cached_token()
    if cached:
        print("[auth] Using cached token.")
        return cached

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise EnvironmentError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set.\n"
            f"  Expected .env file at: {_REPO_ROOT / '.env'}\n"
            "  Add the following lines to that file:\n"
            "    GOOGLE_CLIENT_ID=<your-client-id>\n"
            "    GOOGLE_CLIENT_SECRET=<your-client-secret>"
        )

    # Step 1 — Request a device + user code
    resp = requests.post(
        DEVICE_AUTH_URL,
        data={"client_id": client_id, "scope": SCOPES},
        timeout=10,
    )
    if resp.status_code == 401:
        raise EnvironmentError(
            "Google rejected the Client ID (401 Unauthorized).\n"
            "  Check that GOOGLE_CLIENT_ID is correct in your .env file and\n"
            "  that the OAuth client has 'Device' application type enabled in\n"
            "  the Google Cloud Console."
        )
    resp.raise_for_status()
    device_info = resp.json()

    device_code = device_info["device_code"]
    user_code = device_info["user_code"]
    verification_url = device_info["verification_url"]
    interval = device_info.get("interval", 5)

    # Step 2 — Prompt the user
    print()
    print("=" * 60)
    print("  Google sign-in required.")
    print(f"  1. Open:  {verification_url}")
    print(f"  2. Enter: {user_code}")
    print("=" * 60)
    print("Waiting for authorisation", end="", flush=True)

    # Step 3 — Poll until approved or error
    while True:
        time.sleep(interval)
        token_resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=10,
        )
        token_data = token_resp.json()

        error = token_data.get("error")
        if error == "authorization_pending":
            print(".", end="", flush=True)
            continue
        if error == "slow_down":
            interval += 5
            print(".", end="", flush=True)
            continue
        if error:
            print()
            raise RuntimeError(f"OAuth error: {error} — {token_data.get('error_description', '')}")

        # Success
        print(" authorised!")
        _save_token(token_data)
        return token_data


def fetch_user_profile(access_token: str) -> dict:
    """Return the Google user profile dict for the given access token."""
    resp = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def run(output_dir: str = "output") -> None:
    """Main entry point."""
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    print(f"[{now}] Hello from the CI/CD Homework App!")

    out_path = pathlib.Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    result_file = out_path / "result.txt"

    # ── Required APP_SECRET ───────────────────────────────────────────────
    app_secret = os.environ.get("APP_SECRET", "")
    if not app_secret:
        raise EnvironmentError(
            "APP_SECRET is required but not set.\n"
            "  Local runs : add APP_SECRET=<value> to your .env file.\n"
            "  CI         : add APP_SECRET under Settings → Secrets and variables → Actions."
        )
    masked = app_secret[:2] + "*" * max(0, len(app_secret) - 2)
    print(f"[{now}] APP_SECRET is set: {masked}")

    # ── Google OAuth ──────────────────────────────────────────────────────
    in_ci = os.environ.get("CI", "").lower() == "true"

    if in_ci:
        print(f"[{now}] Running in CI — OAuth skipped.")
        result_file.write_text(
            f"Run timestamp : {now}\n"
            f"Secret present: yes\n"
            f"OAuth         : skipped (CI environment)\n"
            f"Status        : OK\n"
        )
    else:
        token = authenticate()
        profile = fetch_user_profile(token["access_token"])

        name = profile.get("name", "Unknown")
        email = profile.get("email", "Unknown")
        print(f"[{now}] Authenticated as: {name} <{email}>")

        result_file.write_text(
            f"Run timestamp : {now}\n"
            f"Secret present: yes\n"
            f"OAuth         : authenticated\n"
            f"User name     : {name}\n"
            f"User email    : {email}\n"
            f"Status        : OK\n"
        )

    print(f"[{now}] Result written to {result_file}")


if __name__ == "__main__":
    run()
