# CI/CD Homework

A Python web app that lets you **sign in with Google** and shows your profile.
It demonstrates a full CI/CD pipeline with GitHub Actions, secret handling, and artifact upload.

---

## What This App Does

1. You open it in your browser → you see a **Sign in with Google** button
2. You click it → Google asks for permission → you click Allow
3. You come back → you see your **name, email, and profile picture**
4. The app writes `output/result.txt` with your name, email, and a timestamp

---

## Project Structure

```
cicd_homework/
├── app/
│   ├── main.py              # Flask web app (5 routes)
│   └── templates/
│       ├── index.html       # Home page — Sign in button
│       └── profile.html     # Profile page shown after login
├── scripts/
│   └── setup.sh             # Bash: install → test → package artifact
├── tests/
│   └── test_main.py         # 29 pytest tests (no browser needed)
├── .env.example             # Template — copy this to .env and fill in values
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions workflow
├── Makefile                 # Shortcuts for common tasks
└── requirements.txt         # Python dependencies
```

---

## Step 0 — Get the Code

**Fork** the repo on GitHub (click the Fork button in the top-right corner),
then **clone your fork** to your computer:

```bash
git clone https://github.com/<your-username>/cicd_homework.git
cd cicd_homework
```

---

## Step 1 — Create a Google OAuth Client

This app signs users in with Google, so you need to register it in Google Cloud.
You only need a **free** Google account — no credit card required.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (top-left dropdown → **New Project** → give it any name)
3. In the left menu go to **APIs & Services → OAuth consent screen**
   - Choose **External** → click **Create**
   - Fill in **App name** (anything, e.g. `cicd-homework`) and your email → **Save and Continue**
   - Skip Scopes → **Save and Continue**
   - Add your own Gmail address as a **Test user** → **Save and Continue**
4. Go to **APIs & Services → Credentials**
5. Click **+ Create Credentials → OAuth Client ID**
6. Application type: **Web application**
7. Under **Authorized redirect URIs** click **+ Add URI** and type exactly:
   ```
   http://localhost:5000/callback
   ```
8. Click **Create**
9. A popup shows your credentials — click **Download JSON** or just copy the **Client Secret**

> ⚠️ The **Client ID** is already baked into `app/main.py` — you only need the **Client Secret**.

---

## Step 2 — Create Your `.env` File

The `.env` file holds your private secrets. It is **never committed to git** (listed in `.gitignore`).

```bash
cp .env.example .env
```

Now open `.env` in any text editor and fill in two values:

```bash
# Paste the Client Secret from Step 1
GOOGLE_CLIENT_SECRET=GOCSPX-paste-your-secret-here

# Any long random string — signs your login session cookies
APP_SECRET=paste-a-random-string-here
```

Generate a random `APP_SECRET`:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output and paste it as your `APP_SECRET`.

---

## Step 3 — Install Dependencies

Use `make` (recommended — works on Mac and Linux):

```bash
make install
```

Or without make:
```bash
python3 -m pip install -r requirements.txt
```

> 💡 On **macOS with Homebrew Python** you may see a "externally managed" error. `make install` handles this automatically.

---

## Step 4 — Run the App

```bash
make run
```

Or without make:
```bash
python3 app/main.py
```

Open **[http://localhost:5000](http://localhost:5000)** in your browser and click **Sign in with Google**.

**Custom port** — if port 5000 is busy:
```bash
PORT=8080 make run
```
Then open `http://localhost:8080`. The redirect URI updates automatically — no other changes needed.

> ⚠️ If you change `PORT`, also update the **Authorized redirect URI** in Google Cloud Console
> to `http://localhost:<PORT>/callback`.

---

## Step 5 — Run Tests

Tests use Flask's built-in test client — **no browser, no real Google account needed**.

```bash
make test               # run all 29 tests
make test-list          # list all test names
make test-one K=test_login_redirects_to_google   # run one test by name
```

Or without make:
```bash
python3 -m pytest tests/ -v
```

---

## Step 6 — Full CI Pipeline (optional)

Run the same steps GitHub Actions runs:

```bash
make setup
```

This installs deps, runs all tests (saves log to `logs/test.log`), and packages `app/` into `dist/app.tar.gz`.

---

## Makefile Reference

| Command | What it does |
|---------|-------------|
| `make install` | Install Python dependencies |
| `make uninstall` | Uninstall all dependencies from `requirements.txt` |
| `make test` | Run all 29 unit tests |
| `make test-list` | List all test names (usable with `K=`) |
| `make test-one K=<name>` | Run one test by name |
| `make run` | Start the Flask app at `http://localhost:5000` |
| `make setup` | Full CI pipeline: install → test → package |
| `make reauth` | Delete `.token_cache.json` (force Google sign-in again) |
| `make clean` | Delete `output/`, `logs/`, `dist/`, `__pycache__/` |
| `make help` | Show all available commands |

---

## GitHub Actions CI

The workflow (`.github/workflows/ci.yml`) runs automatically on:
- Every push to `main`, `oauth`, or `web` branches
- Every pull request targeting `main`

### What CI Does

1. Checks out code
2. Sets up Python 3.12
3. **Verifies secrets** — fails immediately if `APP_SECRET` or `GOOGLE_CLIENT_SECRET` are missing
4. Runs `scripts/setup.sh` — install, test, package
5. Uploads `dist/app.tar.gz` and `logs/test.log` as downloadable artifacts

### Add Secrets to GitHub

Go to your forked repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Where to get it |
|-------------|-----------------|
| `APP_SECRET` | Any long random string (same command as Step 2) |
| `GOOGLE_CLIENT_SECRET` | From your Google Cloud OAuth client (Step 1) |

> `GOOGLE_CLIENT_ID` is **not** a secret — it is committed directly in `app/main.py`.

---

## Troubleshooting

### `EnvironmentError: APP_SECRET is required`
Your `.env` file is missing or `APP_SECRET` is not set. Check that `.env` exists and has no `#` in front of `APP_SECRET=`.

### `EnvironmentError: GOOGLE_CLIENT_SECRET is required`
Same as above — check `GOOGLE_CLIENT_SECRET=` in your `.env`.

### `Error 400: redirect_uri_mismatch`
The redirect URI in Google Cloud Console does not match the app.
Make sure you added `http://localhost:5000/callback` exactly (no trailing slash) in Step 1.

### `Error 400: invalid_request` or `oauth_test sent an invalid request`
Your Google OAuth client is set to the wrong type (e.g. "TV and Limited Input").
Go back to Step 1 and create a **Web application** client.

### `Session expired or invalid request`
Your browser cookies were cleared or the session timed out. Just click **Sign in with Google** again.

### `Authentication failed: (invalid_grant)`
Try deleting the token cache and signing in again:
```bash
make reauth
```

### Port 5000 is already in use
```bash
PORT=8080 make run
```

---

## How Secrets Work

| What | Sensitive? | Where it lives |
|------|-----------|----------------|
| `GOOGLE_CLIENT_ID` | ❌ No — public | Committed in `app/main.py` |
| `GOOGLE_CLIENT_SECRET` | ✅ Yes | `.env` (local) / GitHub Secret (CI) |
| `APP_SECRET` | ✅ Yes | `.env` (local) / GitHub Secret (CI) |

End users sign in with **their own** Google account — they never see your secrets.
Only the person running the server needs `.env` configured.
