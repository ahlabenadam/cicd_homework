# CI/CD Homework

A minimal Python app with a full GitHub Actions CI/CD pipeline, demonstrating:

- A simple Python script with file output
- A Bash setup/test/package script
- GitHub Actions workflow with artifact upload and secret handling

## Project Structure

```
cicd_homework/
├── app/
│   └── main.py              # Python app
├── scripts/
│   └── setup.sh             # Bash: install deps, run tests, package
├── tests/
│   └── test_main.py         # pytest unit tests
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI workflow
└── requirements.txt
```

## Running Locally

### Prerequisites

- Python 3.12+
- bash

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the app

```bash
python app/main.py
```

Output is written to `output/result.txt`.

### 3. Run the full setup script (install + test + package)

```bash
bash scripts/setup.sh
```

This will:
1. Install dependencies via pip
2. Smoke-test the app
3. Run pytest and save a log to `logs/test.log`
4. Package `app/` into `dist/app.tar.gz`

### 4. Run tests only

```bash
pytest tests/ -v
```

## GitHub Actions CI

The workflow (`.github/workflows/ci.yml`) triggers on:
- Push to `main`
- Pull requests targeting `main`

Steps:
1. Checkout code
2. Set up Python 3.12
3. Run `scripts/setup.sh`
4. Upload `dist/app.tar.gz` and `logs/test.log` as artifacts
5. Report success or failure

## Secret Handling (Bonus)

The workflow reads `APP_SECRET` from a GitHub Actions secret and passes it as an environment variable to the setup script and app. The app masks the secret value in its log output.

To add the secret:
1. Go to **Settings → Secrets and variables → Actions** in the repository
2. Click **New repository secret**
3. Name: `APP_SECRET`, Value: *(your secret value)*
