# Blog App

FastAPI-based blog automation system for:

- AI-assisted draft generation
- Multi-platform publishing
- OpenClaw campaign scheduling and approvals
- Session-based image/media publishing workflows

## Main Features

- Generate posts from:
  - direct topic input
  - URLs
  - YouTube transcripts or metadata
  - uploaded PDF, TXT, and Markdown files
- Publish to:
  - WordPress
  - Blogger
  - Facebook
  - Instagram
  - TikTok
  - Telegram
- Run recurring campaigns with:
  - scheduled execution
  - AI quality review
  - approval queue
  - retry support

## Project Layout

```text
app/
  routers/                FastAPI route handlers
services/                 Business logic and external integrations
templates/pages/          Server-rendered UI pages
static/                   JS, CSS, fonts, and images
tests/                    Automated regression tests
config.py                 Runtime config loading
database.py               SQLite schema and CRUD helpers
main.py                   App entry point
blog_app.db               Local SQLite database
```

## Main Screens

- `/blog-independent`
  - topic-driven generation workspace
- `/settings`
  - API keys, provider settings, automation settings
- `/publish-hub`
  - publish session and media workflow
- `/openclaw-dashboard`
  - campaign, run, and approval monitoring
- `/logs`
  - operation logs

## Run Locally

1. Install dependencies

```powershell
pip install -r requirements.txt
```

2. Configure environment

- Copy `.env.example` to `.env` if needed
- Fill in the API keys and publishing credentials you plan to use

3. Start the app

```powershell
python main.py
```

Default local address:

- `http://127.0.0.1:8000`

## Core API Groups

- Settings and health
  - `/api/settings/*`
  - `/api/health`
- Blog generation and publish
  - `/api/blog/*`
- Publish Hub session flow
  - `/api/publish/*`
- OpenClaw automation
  - `/api/openclaw/*`

See [ARCHITECTURE_REVIEW_2026-08-08.md](D:/Projects/BLOG/blog_app/ARCHITECTURE_REVIEW_2026-08-08.md) for the fuller architecture, runtime flow, and risk review.

## Tests

Run the current regression suite with the standard library test runner:

```powershell
python -m unittest discover -s tests -v
```

Current coverage focuses on deterministic core logic:

- publish HTML assembly
- publish payload and HTML validation
- scheduler time/date calculations

## Notes

- The app stores mutable runtime settings in SQLite and also uses `.env` for bootstrap configuration.
- The server starts an in-process scheduler on FastAPI startup.
- Output assets are exposed through `/output`.
