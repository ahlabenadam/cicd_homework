#!/usr/bin/env python3
"""
CI/CD Homework App — Flask web app.

Users are signed in automatically using a configurable mock identity.
No external accounts or credentials are required.

Run locally:
    python app/main.py          # or: make run
    Open http://localhost:5000 in your browser and click "Enter app".

Required environment variables (set in .env):
    APP_SECRET  — Flask session signing key (any long random string)

Optional — customize the identity shown on the profile page:
    MOCK_NAME    — Display name  (default: "Local User")
    MOCK_EMAIL   — Email address (default: "local@localhost")
    MOCK_PICTURE — Avatar URL   (default: "" → no avatar shown)

Optional:
    PORT         — Port to listen on (default: 5000)
"""

import datetime
import logging
import os
import pathlib

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)

# ── Load .env from the repo root ──────────────────────────────────────────────
_REPO_ROOT = pathlib.Path(__file__).parent.parent
load_dotenv(_REPO_ROOT / ".env")

# ── Constants ─────────────────────────────────────────────────────────────────
try:
    PORT = int(os.environ.get("PORT", "5000"))
except ValueError:
    raise EnvironmentError(
        f"PORT must be an integer (e.g. PORT=8080), got: {os.environ['PORT']!r}"
    )
OUTPUT_DIR = _REPO_ROOT / "output"

# Accepted URL schemes for MOCK_PICTURE — anything else is silently cleared.
_SAFE_PICTURE_SCHEMES = ("http://", "https://", "//")


_log = logging.getLogger(__name__)


def create_app() -> Flask:
    """Application factory — validates APP_SECRET and wires up routes."""
    app_secret = os.environ.get("APP_SECRET", "")

    # Detect missing .env so first-time users get an actionable hint.
    _env_file = _REPO_ROOT / ".env"
    _env_hint = (
        "\n\n  *** Looks like you haven't created a .env file yet. ***\n"
        "  Run:  cp .env.example .env\n"
        "  Then edit .env and set APP_SECRET to a long random string.\n"
        if not _env_file.exists() else ""
    )

    if not app_secret:
        raise EnvironmentError(
            "APP_SECRET is required but not set."
            f"{_env_hint}"
            "\n  Local runs : add APP_SECRET=<any-long-string> to your .env file."
            "\n  CI         : add APP_SECRET under Settings → Secrets and variables → Actions."
        )

    app = Flask(__name__, template_folder="templates")
    app.secret_key = app_secret  # signs session cookies — keep APP_SECRET private!

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        if "email" in session:
            return redirect(url_for("profile"))
        return render_template("index.html")

    @app.route("/login")
    def login():
        """Sign in with a mock identity from env vars."""
        session["name"] = os.environ.get("MOCK_NAME", "Local User")
        session["email"] = os.environ.get("MOCK_EMAIL", "local@localhost")
        # Sanitize picture URL — only allow safe schemes to prevent javascript: / data: URIs
        raw_picture = os.environ.get("MOCK_PICTURE", "")
        session["picture"] = raw_picture if any(raw_picture.startswith(s) for s in _SAFE_PICTURE_SCHEMES) else ""
        return redirect(url_for("profile"))

    @app.route("/profile")
    def profile():
        if "email" not in session:
            flash("Please sign in first.")
            return redirect(url_for("index"))

        name = session["name"]
        email = session["email"]
        picture = session.get("picture", "")

        # Mask APP_SECRET for display (first 2 chars visible, rest hidden)
        raw_secret = app_secret
        masked_secret = raw_secret[:2] + "*" * max(0, len(raw_secret) - 2)

        # Write result file
        now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        result_file = OUTPUT_DIR / "result.txt"
        result_content = (
            f"Run timestamp : {now}\n"
            f"APP_SECRET    : {masked_secret}\n"
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
        )

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    flask_app = create_app()
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    flask_app.run(debug=debug, port=PORT)
