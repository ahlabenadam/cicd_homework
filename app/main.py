#!/usr/bin/env python3
"""
CI/CD Homework App — Flask web app with Google OAuth 2.0 Authorization Code Flow.

Run locally:
    python app/main.py
    Open http://localhost:5000 in your browser.

Required environment variables (set in .env or as GitHub Actions secrets):
    APP_SECRET           — Flask session signing key (any long random string)
    GOOGLE_CLIENT_SECRET — Google OAuth client secret
                           (NOT required when SKIP_OAUTH is set to "true")

Advanced — skip-OAuth mode (local dev / CI without Google credentials):
    SKIP_OAUTH=true      — Bypass Google login entirely.
                           ⚠ WARNING: disables ALL authentication.
                           Never use in production or any public environment.
    MOCK_NAME            — Display name in skip mode  (default: "Local User")
    MOCK_EMAIL           — Email shown in skip mode   (default: "local@localhost")
    MOCK_PICTURE         — Avatar URL in skip mode    (default: "" → no avatar)

Accepted values for SKIP_OAUTH: "1", "true", "yes" (case-insensitive).

GOOGLE_CLIENT_ID is committed directly in this file (not sensitive).
"""

import base64
import datetime
import hashlib
import logging
import os
import pathlib
import secrets as _secrets

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import google.auth.transport.requests as google_requests
import google.oauth2.id_token as id_token_module
from google_auth_oauthlib.flow import Flow

# ── Load .env from the repo root ──────────────────────────────────────────────
_REPO_ROOT = pathlib.Path(__file__).parent.parent
load_dotenv(_REPO_ROOT / ".env")

# Allow OAuth over http://localhost (must be set before any request handling)
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

# ── Google OAuth constants ────────────────────────────────────────────────────
# Client ID is not sensitive — committed here as default, but can be overridden
# via GOOGLE_CLIENT_ID in .env (useful when switching OAuth client types).
GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "722819429855-15mcgeovirctt6gfgtqhqpi8pu9od38p.apps.googleusercontent.com",
)
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
# Single source of truth for the port — overridable via PORT env var.
# REDIRECT_URI is derived from it so the two can never drift apart.
PORT = int(os.environ.get("PORT", "5000"))
REDIRECT_URI = f"http://localhost:{PORT}/callback"

OUTPUT_DIR = _REPO_ROOT / "output"

# ── Skip-OAuth mode ───────────────────────────────────────────────────────────
# Evaluated once at module import. Tests that need to toggle this must patch
# the module attribute directly: monkeypatch.setattr(main_module, "SKIP_OAUTH", True)
# Do NOT rely on monkeypatch.setenv("SKIP_OAUTH", ...) — the env var is already baked in.
#
# ⚠ Security: This flag disables all authentication.
#   Never set SKIP_OAUTH=true on any public-facing or production server.
SKIP_OAUTH: bool = os.environ.get("SKIP_OAUTH", "").lower() in ("1", "true", "yes")

_log = logging.getLogger(__name__)


def create_app() -> Flask:
    """Application factory — validates required secrets and wires up routes."""
    app_secret = os.environ.get("APP_SECRET", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    if not app_secret:
        raise EnvironmentError(
            "APP_SECRET is required but not set.\n"
            "  Local runs : add APP_SECRET=<any-long-string> to your .env file.\n"
            "  CI         : add APP_SECRET under Settings → Secrets and variables → Actions."
        )

    # GOOGLE_CLIENT_SECRET is only required when actually using OAuth.
    if not SKIP_OAUTH and not client_secret:
        raise EnvironmentError(
            "GOOGLE_CLIENT_SECRET is required but not set.\n"
            "  Local runs : add GOOGLE_CLIENT_SECRET=<your-secret> to your .env file.\n"
            "  CI         : add GOOGLE_CLIENT_SECRET under Settings → Secrets and variables → Actions.\n"
            "  Get it from: https://console.cloud.google.com/apis/credentials\n"
            "  Tip        : set SKIP_OAUTH=true in .env to run without Google credentials."
        )

    if SKIP_OAUTH:
        _log.warning(
            "⚠ SKIP_OAUTH is enabled — authentication is DISABLED. "
            "Any visitor can sign in without a Google account. "
            "Never use this on a public or production server."
        )

    app = Flask(__name__, template_folder="templates")
    app.secret_key = app_secret  # signs session cookies — keep APP_SECRET private!

    # ── Client config dict used by google-auth-oauthlib ──────────────────────
    # Built even in skip mode so the structure is always consistent.
    # The /login and /callback routes guard against OAuth calls when SKIP_OAUTH=True.
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": client_secret,
            "redirect_uris": [REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        if "email" in session:
            return redirect(url_for("profile"))
        return render_template("index.html", skip_oauth=SKIP_OAUTH)

    @app.route("/login")
    def login():
        # ── Skip-OAuth fast path ──────────────────────────────────────────
        if SKIP_OAUTH:
            session["name"] = os.environ.get("MOCK_NAME", "Local User")
            session["email"] = os.environ.get("MOCK_EMAIL", "local@localhost")
            session["picture"] = os.environ.get("MOCK_PICTURE", "")
            session["skip_oauth"] = True
            return redirect(url_for("profile"))

        # ── Normal OAuth path ─────────────────────────────────────────────
        # Generate PKCE code verifier + challenge explicitly so we can store
        # the verifier in the session and pass it during token exchange.
        # This prevents "Missing code verifier" errors across all library versions.
        code_verifier = _secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )

        flow = Flow.from_client_config(
            client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
        session["oauth_state"] = state
        session["code_verifier"] = code_verifier
        return redirect(auth_url)

    @app.route("/callback")
    def callback():
        # In skip-OAuth mode /callback is never reached via the normal flow,
        # but guard against direct access without exposing internal config.
        if SKIP_OAUTH:
            flash("Sign-in is in local mode. Redirecting you now.")
            return redirect(url_for("login"))

        # ── Manual CSRF state check ───────────────────────────────────────
        # We validate state ourselves and create the Flow WITHOUT state= so
        # oauthlib does not attempt its own (stricter) internal comparison,
        # which can raise mismatching_state in some library versions.
        stored_state = session.pop("oauth_state", None)
        code_verifier = session.pop("code_verifier", None)
        received_state = request.args.get("state")

        if not stored_state or stored_state != received_state:
            flash("Session expired or invalid request. Please sign in again.")
            return redirect(url_for("index"))

        flow = Flow.from_client_config(
            client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI
        )
        try:
            flow.fetch_token(
                authorization_response=request.url,
                code_verifier=code_verifier,
            )
        except Exception as exc:
            flash(f"Authentication failed: {exc}")
            return redirect(url_for("index"))

        credentials = flow.credentials
        id_info = id_token_module.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        session["name"] = id_info.get("name", "Unknown")
        session["email"] = id_info.get("email", "Unknown")
        session["picture"] = id_info.get("picture", "")
        return redirect(url_for("profile"))

    @app.route("/profile")
    def profile():
        if "email" not in session:
            flash("Please sign in first.")
            return redirect(url_for("index"))

        name = session["name"]
        email = session["email"]
        picture = session.get("picture", "")
        local_mode = session.get("skip_oauth", False)

        # Mask APP_SECRET for display (first 2 chars visible, rest hidden)
        raw_secret = app_secret
        masked_secret = raw_secret[:2] + "*" * max(0, len(raw_secret) - 2)

        # Write result file
        now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        result_file = OUTPUT_DIR / "result.txt"
        oauth_status = "skipped (local mode)" if local_mode else "authenticated"
        result_content = (
            f"Run timestamp : {now}\n"
            f"APP_SECRET    : {masked_secret}\n"
            f"OAuth         : {oauth_status}\n"
            f"User name     : {name}\n"
            f"User email    : {email}\n"
            f"Status        : OK\n"
        )
        result_file.write_text(result_content)

        return render_template(
            "profile.html",
            name=name,
            email=email,
            picture=picture,
            masked_secret=masked_secret,
            result_content=result_content,
            local_mode=local_mode,
        )

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    flask_app = create_app()
    flask_app.run(debug=True, port=PORT)
