"""
Tests for the Flask web app (app/main.py).

All tests use Flask's built-in test client — no browser or real Google OAuth needed.
The Google OAuth callback is tested in two ways:
  1. By injecting a pre-populated session (simulates post-login state for profile/logout tests).
  2. By mocking Flow.fetch_token and id_token_module.verify_oauth2_token so the full
     /callback route is exercised, including state validation and session writing.
     This catches bugs like CSRF state mismatches and token exchange failures.

SKIP_OAUTH mode:
  SKIP_OAUTH is evaluated once at module import and stored as a boolean constant.
  Tests that need to toggle it must patch the module attribute directly:
      monkeypatch.setattr(main_module, "SKIP_OAUTH", True)
  Do NOT use monkeypatch.setenv("SKIP_OAUTH", ...) — the env var is already baked in
  and changing it after import has no effect on the constant.
"""

import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import app.main as main_module
from app.main import create_app, PORT, REDIRECT_URI

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def env_vars(monkeypatch, tmp_path):
    """Set required environment variables and point output to a temp dir."""
    monkeypatch.setenv("APP_SECRET", "test-app-secret-for-pytest")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def client(env_vars):
    """Flask test client with TESTING mode enabled."""
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    # Allow OAuth over http in tests
    flask_app.config["SERVER_NAME"] = "localhost"
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def logged_in_client(client):
    """Test client with a pre-populated session (simulates post-login state)."""
    with client.session_transaction() as sess:
        sess["name"] = "Ada Lovelace"
        sess["email"] = "ada@example.com"
        sess["picture"] = "https://example.com/avatar.jpg"
    return client


# ── App creation / secret enforcement ────────────────────────────────────────

def test_missing_app_secret_raises(monkeypatch):
    """create_app() must raise EnvironmentError when APP_SECRET is absent."""
    monkeypatch.delenv("APP_SECRET", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")
    monkeypatch.setattr(main_module, "SKIP_OAUTH", False)  # ensure OAuth mode
    with pytest.raises(EnvironmentError, match="APP_SECRET is required"):
        create_app()


def test_missing_client_secret_raises(monkeypatch):
    """create_app() must raise EnvironmentError when GOOGLE_CLIENT_SECRET is absent (OAuth mode)."""
    monkeypatch.setenv("APP_SECRET", "test-secret")
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(main_module, "SKIP_OAUTH", False)  # ensure OAuth mode
    with pytest.raises(EnvironmentError, match="GOOGLE_CLIENT_SECRET is required"):
        create_app()


def test_missing_app_secret_error_mentions_env_file(monkeypatch):
    """EnvironmentError for APP_SECRET should mention .env file."""
    monkeypatch.delenv("APP_SECRET", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")
    monkeypatch.setattr(main_module, "SKIP_OAUTH", False)
    with pytest.raises(EnvironmentError, match=r"\.env"):
        create_app()


def test_missing_client_secret_error_mentions_google_console(monkeypatch):
    """EnvironmentError for GOOGLE_CLIENT_SECRET should mention Google Console."""
    monkeypatch.setenv("APP_SECRET", "test-secret")
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(main_module, "SKIP_OAUTH", False)
    with pytest.raises(EnvironmentError, match="console.cloud.google.com"):
        create_app()


# ── Home page (GET /) ─────────────────────────────────────────────────────────

def test_home_returns_200(client):
    """GET / returns HTTP 200."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_home_shows_sign_in_link(client):
    """GET / contains a link to /login."""
    resp = client.get("/")
    assert b"/login" in resp.data


def test_home_redirects_to_profile_when_logged_in(logged_in_client):
    """GET / redirects to /profile when user is already in session."""
    resp = logged_in_client.get("/")
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


# ── Login (GET /login) ────────────────────────────────────────────────────────

def test_login_redirects_to_google(client):
    """GET /login redirects to accounts.google.com."""
    resp = client.get("/login")
    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers["Location"]


def test_login_stores_oauth_state_in_session(client):
    """GET /login stores oauth_state in the session."""
    client.get("/login")
    with client.session_transaction() as sess:
        assert "oauth_state" in sess


# ── Profile (GET /profile) ────────────────────────────────────────────────────

def test_profile_requires_login(client):
    """GET /profile without session redirects to /."""
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_profile_shows_name(logged_in_client):
    """GET /profile displays the user's name."""
    resp = logged_in_client.get("/profile")
    assert resp.status_code == 200
    assert b"Ada Lovelace" in resp.data


def test_profile_shows_email(logged_in_client):
    """GET /profile displays the user's email."""
    resp = logged_in_client.get("/profile")
    assert b"ada@example.com" in resp.data


def test_profile_shows_avatar(logged_in_client):
    """GET /profile includes the avatar image URL."""
    resp = logged_in_client.get("/profile")
    assert b"https://example.com/avatar.jpg" in resp.data


def test_profile_shows_sign_out_link(logged_in_client):
    """GET /profile contains a link to /logout."""
    resp = logged_in_client.get("/profile")
    assert b"/logout" in resp.data


def test_profile_writes_result_file(logged_in_client, env_vars):
    """GET /profile writes output/result.txt with name, email, APP_SECRET, and OK status."""
    logged_in_client.get("/profile")
    result_file = env_vars / "result.txt"
    assert result_file.exists(), "result.txt was not created"
    content = result_file.read_text()
    assert "User name     : Ada Lovelace" in content
    assert "User email    : ada@example.com" in content
    assert "Status        : OK" in content
    assert "OAuth         : authenticated" in content
    assert "APP_SECRET" in content


def test_profile_shows_masked_secret(logged_in_client):
    """GET /profile page should display the masked APP_SECRET (te**...) not the raw value."""
    resp = logged_in_client.get("/profile")
    # APP_SECRET fixture value is "test-app-secret-for-pytest"
    # masked = "te" + "*" * 24
    assert b"APP_SECRET" in resp.data
    assert b"te**********************" in resp.data
    # Raw value must NOT appear in the response
    assert b"test-app-secret-for-pytest" not in resp.data


def test_profile_result_file_has_timestamp(logged_in_client, env_vars):
    """result.txt should contain a UTC timestamp."""
    logged_in_client.get("/profile")
    content = (env_vars / "result.txt").read_text()
    assert "Run timestamp" in content
    assert "Z" in content  # UTC marker


# ── Logout (GET /logout) ──────────────────────────────────────────────────────

def test_logout_clears_session(logged_in_client):
    """GET /logout clears the session."""
    logged_in_client.get("/logout")
    with logged_in_client.session_transaction() as sess:
        assert "email" not in sess
        assert "name" not in sess


def test_logout_redirects_to_home(logged_in_client):
    """GET /logout redirects to /."""
    resp = logged_in_client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_after_logout_profile_requires_login(logged_in_client):
    """After logout, GET /profile should redirect to /."""
    logged_in_client.get("/logout")
    resp = logged_in_client.get("/profile")
    assert resp.status_code == 302


# ── Callback tests (GET /callback) ────────────────────────────────────────────

def test_callback_without_state_redirects_to_home(client):
    """GET /callback with no oauth_state in session redirects to / with flash."""
    resp = client.get("/callback?code=fake&state=bad")
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_callback_with_mismatching_state_redirects_to_home(client):
    """
    Regression: state in session does not match state in URL.
    Previously caused 'mismatching_state' crash inside oauthlib.
    Now we validate manually and redirect gracefully.
    """
    with client.session_transaction() as sess:
        sess["oauth_state"] = "correct-state"
        sess["code_verifier"] = "some-verifier"

    resp = client.get("/callback?code=fake&state=wrong-state")
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_callback_with_matching_state_redirects_to_profile(client):
    """
    Full callback route: state matches, token exchange and id_token verification
    are mocked. Route should store user in session and redirect to /profile.
    This exercises Flow.fetch_token() — the code path that caused both the
    mismatching_state bug and the Missing code verifier bug.
    """
    with client.session_transaction() as sess:
        sess["oauth_state"] = "valid-state-xyz"
        sess["code_verifier"] = "test-code-verifier"

    fake_id_info = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "picture": "https://example.com/avatar.jpg",
    }
    mock_flow = MagicMock()
    mock_flow.credentials.id_token = "fake-id-token"

    with patch("app.main.Flow") as MockFlow, \
         patch("app.main.id_token_module.verify_oauth2_token", return_value=fake_id_info), \
         patch("app.main.google_requests.Request"):
        MockFlow.from_client_config.return_value = mock_flow
        resp = client.get("/callback?code=real-code&state=valid-state-xyz")

    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_callback_passes_code_verifier_to_fetch_token(client):
    """
    Regression: PKCE code_verifier must be passed to fetch_token.
    Without it Google returns 'Missing code verifier'.
    """
    with client.session_transaction() as sess:
        sess["oauth_state"] = "valid-state-xyz"
        sess["code_verifier"] = "my-pkce-verifier"

    mock_flow = MagicMock()
    mock_flow.credentials.id_token = "fake-id-token"
    fake_id_info = {"name": "T", "email": "t@x.com", "picture": ""}

    with patch("app.main.Flow") as MockFlow, \
         patch("app.main.id_token_module.verify_oauth2_token", return_value=fake_id_info), \
         patch("app.main.google_requests.Request"):
        MockFlow.from_client_config.return_value = mock_flow
        client.get("/callback?code=real-code&state=valid-state-xyz")

    # fetch_token must have been called with the code_verifier kwarg
    mock_flow.fetch_token.assert_called_once()
    _, kwargs = mock_flow.fetch_token.call_args
    assert kwargs.get("code_verifier") == "my-pkce-verifier"


def test_callback_sets_session_from_google_profile(client):
    """After successful callback, session should contain name, email, picture."""
    with client.session_transaction() as sess:
        sess["oauth_state"] = "valid-state-xyz"
        sess["code_verifier"] = "test-code-verifier"

    fake_id_info = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "picture": "https://example.com/avatar.jpg",
    }
    mock_flow = MagicMock()
    mock_flow.credentials.id_token = "fake-id-token"

    with patch("app.main.Flow") as MockFlow, \
         patch("app.main.id_token_module.verify_oauth2_token", return_value=fake_id_info), \
         patch("app.main.google_requests.Request"):
        MockFlow.from_client_config.return_value = mock_flow
        client.get("/callback?code=real-code&state=valid-state-xyz")

    with client.session_transaction() as sess:
        assert sess.get("name") == "Ada Lovelace"
        assert sess.get("email") == "ada@example.com"
        assert sess.get("picture") == "https://example.com/avatar.jpg"


def test_callback_token_fetch_error_flashes_and_redirects(client):
    """If flow.fetch_token() raises, the error is flashed and user is sent to /."""
    with client.session_transaction() as sess:
        sess["oauth_state"] = "valid-state-xyz"
        sess["code_verifier"] = "test-code-verifier"

    mock_flow = MagicMock()
    mock_flow.fetch_token.side_effect = Exception("token exchange failed")

    with patch("app.main.Flow") as MockFlow:
        MockFlow.from_client_config.return_value = mock_flow
        resp = client.get("/callback?code=bad-code&state=valid-state-xyz")

    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


# ── Port / REDIRECT_URI consistency ───────────────────────────────────────────

def test_redirect_uri_derived_from_port_constant():
    """
    Regression: REDIRECT_URI must be derived from PORT, not hardcoded separately.
    If someone changes PORT (or the PORT env var) the redirect URI must update too.
    """
    assert f"localhost:{PORT}" in REDIRECT_URI, (
        f"REDIRECT_URI ({REDIRECT_URI!r}) does not use PORT constant ({PORT}). "
        "They have drifted — change PORT or REDIRECT_URI to stay in sync."
    )
    assert REDIRECT_URI.endswith("/callback")


def test_login_sends_correct_redirect_uri_to_google(client):
    """
    /login must pass REDIRECT_URI (derived from PORT) to the Google OAuth flow.
    Catches the bug where port in run() and port in REDIRECT_URI were different.
    """
    with patch("app.main.Flow") as MockFlow:
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?fake=1", "state123")
        MockFlow.from_client_config.return_value = mock_flow
        client.get("/login")

    _, kwargs = MockFlow.from_client_config.call_args
    assert kwargs.get("redirect_uri") == REDIRECT_URI, (
        f"Flow was created with redirect_uri={kwargs.get('redirect_uri')!r} "
        f"but REDIRECT_URI is {REDIRECT_URI!r}. Port mismatch!"
    )


def test_callback_consumes_state_and_verifier_from_session(client):
    """oauth_state and code_verifier must be removed from session after use."""
    with client.session_transaction() as sess:
        sess["oauth_state"] = "valid-state-xyz"
        sess["code_verifier"] = "test-code-verifier"

    fake_id_info = {"name": "Test", "email": "test@example.com", "picture": ""}
    mock_flow = MagicMock()
    mock_flow.credentials.id_token = "fake-id-token"

    with patch("app.main.Flow") as MockFlow, \
         patch("app.main.id_token_module.verify_oauth2_token", return_value=fake_id_info), \
         patch("app.main.google_requests.Request"):
        MockFlow.from_client_config.return_value = mock_flow
        client.get("/callback?code=real-code&state=valid-state-xyz")

    with client.session_transaction() as sess:
        assert "oauth_state" not in sess
        assert "code_verifier" not in sess


# ── SKIP_OAUTH mode tests ──────────────────────────────────────────────────────
# IMPORTANT: SKIP_OAUTH is a module-level constant baked in at import time.
# Tests MUST patch main_module.SKIP_OAUTH directly — monkeypatch.setenv has no effect.

@pytest.fixture()
def env_vars_skip(monkeypatch, tmp_path):
    """Env fixture for SKIP_OAUTH mode — no GOOGLE_CLIENT_SECRET required."""
    monkeypatch.setenv("APP_SECRET", "test-app-secret-for-pytest")
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(main_module, "SKIP_OAUTH", True)
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def skip_client(env_vars_skip):
    """Flask test client with SKIP_OAUTH=True and no GOOGLE_CLIENT_SECRET."""
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SERVER_NAME"] = "localhost"
    with flask_app.test_client() as c:
        yield c


def test_skip_oauth_create_app_succeeds_without_client_secret(monkeypatch):
    """
    When SKIP_OAUTH=True, create_app() must succeed even if GOOGLE_CLIENT_SECRET is absent.
    This is the core value proposition of SKIP_OAUTH mode.
    """
    monkeypatch.setenv("APP_SECRET", "test-secret")
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(main_module, "SKIP_OAUTH", True)
    app = create_app()  # must not raise
    assert app is not None


def test_skip_oauth_login_does_not_redirect_to_google(skip_client):
    """In SKIP_OAUTH mode, GET /login must NOT redirect to accounts.google.com."""
    resp = skip_client.get("/login")
    assert resp.status_code == 302
    assert "accounts.google.com" not in resp.headers.get("Location", "")


def test_skip_oauth_login_redirects_to_profile(skip_client):
    """In SKIP_OAUTH mode, GET /login goes directly to /profile."""
    resp = skip_client.get("/login")
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_skip_oauth_login_stores_mock_identity_in_session(skip_client, monkeypatch):
    """In SKIP_OAUTH mode, /login stores MOCK_NAME and MOCK_EMAIL in the session."""
    monkeypatch.setenv("MOCK_NAME", "Test Robot")
    monkeypatch.setenv("MOCK_EMAIL", "robot@localhost")
    skip_client.get("/login")
    with skip_client.session_transaction() as sess:
        assert sess.get("name") == "Test Robot"
        assert sess.get("email") == "robot@localhost"
        assert sess.get("skip_oauth") is True


def test_skip_oauth_login_uses_defaults_when_mock_vars_absent(skip_client, monkeypatch):
    """In SKIP_OAUTH mode, mock identity defaults to 'Local User' / 'local@localhost'."""
    monkeypatch.delenv("MOCK_NAME", raising=False)
    monkeypatch.delenv("MOCK_EMAIL", raising=False)
    skip_client.get("/login")
    with skip_client.session_transaction() as sess:
        assert sess.get("name") == "Local User"
        assert sess.get("email") == "local@localhost"


def test_skip_oauth_profile_shows_local_mode_badge(skip_client):
    """In SKIP_OAUTH mode, /profile must show the 'Local mode' badge."""
    skip_client.get("/login")  # populates session
    resp = skip_client.get("/profile")
    assert resp.status_code == 200
    assert b"Local mode" in resp.data or b"local mode" in resp.data


def test_skip_oauth_result_file_says_skipped(skip_client, env_vars_skip):
    """In SKIP_OAUTH mode, result.txt must say 'skipped (local mode)', not 'authenticated'."""
    skip_client.get("/login")
    skip_client.get("/profile")
    content = (env_vars_skip / "result.txt").read_text()
    assert "skipped (local mode)" in content
    assert "authenticated" not in content


def test_skip_oauth_callback_redirects_to_login(skip_client):
    """In SKIP_OAUTH mode, GET /callback must redirect to /login, not crash."""
    resp = skip_client.get("/callback?code=fake&state=fake")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_skip_oauth_callback_flash_does_not_expose_env_var_name(skip_client):
    """
    The flash message shown when /callback is hit in SKIP_OAUTH mode must NOT
    expose the internal env var name 'SKIP_OAUTH' to the browser.
    """
    skip_client.get("/callback?code=fake&state=fake")
    # Follow the redirect to / to see flash messages
    resp = skip_client.get("/")
    assert b"SKIP_OAUTH" not in resp.data


def test_skip_oauth_home_page_shows_local_mode_button(skip_client):
    """In SKIP_OAUTH mode, GET / must show a local-mode button, not the Google sign-in button."""
    resp = skip_client.get("/")
    assert resp.status_code == 200
    # Should NOT say "Sign in with Google"
    assert b"Sign in with Google" not in resp.data
    # Should indicate local mode
    assert b"local mode" in resp.data.lower() or b"without sign-in" in resp.data


def test_skip_oauth_logout_clears_skip_oauth_flag(skip_client):
    """After logout in SKIP_OAUTH mode, the skip_oauth session key must be gone."""
    skip_client.get("/login")
    with skip_client.session_transaction() as sess:
        assert "skip_oauth" in sess
    skip_client.get("/logout")
    with skip_client.session_transaction() as sess:
        assert "skip_oauth" not in sess
