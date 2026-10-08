"""
Tests for the Flask web app (app/main.py) — no-OAuth mode.

All tests use Flask's built-in test client — no browser, no Google account needed.
The app signs users in automatically using a configurable mock identity (MOCK_NAME,
MOCK_EMAIL, MOCK_PICTURE env vars), so tests simply call GET /login to set up a session.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import app.main as main_module
from app.main import create_app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def env_vars(monkeypatch, tmp_path):
    """Set required environment variables and redirect output to a temp dir."""
    monkeypatch.setenv("APP_SECRET", "test-app-secret-for-pytest")
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def client(env_vars):
    """Flask test client with TESTING mode enabled."""
    flask_app = create_app()
    flask_app.config["TESTING"] = True
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
    with pytest.raises(EnvironmentError, match="APP_SECRET is required"):
        create_app()


def test_missing_app_secret_error_mentions_env_file(monkeypatch):
    """EnvironmentError for APP_SECRET should mention .env file."""
    monkeypatch.delenv("APP_SECRET", raising=False)
    with pytest.raises(EnvironmentError, match=r"\.env"):
        create_app()


def test_missing_app_secret_suggests_env_example_when_no_env_file(monkeypatch, tmp_path):
    """When .env is missing, error should suggest 'cp .env.example .env'."""
    monkeypatch.delenv("APP_SECRET", raising=False)
    # Point _REPO_ROOT to a temp dir that has no .env file
    monkeypatch.setattr(main_module, "_REPO_ROOT", tmp_path)
    with pytest.raises(EnvironmentError, match=r"cp .env\.example \.env"):
        create_app()


def test_missing_app_secret_no_env_example_hint_when_env_exists(monkeypatch, tmp_path):
    """When .env exists but APP_SECRET is unset, the 'cp' hint should NOT appear."""
    monkeypatch.delenv("APP_SECRET", raising=False)
    # Create an empty .env so the file exists
    (tmp_path / ".env").write_text("")
    monkeypatch.setattr(main_module, "_REPO_ROOT", tmp_path)
    with pytest.raises(EnvironmentError) as exc_info:
        create_app()
    assert "cp .env.example" not in str(exc_info.value)


# ── Home page (GET /) ─────────────────────────────────────────────────────────

def test_home_returns_200(client):
    """GET / returns HTTP 200."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_home_shows_enter_app_link(client):
    """GET / contains a link to /login."""
    resp = client.get("/")
    assert b"/login" in resp.data


def test_home_redirects_to_profile_when_logged_in(logged_in_client):
    """GET / redirects to /profile when user is already in session."""
    resp = logged_in_client.get("/")
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


# ── Login (GET /login) ────────────────────────────────────────────────────────

def test_login_redirects_to_profile(client):
    """GET /login sets session and redirects directly to /profile (no OAuth)."""
    resp = client.get("/login")
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_login_does_not_redirect_to_google(client):
    """GET /login must never redirect to accounts.google.com."""
    resp = client.get("/login")
    assert "accounts.google.com" not in resp.headers.get("Location", "")


def test_login_stores_mock_identity_in_session(client, monkeypatch):
    """GET /login stores MOCK_NAME and MOCK_EMAIL in the session."""
    monkeypatch.setenv("MOCK_NAME", "Test Robot")
    monkeypatch.setenv("MOCK_EMAIL", "robot@localhost")
    client.get("/login")
    with client.session_transaction() as sess:
        assert sess.get("name") == "Test Robot"
        assert sess.get("email") == "robot@localhost"


def test_login_uses_defaults_when_mock_vars_absent(client, monkeypatch):
    """GET /login defaults to 'Local User' / 'local@localhost' when MOCK_* not set."""
    monkeypatch.delenv("MOCK_NAME", raising=False)
    monkeypatch.delenv("MOCK_EMAIL", raising=False)
    client.get("/login")
    with client.session_transaction() as sess:
        assert sess.get("name") == "Local User"
        assert sess.get("email") == "local@localhost"


# ── Profile (GET /profile) ────────────────────────────────────────────────────

def test_profile_requires_login(client):
    """GET /profile without session redirects to the index page (/)."""
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].rstrip("/").endswith("")  # redirects to root
    # More specific: location must be exactly "/" or "http://localhost/"
    loc = resp.headers["Location"]
    assert loc == "/" or loc.endswith("://localhost/")


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


def test_profile_hides_avatar_when_picture_is_empty(client):
    """GET /profile must not render a broken <img> when MOCK_PICTURE is empty."""
    client.get("/login")  # MOCK_PICTURE defaults to ""
    resp = client.get("/profile")
    assert b'<img' not in resp.data


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
    assert "APP_SECRET" in content


def test_profile_shows_masked_secret(logged_in_client):
    """GET /profile page should display the masked APP_SECRET (te**...) not the raw value."""
    resp = logged_in_client.get("/profile")
    # APP_SECRET fixture value is "test-app-secret-for-pytest" (26 chars)
    # masked = "te" + "*" * 24  →  "te************************"
    assert b"APP_SECRET" in resp.data
    assert b"te************************" in resp.data  # exactly 24 asterisks
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
    """GET /logout redirects to the index page (/) not to /profile or /logout."""
    resp = logged_in_client.get("/logout")
    assert resp.status_code == 302
    loc = resp.headers["Location"]
    assert loc == "/" or loc.endswith("://localhost/")


def test_after_logout_profile_requires_login(logged_in_client):
    """After logout, GET /profile should redirect to /."""
    logged_in_client.get("/logout")
    resp = logged_in_client.get("/profile")
    assert resp.status_code == 302


# ── Port ──────────────────────────────────────────────────────────────────────

def test_port_constant_is_integer():
    """PORT must be a positive integer."""
    assert isinstance(main_module.PORT, int)
    assert main_module.PORT > 0


# ── Flash messages ────────────────────────────────────────────────────────────

def test_profile_flashes_message_when_not_logged_in(client):
    """Unauthenticated /profile visit should flash 'Please sign in first.' on the home page."""
    client.get("/profile")  # redirects to /, flash is set
    resp = client.get("/")  # follow redirect to see flash
    assert b"Please sign in first" in resp.data


# ── Re-login overwrites session ────────────────────────────────────────────────

def test_login_overwrites_existing_session(client, monkeypatch):
    """Calling /login a second time replaces the previous session identity."""
    monkeypatch.setenv("MOCK_NAME", "First User")
    client.get("/login")
    monkeypatch.setenv("MOCK_NAME", "Second User")
    client.get("/login")
    with client.session_transaction() as sess:
        assert sess.get("name") == "Second User"


# ── Removed routes return 404 ──────────────────────────────────────────────────

def test_callback_route_does_not_exist(client):
    """GET /callback must return 404 — OAuth callback route was removed."""
    resp = client.get("/callback?code=fake&state=fake")
    assert resp.status_code == 404


# ── Picture URL sanitization ───────────────────────────────────────────────────

def test_login_blocks_javascript_picture_url(client, monkeypatch):
    """MOCK_PICTURE with a javascript: URI must be cleared before storing in session."""
    monkeypatch.setenv("MOCK_PICTURE", "javascript:alert(1)")
    client.get("/login")
    with client.session_transaction() as sess:
        assert sess.get("picture") == ""


def test_login_blocks_data_uri_picture(client, monkeypatch):
    """MOCK_PICTURE with a data: URI must be cleared before storing in session."""
    monkeypatch.setenv("MOCK_PICTURE", "data:text/html,<h1>pwned</h1>")
    client.get("/login")
    with client.session_transaction() as sess:
        assert sess.get("picture") == ""


def test_login_allows_https_picture_url(client, monkeypatch):
    """MOCK_PICTURE with an https:// URL must be kept."""
    monkeypatch.setenv("MOCK_PICTURE", "https://example.com/avatar.jpg")
    client.get("/login")
    with client.session_transaction() as sess:
        assert sess.get("picture") == "https://example.com/avatar.jpg"
