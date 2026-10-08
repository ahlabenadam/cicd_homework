# CI/CD Homework

A Python web app with a full GitHub Actions CI/CD pipeline, demonstrating:

- Flask web app with Google OAuth 2.0 (Authorization Code Flow)
- Bash setup/test/package script
- GitHub Actions workflow with secret handling and artifact upload

## Project Structure

```
cicd_homework/
├── app/
│   ├── main.py              # Flask web app
│   └── templates/
│       ├── index.html       # Home page — Sign in with Google
│       └── profile.html     # Profile card shown after login
├── scripts/
│   └── setup.sh             # Bash: install deps, run tests, package
├── tests/
│   └── test_main.py         # pytest tests (Flask test client, no browser needed)
├── .env.example             # Template for required environment variables
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI workflow
└── requirements.txt
```

## Quick Start (Local)

### 1. Prerequisites

- Python 3.12+
- A Google Cloud project with an OAuth 2.0 Web client configured

### 2. Create a Google OAuth Client

1. Go to [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials → OAuth Client ID**
3. Application type: **Web application**
4. Add `http://localhost:5000/callback` to **Authorized redirect URIs**
   (if you override the `PORT` env var, use `http://localhost:<PORT>/callback` instead)
5. Copy the **Client Secret** (the Client ID is already in `app/main.py`)

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env and fill in your GOOGLE_CLIENT_SECRET and APP_SECRET
```

Generate a random `APP_SECRET`:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the app

```bash
python app/main.py          # default: http://localhost:5000
PORT=8080 python app/main.py  # custom port example
```

Open [http://localhost:5000](http://localhost:5000) in your browser and click **Sign in with Google**.
> If you set `PORT`, open `http://localhost:<PORT>` instead — the redirect URI updates automatically.

After sign-in, your profile is shown and `output/result.txt` is written.

### 6. Run tests (no browser needed)

```bash
pytest tests/ -v
```

Tests use Flask's test client and mock sessions — no real Google OAuth required.

### 7. Run the full setup script (install + test + package)

```bash
bash scripts/setup.sh
```

This installs deps, runs pytest (log → `logs/test.log`), and packages `app/` into `dist/app.tar.gz`.

## GitHub Actions CI

The workflow (`.github/workflows/ci.yml`) triggers on:
- Push to `main`, `oauth`, or `web` branches
- Pull requests targeting `main`

Steps:
1. Checkout code
2. Set up Python 3.12
3. **Verify required secrets** (fail fast if `APP_SECRET` or `GOOGLE_CLIENT_SECRET` missing)
4. Run `scripts/setup.sh` (install, test, package)
5. Upload `dist/app.tar.gz` and `logs/test.log` as artifacts
6. Report success or failure

## GitHub Secrets Required

Add these under **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Description |
|--------|-------------|
| `APP_SECRET` | Flask session signing key — any long random string |
| `GOOGLE_CLIENT_SECRET` | From your Google Cloud OAuth client |

> `GOOGLE_CLIENT_ID` is committed directly in `app/main.py` — it is not sensitive.

## Notes on the OAuth Model

- **GOOGLE_CLIENT_ID** identifies the registered app — committed to the repo, safe to share
- **GOOGLE_CLIENT_SECRET** proves you own the app — keep it private
- **APP_SECRET** signs Flask session cookies — keep it private
- End users sign in with *their own* Google account; they need no credentials
- Only the person *running the server* needs `.env` configured
