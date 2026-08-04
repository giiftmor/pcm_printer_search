# PCM Compass — Agent Instructions

## Purpose

PCM Compass (repo dir `pcm_printer_search`) is a **multi-functional IT helpdesk toolkit** for the **NWU PCM (Potchefstroom) IT Service Desk**. It replaces the old PCM Printer Search monolith with a modular Flask dashboard plus a Chrome extension (MV3) that together consolidate the desk's daily tools: printer inventory search, user lookup (IDM/Grouper), quick links to NWU portals, and browser-extension distribution. Branding is NWU green (`#006633`).

## Running the App

```bash
docker compose up -d    # Flask app on port 5000 (prod: gunicorn, 4 workers)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d  # Dev mode
python app.py           # Local dev without Docker
./bin/switch.sh dev|prod|rebuild|status|logs|stop   # Mode switcher (writes .mode)
```

- Extension build/upload: `./bin/build-extension.sh` → ZIPs `browser_extension/` to `static/dist/pcm-compass-v{version}.zip`, optionally uploads to Nextcloud WebDAV.
- Env config via `.env` (see `.env.example`): `FLASK_SECRET_KEY`, `ADMIN_PASSWORD`, `WORKBOOK_URL`, `DATA_REFRESH_INTERVAL`, `QUICK_LINKS_FILE`.

## Project Structure (current)

```
app.py              # Flask app factory (create_app) + dev server
config.py           # Config class (env-driven)
core/auth.py        # bcrypt admin auth + admin_required session guard
modules/            # Feature blueprints (each self-contained)
  printer_search/   # engine.py: Excel load/search + 60s auto-reload thread; svcp.py: build_svcp_url + svcp_url row enrichment; routes.py: search + admin CRUD/login
  quick_links/      # engine.py: grouped categories JSON CRUD; routes.py: /api/links (+ categories)
  user_lookup/      # urls.py: URL builders (IDM Consolidation/Password, Grouper, Grouper group URLs + presets); routes.py: /api/user-lookup/urls, /api/user-lookup/grouper-presets, /api/user-lookup/group-url
templates/          # routes.py: page routes; base.html + per-page Jinja templates
static/             # compass.css, compass.js, dist/ (extension ZIPs)
browser_extension/  # Chrome extension (Manifest V3) — popup + url_helpers.js (URL builders, tab-reuse matcher) + build docs
docs/               # Design specs and plans (docs/superpowers/)
.opencode/plans/    # Implementation plans
.superpowers/sdd/   # Subagent-driven-development task briefs/reports/progress
major-improvements-implementation-status.md  # Tests/CI/hardening program tracking
```

> Note: `modules/idm_lookup/` and `modules/grouper/` were deleted — replaced by the single `user_lookup` module that constructs URLs and opens the real NWU pages in browser tabs (browser-native auth, no credentials stored).

## Tech Stack

- **Backend:** Python 3.11, Flask 2.x, Pandas + openpyxl (Excel), requests, bcrypt, gunicorn, python-dotenv
- **Frontend:** Jinja2 server-rendered templates, vanilla JS (no frameworks), custom CSS
- **Extension:** Chrome Manifest V3, vanilla JS, `chrome.storage.local` (history + app URL only)
- **Deploy:** Docker multi-stage build, Docker Compose (prod + dev overlays), Nextcloud WebDAV for distribution
- **Tests:** pytest (run via Docker `pcm-test` image — host has no usable Python) + `node --test` for extension `url_helpers.js`. CI not yet wired — **planned** (see `major-improvements-implementation-status.md`)

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/status` | none | App + extension versions (`{"name","app_version","extension_version"}`) |
| POST | `/api/printer/search` | none | Search all Excel sheets (form field `search_term`; rows may include `svcp_url`) |
| GET | `/api/printer/last-update` | none | Excel data timestamp |
| GET | `/api/admin/status` | none | Is current session admin? |
| POST | `/api/admin/login` | none | Admin password login (bcrypt, session) |
| POST | `/api/admin/logout` | none | Clear admin session |
| GET | `/api/admin/get_url` | admin | Saved workbook URL |
| POST | `/api/admin/update_url` | admin | Update workbook URL + reload data |
| POST | `/api/admin/reload_data` | admin | Force Excel reload |
| GET | `/api/links` | none | List categories with nested links (`{"categories":[...]}`) |
| POST | `/api/links` | admin | Add link (JSON: `category_id`, name, url, icon) |
| DELETE | `/api/links/<id>` | admin | Remove link by id |
| POST | `/api/links/categories` | admin | Add empty category (JSON: name) |
| DELETE | `/api/links/categories/<id>` | admin | Remove empty category (409 if non-empty, 404 if unknown) |
| GET | `/api/user-lookup/urls?user_id=X` | none | Return IDM/Grouper URLs for a user |
| GET | `/api/user-lookup/grouper-presets` | none | Preset Grouper groups (`{"presets":[{"id","label","name","url"}]}`) |
| GET | `/api/user-lookup/group-url?name=X` | none | Build Grouper group URL for a stem/name |

Pages: `/` (dashboard), `/printer-search`, `/quick-links`, `/user-lookup`, `/download-extension`, `/download-extension/zip`.

> `POST /api/printer/search` result rows may include `svcp_url`, built by `modules/printer_search/svcp.py` from the `Printer Hostname` cell. The web UI renders this field (escaped) and never concatenates raw hostname into an `href`.

## Security Model

- **No NWU credentials stored anywhere** — IDM/Grouper use browser-native auth; extension only holds the Flask app URL + local search history.
- Admin auth: single password (bcrypt-hashed at startup from `ADMIN_PASSWORD`), Flask session cookie.
- **Known gaps under hardening** (tracked in `major-improvements-implementation-status.md`): a plaintext NWU password exists in git history (old docs), a hardcoded Nextcloud share token in `bin/build-extension.sh`, default admin password fallback, no CSRF protection, no rate limiting on login, dependency ranges unpinned. Do NOT introduce new hardcoded secrets.

## Versioning

- App: `VERSION` file (repo root) is the source of truth, exposed as `Config.APP_VERSION`, footer, and `/api/status`. `package.json` mirrors it. Semver; bump on release.
- Extension: `browser_extension/manifest.json` is the source of truth. `bin/build-extension.sh` reads it for the zip name. Bump on every shippable extension change.

## Development Workflow

- **Test/lint first:** pytest suite in `tests/` runs via Docker (`docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q"`); extension JS via `node --test tests/url_helpers.test.js`. CI is still the active improvement program (see status doc) — prefer writing/updating tests in the same change as code.
- **Module pattern:** each feature = `modules/<name>/` with `engine.py` (logic) + `routes.py` (blueprint) + `__init__.py`; page templates extend `templates/base.html`.
- **Conventions:** JSON endpoints prefixed `/api/`; vanilla JS only; NWU green `#006633`/`#4a8c6f`; no external JS frameworks.
- **Planning:** larger work goes through superpowers — spec in `docs/superpowers/specs/`, plan in `.opencode/plans/` (or `docs/superpowers/plans/`), execute via subagent-driven development with task briefs/reports under `.superpowers/sdd/`. Commit per task.

## 📝 Changelog

**MANDATORY: Update CHANGELOG.md on every task completion.**

After any meaningful change:
1. Open `CHANGELOG.md` and add an entry under `[Unreleased]`
2. Section: Added / Changed / Fixed
3. Format: `- YYYY-MM-DD: Brief description`
4. When changes are verified working, run `~/.agents/scripts/release.sh` to stamp as a versioned release
5. If no CHANGELOG.md exists, copy from `~/.agents/templates/CHANGELOG.md`
6. **Also** add a one-line summary to `~/projects/tailnet-changelog/CHANGELOG.md`
