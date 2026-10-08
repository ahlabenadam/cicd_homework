.PHONY: install uninstall test test-one test-list run run-oauth setup reauth clean help

# ── Base ──────────────────────────────────────────────────────────────────────

# Install dependencies (required by most targets).
# Tries --break-system-packages first (needed on Homebrew Python / macOS),
# falls back to plain install (works in virtualenvs and CI runners).
install:
	@python3 -m pip install -q --break-system-packages -r requirements.txt 2>/dev/null || \
	python3 -m pip install -q -r requirements.txt

# Uninstall all packages listed in requirements.txt
uninstall:
	@python3 -m pip uninstall -y -r requirements.txt 2>/dev/null || true

# ── Testing ───────────────────────────────────────────────────────────────────

# Run all unit tests locally
test: install
	python3 -m pytest tests/ -v

# List all test names without running them (names usable with K= option)
test-list: install
	@python3 -m pytest tests/ --collect-only -q 2>/dev/null | grep "::" | sed 's/.*:://'

# Run a single test by name (usage: make test-one K=test_callback_passes_code_verifier)
test-one: install
	@if [ -z "$(K)" ]; then echo "ERROR: K is required. Usage: make test-one K=test_name"; exit 1; fi
	@python3 -m pytest tests/ -v -k "$(K)"; code=$$?; \
	if [ $$code -eq 5 ]; then \
		echo ""; \
		echo "ERROR: No test found matching K=\"$(K)\". Run 'make test-list' to see available names."; \
		exit 1; \
	fi; exit $$code

# ── App ───────────────────────────────────────────────────────────────────────

# Start the app without Google OAuth (default — no credentials needed).
# ⚠ Authentication is disabled — local dev only.
# Customize the mock identity with MOCK_NAME, MOCK_EMAIL, MOCK_PICTURE env vars.
run: install
	SKIP_OAUTH=true python3 app/main.py

# Start the app with real Google OAuth (advanced — requires GOOGLE_CLIENT_SECRET in .env).
run-oauth: install
	python3 app/main.py

# Full CI-equivalent: install → test → package artifact
setup: install
	bash scripts/setup.sh

# ── Maintenance ───────────────────────────────────────────────────────────────

# Force Google re-authentication (deletes cached token)
reauth:
	rm -f .token_cache.json

# Remove generated directories
clean:
	rm -rf output/ logs/ dist/ __pycache__/ app/__pycache__/ tests/__pycache__/

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install    Install Python dependencies (python3 -m pip install -r requirements.txt)"
	@echo "  uninstall  Uninstall all packages listed in requirements.txt"
	@echo "  test       Run all unit tests        [depends on: install]"
	@echo "  test-list  List all test names        [depends on: install]"
	@echo "  test-one   Run one test by name       [depends on: install]  e.g. make test-one K=test_login"
	@echo "  run        Start app (no OAuth, no Google credentials needed) [depends on: install]"
	@echo "  run-oauth  Start app with real Google sign-in (advanced)      [depends on: install]"
	@echo "  setup      Full CI pipeline           [depends on: install]"
	@echo "  reauth     Delete .token_cache.json (force Google sign-in)"
	@echo "  clean      Remove output/, logs/, dist/, __pycache__/"
	@echo "  help       Show this message"
	@echo ""
