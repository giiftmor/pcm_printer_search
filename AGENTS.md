# PCM Compass — Agent Instructions

## Running the App

```bash
docker compose up -d    # Flask app on port 5000
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d  # Dev mode
python app.py           # Local dev without Docker
```

## Project Structure

```
app.py              # Flask app factory + dev server
config.py           # Config class (env-driven)
core/               # Shared utilities (auth, helpers)
modules/            # Feature blueprints
  printer_search/   # Printer search module
  idm_lookup/       # IDM lookup module
  grouper/          # Grouper module
  quick_links/      # Quick links module
templates/          # Page routes + Jinja templates
static/             # CSS, JS, images
browser_extension/  # Chrome extension (Manifest V3)
docs/               # Design specs and documentation
```

## Tech Stack

Python 3.11, Flask, Pandas, openpyxl, Gunicorn, Docker, Chrome Extension (Manifest V3)

## 📝 Changelog

**MANDATORY: Update CHANGELOG.md on every task completion.**

After any meaningful change:
1. Open `CHANGELOG.md` and add an entry under `[Unreleased]`
2. Section: Added / Changed / Fixed
3. Format: `- YYYY-MM-DD: Brief description`
4. When changes are verified working, run `~/.agents/scripts/release.sh` to stamp as a versioned release
5. If no CHANGELOG.md exists, copy from `~/.agents/templates/CHANGELOG.md`
6. **Also** add a one-line summary to `~/projects/tailnet-changelog/CHANGELOG.md`
