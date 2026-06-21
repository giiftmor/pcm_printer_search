# PCM Printer Search — Agent Instructions

## Running the App

```bash
docker compose up -d    # Flask app on port 5000
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d  # Dev mode
```

## Tech Stack

Python 3.11, Flask, Pandas, openpyxl, Gunicorn, Docker

## 📝 Changelog

**MANDATORY: Update CHANGELOG.md on every task completion.**

After any meaningful change:
1. Open `CHANGELOG.md` and add an entry under `[Unreleased]`
2. Section: Added / Changed / Fixed
3. Format: `- YYYY-MM-DD: Brief description`
4. When changes are verified working, run `~/.agents/scripts/release.sh` to stamp as a versioned release
5. If no CHANGELOG.md exists, copy from `~/.agents/templates/CHANGELOG.md`
6. **Also** add a one-line summary to `~/projects/tailnet-changelog/CHANGELOG.md`
