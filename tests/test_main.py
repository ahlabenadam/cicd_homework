"""
Unit tests for app/main.py
"""

import pathlib
import sys

# Allow importing from the repo root
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.main import run


def test_run_creates_result_file(tmp_path):
    """run() should create output/result.txt in the given output directory."""
    run(output_dir=str(tmp_path))
    result = tmp_path / "result.txt"
    assert result.exists(), "result.txt was not created"


def test_result_file_contains_ok(tmp_path):
    """result.txt should report Status: OK."""
    run(output_dir=str(tmp_path))
    content = (tmp_path / "result.txt").read_text()
    assert "Status        : OK" in content


def test_run_with_secret(tmp_path, monkeypatch):
    """run() should log a masked secret when APP_SECRET is set."""
    monkeypatch.setenv("APP_SECRET", "supersecret")
    run(output_dir=str(tmp_path))
    content = (tmp_path / "result.txt").read_text()
    assert "Secret present: yes" in content


def test_run_without_secret(tmp_path, monkeypatch):
    """run() should note that secret is absent when APP_SECRET is not set."""
    monkeypatch.delenv("APP_SECRET", raising=False)
    run(output_dir=str(tmp_path))
    content = (tmp_path / "result.txt").read_text()
    assert "Secret present: no" in content
