#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# setup.sh — CI/CD Homework setup, test, and package script
#
# Steps:
#   1. Install Python dependencies
#   2. Run the app once (smoke test)
#   3. Run pytest and capture a log
#   4. Package the app into a tarball artifact
#
# Usage: bash scripts/setup.sh
# -----------------------------------------------------------------------------

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

LOG_DIR="${REPO_ROOT}/logs"
DIST_DIR="${REPO_ROOT}/dist"
OUTPUT_DIR="${REPO_ROOT}/output"

mkdir -p "${LOG_DIR}" "${DIST_DIR}" "${OUTPUT_DIR}"

# ── 1. Install dependencies ──────────────────────────────────────────────────
echo "==> Installing dependencies..."
pip install --quiet -r requirements.txt

# ── 2. Smoke-test the app ────────────────────────────────────────────────────
echo "==> Running app smoke test..."
python app/main.py

# ── 3. Run pytest and capture log ───────────────────────────────────────────
echo "==> Running tests..."
set +e
pytest tests/ -v 2>&1 | tee "${LOG_DIR}/test.log"
TEST_EXIT=${PIPESTATUS[0]}
set -e

if [[ ${TEST_EXIT} -ne 0 ]]; then
    echo "ERROR: Tests failed (exit code ${TEST_EXIT}). Check ${LOG_DIR}/test.log for details."
    exit ${TEST_EXIT}
fi

echo "==> All tests passed."

# ── 4. Package the app ──────────────────────────────────────────────────────
echo "==> Packaging artifact..."
tar -czf "${DIST_DIR}/app.tar.gz" app/
echo "==> Artifact written to ${DIST_DIR}/app.tar.gz"

echo "==> Setup complete."
