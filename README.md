# CI/CD Homework

A Python web app that shows a profile page with a configurable identity.
It demonstrates a full CI/CD pipeline with GitHub Actions, secret handling, and artifact upload.

---

## What This App Does

1. You open it in your browser → you see an **Enter app** button
2. You click it → you are signed in with a mock identity
3. You see a **profile page** with your name, email, and (optional) avatar
4. The app writes `output/result.txt` with your name, email, and a timestamp

The identity is configured via environment variables — perfect for testing and CI pipelines.

---

## Project Structure

```
cicd_homework/
├── app/
│   ├── main.py              # Flask web app (4 routes)
│   └── templates/
│       ├── index.html       # Home page — Enter app button
│       └── profile.html     # Profile page shown after login
├── scripts/
│   └── setup.sh             # Bash: install → test → package artifact
├── tests/
│   └── test_main.py         # pytest tests (no browser needed)
├── .env.example             # Template — copy this to .env and fill in values
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI workflow
├── Makefile                 # Shortcuts for common tasks
└── requirements.txt         # Python dependencies
```

---

## Quick Start

### Step 0 — Get the Code

**Fork** the repo on GitHub (Fork button in the top-right corner),
then **clone your fork**:

```bash
git clone https://github.com/<your-username>/cicd_homework.git
cd cicd_homework
```

### Step 1 — Create `.env`

```bash
cp .env.example .env
```

Open `.env` and set `APP_SECRET` to any long random string:

```bash
APP_SECRET=paste-a-random-string-here
```

### Step 2 — Run

```bash
make
```

That's it. Open **[http://localhost:5000](http://localhost:5000)** and click **Enter app**.

> 5000 is the default port. Override by adding `PORT=<number>` to your `.env`.

---

## Customize the Identity

By default the profile shows **Local User / local@localhost**.
Change it by adding any of these to your `.env`:

```bash
MOCK_NAME=Ada Lovelace
MOCK_EMAIL=ada@example.com
MOCK_PICTURE=https://example.com/avatar.jpg
```

---

## Run Tests

Tests use Flask's test client — no browser needed.

```bash
make test               # run all tests
make test-list          # list all test names
make test-one K=test_profile_shows_name   # run one test by name
```

---

## Full CI Pipeline (optional)

Runs the same steps as GitHub Actions:

```bash
make ci
```

Installs deps, runs all tests (log → `logs/test.log`), packages `app/` into `dist/app.tar.gz`.

---

## Makefile Reference

| Command | What it does |
|---------|-------------|
| `make` | Start the app (same as `make run`) |
| `make install` | Install Python dependencies |
| `make uninstall` | Uninstall all packages from `requirements.txt` |
| `make run` | Start Flask app at `http://localhost:5000` |
| `make test` | Run all unit tests |
| `make test-list` | List all test names (usable with `K=`) |
| `make test-one K=<name>` | Run one test by name |
| `make ci` | Run full CI pipeline locally: install → test → package |
| `make clean` | Delete `output/`, `logs/`, `dist/`, `__pycache__/` |
| `make help` | Show all available commands |

---

## GitHub Actions CI

Two workflows live in `.github/workflows/`:

| Workflow | File | Trigger |
|----------|------|---------|
| **CI** | `ci.yml` | Push to `main`/`web`/`skip_oauth`; every PR to `main` |
| **Auto-merge** | `auto-merge.yml` | When CI completes on a PR |

The **CI** workflow runs automatically on:
- Every push to `main`, `web`, or `skip_oauth` branches
- Every pull request targeting `main`

### What CI Does

1. Checks out code
2. Sets up Python 3.12
3. **Verifies `APP_SECRET`** is set — fails immediately if missing
4. Runs `scripts/setup.sh` — install, test, package
5. Uploads `dist/app.tar.gz` and `logs/test.log` as downloadable artifacts

### Add Secrets to GitHub

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Description |
|--------|-------------|
| `APP_SECRET` | Any long random string — signs session cookies |

---

## Auto-merge Workflow

The second workflow (`.github/workflows/auto-merge.yml`) watches every CI run on a pull request
and **automatically merges or rejects the PR** — no human click required.

### How it works

```
Developer pushes branch
       │
       ▼
CI workflow runs  ──────────────────────────────┐
       │                                        │
  ✅ Passes                                ❌ Fails
       │                                        │
       ▼                                        ▼
Auto-merge triggers                    Auto-reject triggers
  • Squash-merges PR into main           • Adds label "ci-failed"
  • Deletes the feature branch           • Posts comment with link to failed job logs
  • Posts comment with CI log link       • PR stays open — developer fixes & re-pushes
    and app.tgz artifact download
```

### One-time repo setup (required)

Auto-merge only works reliably when GitHub enforces that CI must pass before merging.
Without branch protection the workflow still runs, but anyone could click "Merge" manually
before CI finishes.

**Recommended branch protection rule for `main`:**

1. Go to **Settings → Branches → Add branch ruleset** (or "Add rule" on older UI).
2. Set **Branch name pattern** to `main`.
3. Enable **"Require status checks to pass before merging"**.
4. Add `CI` (the workflow name) to the required status checks.
5. Optionally enable **"Require branches to be up to date before merging"**.
6. Save.

That's it. With this in place the sequence is fully automatic:

| Scenario | Outcome |
|----------|---------|
| PR CI passes | Squash-merged into `main`, branch deleted; comment posted with CI log link and `app.tgz` download |
| PR CI fails  | `ci-failed` label added; comment posted with direct link to failed job logs; PR stays open |

### Permissions used

The workflow runs with the built-in `GITHUB_TOKEN` — no new secrets needed.
It requests:
- `contents: write` — to push the merge commit
- `pull-requests: write` — to comment and add labels

---

## Troubleshooting

### `EnvironmentError: APP_SECRET is required`
Your `.env` file is missing or `APP_SECRET` is not set.
If you just cloned the repo, run:
```bash
cp .env.example .env
```
Then edit `.env` and set `APP_SECRET`.

### Port 5000 is already in use
Add `PORT=8080` (or any free port) to your `.env`, then run `make` again.

### I want to sign in as a different user
Open a private/incognito browser window, or clear your cookies for `localhost`.
Then update `MOCK_NAME` / `MOCK_EMAIL` in `.env` and restart with `make`.

---

## Environment Variables Reference

| Variable | Required? | Default | Description |
|----------|-----------|---------|-------------|
| `APP_SECRET` | ✅ Yes | — | Signs Flask session cookies — keep private |
| `PORT` | No | `5000` | Port the app listens on |
| `MOCK_NAME` | No | `Local User` | Name shown on profile page |
| `MOCK_EMAIL` | No | `local@localhost` | Email shown on profile page |
| `MOCK_PICTURE` | No | *(none)* | Avatar URL — leave blank for no avatar |
