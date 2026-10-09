#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# setup.sh — CI/CD Homework setup, test, and package script
#
# Steps:
#   1. Install Python dependencies
#   2. Run pytest (Flask test client — no browser or server required)
#   3. Package the app into a tarball artifact
#
# Usage: bash scripts/setup.sh
# -----------------------------------------------------------------------------

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

LOG_DIR="${REPO_ROOT}/logs"
DIST_DIR="${REPO_ROOT}/dist"

mkdir -p "${LOG_DIR}" "${DIST_DIR}"

# ── 1. Install dependencies ──────────────────────────────────────────────────
echo "==> Installing dependencies..."
python3 -m pip install -q --break-system-packages -r requirements.txt 2>/dev/null || \
python3 -m pip install -q -r requirements.txt

# ── 2. Run pytest and capture log ───────────────────────────────────────────
echo "==> Running tests..."
set +e
python3 -m pytest tests/ -v 2>&1 | tee "${LOG_DIR}/test.log"
TEST_EXIT=${PIPESTATUS[0]}
set -e

if [[ ${TEST_EXIT} -ne 0 ]]; then
    echo "ERROR: Tests failed (exit code ${TEST_EXIT}). Check ${LOG_DIR}/test.log for details."
    exit ${TEST_EXIT}
fi

echo "==> All tests passed."

# ── 3. Package the app ──────────────────────────────────────────────────────
echo "==> Packaging artifact..."
tar -czf "${DIST_DIR}/app.tar.gz" app/ requirements.txt
echo "==> Artifact written to ${DIST_DIR}/app.tar.gz (includes app/ and requirements.txt)"

echo "==> Setup complete."
