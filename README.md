# PCM Compass

A **multi-functional IT helpdesk toolkit** for the **NWU PCM (Potchefstroom) IT Service Desk**. PCM Compass consolidates the desk's daily tools into a modular Flask dashboard plus a Chrome browser extension (Manifest V3): printer inventory search, quick links to NWU portals, user lookup (IDM / Grouper), SCSM ticket/user search, and browser-extension distribution.

It replaces the old PCM Printer Search monolith. Branding is NWU green (`#006633`).

> **Related project:** the SCSM Search page is backed by the separate **[scsm-search](https://github.com/giiftmor/scsm-search)** API service. See [SCSM Search & the scsm-search API](#scsm-search--the-scsm-search-api).

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Pages & API endpoints](#pages--api-endpoints)
- [Modules](#modules)
- [Browser extension](#browser-extension)
- [Testing](#testing)
- [Deployment](#deployment)
- [Versioning](#versioning)
- [Security model](#security-model)
- [Project structure](#project-structure)
- [SCSM Search & the scsm-search API](#scsm-search--the-scsm-search-api)
- [Changelog](#changelog)

---

## Features

- **Printer search** — search the NWU printer inventory Excel workbook across all sheets (hostname, serial, MAC, etc.), with a generated SVCP portal link (`https://{hostname}.svcp.nwu.ac.za`) per matching row and a 60-second background auto-reload.
- **Quick links** — categorized NWU portal links (Portals, Printing, Identity, SIS Omnia, NAC) with an admin CRUD API and sectioned UI (web + extension).
- **User lookup** — construct IDM consolidation / IDM password and Grouper person/group URLs from a user ID, opening the real NWU pages in a new tab (browser-native auth, no credentials stored). Includes preset Grouper groups.
- **SCSM Search** — split-pane agent workspace over the scsm-search API: Google-style search results (Incidents + Service Requests), relationship tabs (All / Affected user / Created by / Assigned), a detail pane with "Open in SCSM ↗", and a background related-tickets cache (30-min TTL).
- **Browser extension** — MV3 popup for printer search, user lookup, quick links, and an "Open app" link, distributed through a Nextcloud shared folder.

---

## Architecture

```
                        ┌────────────────────────────┐
                        │  PCM Compass (Flask, :5000) │
                        │                            │
                        │  /printer-search            │
                        │  /quick-links               │
                        │  /user-lookup               │
                        │  /scsm-search ───────┐      │
                        │  /download-extension  │      │
                        └───────────┬───────────┘      │
                                    │                  │
              Chrome extension      │                  │
              (MV3, Nextcloud       │                  │  HTTP/JSON (x-api-key)
              distributed) ──────── │                  │
                                    │                  ▼
                        ┌───────────┴───────────┐  ┌─────────────────────┐
                        │  n8n / other tools     │  │  scsm-search API     │
                        │  (same ai-stack net)   │  │  (Node/Express,      │
                        └───────────────────────┘  │   :8080, separate     │
                                                    │   repo) → SQL Server  │
                                                    └─────────────────────┘
```

The Flask app, the extension, and `scsm-search` all live on the `ai-stack_ai_net` Docker network.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, Flask 2.x, Pandas + openpyxl (Excel), requests, bcrypt, gunicorn, python-dotenv |
| Frontend | Jinja2 server-rendered templates, vanilla JS (no frameworks), custom CSS |
| Extension | Chrome Manifest V3, vanilla JS, `chrome.storage.local` |
| Deploy | Docker multi-stage build, Docker Compose (prod + dev overlays), Nextcloud WebDAV for extension distribution |
| Tests | `pytest` (via Docker `pcm-test` image) + `node --test` for extension JS |

---

## Quick start

```bash
cp .env.example .env          # fill in FLASK_SECRET_KEY, ADMIN_PASSWORD, etc.
docker compose up -d          # Flask app on :5000 (prod: gunicorn, 4 workers)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d   # dev mode
python app.py                 # local dev without Docker
./bin/switch.sh dev|prod|rebuild|status|logs|stop                       # mode switcher
```

Open http://localhost:5000.

---

## Configuration

All configuration is via `.env` (see `.env.example`):

| Var | Default | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | dev fallback | Flask session signing key (set a real one) |
| `ADMIN_PASSWORD` | `print@NWU` | Admin login password (bcrypt-hashed at startup) |
| `WORKBOOK_URL` | Nextcloud share URL | Source of the printer inventory Excel workbook |
| `DATA_REFRESH_INTERVAL` | `60` | Seconds between background Excel reloads |
| `SCSM_API_URL` | `http://scsm-search:3000` | Base URL of the scsm-search API (see below) |
| `SCSM_API_KEY` | (empty) | API key for the scsm-search service |
| `SCSM_PORTAL_BASE` | `https://support.nwu.ac.za` | Base for "Open in SCSM ↗" deep links |

`QUICK_LINKS_FILE` (`quick_links.json`) holds the categorized quick-link data and is managed via the admin API.

---

## Pages & API endpoints

Pages:

| Path | Purpose |
|---|---|
| `/` | Dashboard |
| `/printer-search` | Printer inventory search |
| `/quick-links` | Categorized NWU portal links |
| `/user-lookup` | IDM / Grouper URL builder |
| `/scsm-search` | SCSM ticket/user search workspace |
| `/download-extension` | Extension download + install instructions |

API (JSON, `/api/` prefix):

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/status` | none | App + extension versions |
| POST | `/api/printer/search` | none | Search Excel sheets (`search_term`; rows may include `svcp_url`) |
| GET | `/api/printer/last-update` | none | Excel data timestamp |
| GET | `/api/admin/status` | none | Is current session admin? |
| POST | `/api/admin/login` | none | Admin password login (bcrypt, session) |
| POST | `/api/admin/logout` | none | Clear admin session |
| GET | `/api/admin/get_url` | admin | Saved workbook URL |
| POST | `/api/admin/update_url` | admin | Update workbook URL + reload data |
| POST | `/api/admin/reload_data` | admin | Force Excel reload |
| GET | `/api/links` | none | List categories with nested links (`{"categories":[...]}`) |
| POST | `/api/links` | admin | Add link |
| DELETE | `/api/links/<id>` | admin | Remove link |
| POST | `/api/links/categories` | admin | Add empty category |
| DELETE | `/api/links/categories/<id>` | admin | Remove empty category |
| GET | `/api/user-lookup/urls?user_id=X` | none | IDM/Grouper URLs for a user |
| GET | `/api/user-lookup/grouper-presets` | none | Preset Grouper groups |
| POST | `/api/scsm/tickets` | none | Proxy: SCSM ticket search (both types merged, sorted by date) |
| POST | `/api/scsm/users` | none | Proxy: SCSM user search |
| GET | `/api/scsm/users/<id>/tickets` | none | Proxy: user's tickets (with related-tickets cache) |
| POST | `/api/scsm/related` | none | Related-ticket tabs for a ticket's users + SCSM deep link |

> The `/api/scsm/*` routes are proxies into the **scsm-search** service and are configured by `SCSM_API_URL` / `SCSM_API_KEY`.

---

## Modules

Each feature is a self-contained blueprint under `modules/`:

| Module | Files | What it does |
|---|---|---|
| `printer_search` | `engine.py` (Excel load/search + auto-reload), `svcp.py` (`build_svcp_url`), `routes.py` | Printer inventory search + admin CRUD/login |
| `quick_links` | `engine.py` (grouped JSON CRUD), `routes.py` | Categorized quick links + admin endpoints |
| `user_lookup` | `urls.py` (IDM/Grouper URL builders), `routes.py` | URL construction; browser-native auth on the real NWU pages |
| `scsm_search` | `engine.py` (scsm-search API client + related-tickets cache), `routes.py` | The `/scsm-search` agent workspace |

---

## Browser extension

The Chrome extension (`browser_extension/`) is the desk's on-the-go access point: printer search, user lookup, quick links, SCSM search, and app/version links in a popup.

- **Installation for users:** see [`browser_extension/INSTALL.md`](browser_extension/INSTALL.md) (Nextcloud synced-folder install is the primary path; ZIP is the fallback).
- **Developer docs:** [`browser_extension/README.md`](browser_extension/README.md).

### Distribution (Nextcloud CI/CD)

The extension is distributed through a **Nextcloud shared folder** — a fully enclosed, rudimentary CI/CD pipeline:

1. **Develop** in `browser_extension/`.
2. **Deploy** with `./bin/build-extension.sh` — ZIPs the extension to `static/dist/pcm-compass-v{version}.zip` and uploads individual files + docs to the Nextcloud share.
3. **Clients** sync that folder with the Nextcloud desktop client ("Always keep on this device") and load the extension via **Load unpacked**.
4. **Updates:** JS/HTML/CSS changes apply on the next popup open; `manifest.json` changes (version, permissions, icons) need a one-time **Reload (↻)** on `chrome://extensions` (the popup shows a reload banner via the deployed `version.json`).

**Hard rules** (guarded by `tests/build_extension.test.js`):
- `EXT_FILES` in `bin/build-extension.sh` must list **every** runtime file — a missing entry silently breaks client installs (`PCM_URL_HELPERS is not defined`, `ERR_FILE_NOT_FOUND`, etc.).
- Bump `manifest.json` on every shippable change and keep the in-extension `changelog.html` in sync.
- No secrets in the extension or its deploy script.

---

## Testing

```bash
# Backend (pytest) — the host has no usable Python, run via the pcm-test Docker image:
docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q"

# Extension JS:
node --test tests/url_helpers.test.js tests/build_extension.test.js
```

CI is not wired yet — it is a tracked improvement program (see `major-improvements-implementation-status.md`). Prefer writing/updating tests in the same change as code.

---

## Deployment

`docker-compose.yml` runs the app on host port **5000**, reads `.env`, joins the external `ai-stack_ai_net` network (so it can reach `scsm-search` by name), and health-checks `/`. The multi-stage `Dockerfile` builds the extension during image build and runs gunicorn as a non-root `appuser`.

`docker-compose.dev.yml` overlays live-mounted source + Flask debug reloader.

---

## Versioning

- **App:** `VERSION` (repo root) is the source of truth — exposed as `Config.APP_VERSION`, the footer, and `/api/status`. Mirrored in `package.json`. Semver; bump on release.
- **Extension:** `browser_extension/manifest.json` is the source of truth; `bin/build-extension.sh` reads it for the ZIP name and writes `version.json`.

After meaningful changes, add an entry to `CHANGELOG.md` under `[Unreleased]` (see [Changelog](#changelog)).

---

## Security model

- **No NWU credentials stored anywhere** — IDM/Grouper use browser-native auth; the extension only holds the Flask app URL + local search history.
- **Admin auth:** single password (bcrypt-hashed at startup from `ADMIN_PASSWORD`), Flask session cookie, `admin_required` guard on admin routes.
- **Known gaps under hardening** (tracked in `major-improvements-implementation-status.md`): a plaintext NWU password exists in old git history, a hardcoded Nextcloud share token in `bin/build-extension.sh`, default admin password fallback, no CSRF protection, no rate limiting on login, dependency ranges unpinned. Do **not** introduce new hardcoded secrets.

---

## Project structure

```
app.py              # Flask app factory (create_app) + dev server
config.py           # Config class (env-driven)
core/auth.py        # bcrypt admin auth + admin_required session guard
modules/            # Feature blueprints (each self-contained)
  printer_search/
  quick_links/
  user_lookup/
  scsm_search/
templates/          # base.html + per-page Jinja templates + page routes
static/             # compass.css, compass.js, dist/ (extension ZIPs)
browser_extension/  # Chrome extension (MV3): popup + url_helpers.js + changelog.html
bin/                # build-extension.sh, switch.sh
docs/               # Design specs and plans (docs/superpowers/)
tests/              # pytest suites + extension JS tests
major-improvements-implementation-status.md  # Tests/CI/hardening program tracking
```

---

## SCSM Search & the scsm-search API

The `/scsm-search` page does **not** talk to SQL Server. It consumes the dedicated **[scsm-search](https://github.com/giiftmor/scsm-search)** service — a read-only Node/Express API that queries the SCSM `CiresonAnalytics` warehouse (`SM_WorkItem_Incident`, `SM_WorkItem_ServiceRequest`) and the `ServiceManager` user view, and exposes:

- `GET /v1/search/tickets?type=incident|servicerequest&q=&status=&priority=&...`
- `GET /v1/search/users?q=`
- `GET /v1/users/:id/tickets?role=affected|created_by|assigned`

All endpoints require an `x-api-key` header. Compass proxies them through `/api/scsm/*`, and the `modules/scsm_search/engine.py` client adds:

- merging of both ticket types with a `ticketType` discriminator,
- enrichment with an "Open in SCSM ↗" deep link (`SCSM_PORTAL_BASE/{Incident|ServiceRequest}/Edit/{id}/`),
- a **related-tickets cache** (30-minute TTL, daemon warm threads, in-flight guards) so relationship tabs respond instantly on re-visit.

**Wiring:** both services run on the `ai-stack_ai_net` Docker network. `SCSM_API_URL` points at `scsm-search` by service name (port `8080` in the live stack; the repo default `http://scsm-search:3000` until a permanent port is chosen), and `SCSM_API_KEY` carries the consumer key issued to Compass.

See the scsm-search repo for full API documentation, and `docs/scsm-search-architecture.md` in this repo for the original design.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Entries are added under `[Unreleased]` for every meaningful change and stamped into a versioned release with `~/.agents/scripts/release.sh`.
