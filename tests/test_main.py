"""
Unit tests for app/main.py
"""

import json
import pathlib
import sys
import time
from unittest.mock import patch

import pytest

# Allow importing from the repo root
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.main import _load_cached_token, _save_token, run


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_token() -> dict:
    return {
        "access_token": "ya29.fake-access-token",
        "expires_in": 3600,
        "stored_at": time.time(),
    }


def _fake_profile() -> dict:
    return {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "sub": "123456789",
    }


# ── APP_SECRET enforcement tests ──────────────────────────────────────────────

def test_missing_app_secret_raises_error(tmp_path, monkeypatch):
    """run() must raise EnvironmentError when APP_SECRET is not set."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("APP_SECRET", raising=False)
    with pytest.raises(EnvironmentError, match="APP_SECRET is required"):
        run(output_dir=str(tmp_path))


def test_missing_app_secret_error_mentions_env_file(tmp_path, monkeypatch):
    """The EnvironmentError message should guide the user to the .env file."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("APP_SECRET", raising=False)
    with pytest.raises(EnvironmentError, match=r"\.env"):
        run(output_dir=str(tmp_path))


# ── Stage 1 tests (APP_SECRET now required) ───────────────────────────────────

def test_run_creates_result_file(tmp_path, monkeypatch):
    """run() should create output/result.txt in the given output directory."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("APP_SECRET", "test-secret")
    run(output_dir=str(tmp_path))
    assert (tmp_path / "result.txt").exists()


def test_result_file_contains_ok(tmp_path, monkeypatch):
    """result.txt should report Status: OK."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("APP_SECRET", "test-secret")
    run(output_dir=str(tmp_path))
    content = (tmp_path / "result.txt").read_text()
    assert "Status        : OK" in content


def test_result_file_secret_present(tmp_path, monkeypatch):
    """result.txt should show 'Secret present: yes' when APP_SECRET is set."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("APP_SECRET", "supersecret")
    run(output_dir=str(tmp_path))
    content = (tmp_path / "result.txt").read_text()
    assert "Secret present: yes" in content


# ── OAuth CI-skip tests ───────────────────────────────────────────────────────

def test_ci_skip_oauth(tmp_path, monkeypatch):
    """When CI=true, run() must skip OAuth and write the skip notice."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("APP_SECRET", "test-secret")
    run(output_dir=str(tmp_path))
    content = (tmp_path / "result.txt").read_text()
    assert "OAuth         : skipped (CI environment)" in content


def test_ci_skip_does_not_call_google(tmp_path, monkeypatch):
    """When CI=true, no HTTP calls to Google should be made."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("APP_SECRET", "test-secret")
    with patch("app.main.requests.post") as mock_post, \
         patch("app.main.requests.get") as mock_get:
        run(output_dir=str(tmp_path))
        mock_post.assert_not_called()
        mock_get.assert_not_called()


# ── OAuth authenticated path tests ───────────────────────────────────────────

def test_authenticated_run_writes_profile(tmp_path, monkeypatch):
    """When authenticated (mocked), result.txt should contain user name and email."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("APP_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")

    with patch("app.main.authenticate", return_value=_fake_token()), \
         patch("app.main.fetch_user_profile", return_value=_fake_profile()):
        run(output_dir=str(tmp_path))

    content = (tmp_path / "result.txt").read_text()
    assert "OAuth         : authenticated" in content
    assert "User name     : Ada Lovelace" in content
    assert "User email    : ada@example.com" in content
    assert "Status        : OK" in content
    assert "Secret present: yes" in content


# ── Token cache tests ─────────────────────────────────────────────────────────

def test_save_and_load_valid_token(tmp_path, monkeypatch):
    """A freshly saved token should be loaded back successfully."""
    monkeypatch.chdir(tmp_path)
    token = {"access_token": "abc123", "expires_in": 3600}
    _save_token(token)
    loaded = _load_cached_token()
    assert loaded is not None
    assert loaded["access_token"] == "abc123"


def test_expired_token_returns_none(tmp_path, monkeypatch):
    """An expired cached token should not be returned."""
    monkeypatch.chdir(tmp_path)
    token = {
        "access_token": "expired",
        "expires_in": 1,
        "stored_at": time.time() - 3600,  # stored 1 hour ago
    }
    (tmp_path / ".token_cache.json").write_text(json.dumps(token))
    assert _load_cached_token() is None


def test_missing_cache_returns_none(tmp_path, monkeypatch):
    """When no cache file exists, _load_cached_token should return None."""
    monkeypatch.chdir(tmp_path)
    assert _load_cached_token() is None
