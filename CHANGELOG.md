# Changelog

## [Unreleased]

### Added
- 2026-08-10: PCM Compass SCSM Search integration design spec — split-pane agent workspace page (Google-style search results + relationship tabs: All results / Affected user / Created by / Assigned) backed by the live scsm-search API; scsm-search backend additions (WorkItemId in `q`, `createdByUser`/`assignedUser` in ticket responses, `role` param on `/v1/users/:id/tickets`); background "other tickets" cache (30-min TTL, in-process) with progressive-disclosure delay model (`docs/superpowers/specs/2026-08-10-scsm-search-compass-integration-design.md`)

### Fixed
- 2026-08-04: Extension popup crash on Search/Open app when the app URL has a port (e.g. `196.252.15.214:5000`) — tab match pattern built from `new URL(appUrl).hostname` (no port) with a `tabs.query` fallback to `tabs.create` (extension v2.3.3)
- 2026-08-04: Extension popup crash (`PCM_URL_HELPERS is not defined`) — `bin/build-extension.sh` `EXT_FILES` now includes `url_helpers.js`, so the Nextcloud `pcm-compass/` per-file folder ships it; regression guarded by `tests/build_extension.test.js`

### Changed
- 2026-08-04: Grouper group presets now store full subject-summary URLs (with UUIDs) instead of name stems — preset shape is `{id, label, url}`; removed free-text group lookup, `build_grouper_group_url`/`buildGrouperGroupURL` builders, and `GET /api/user-lookup/group-url` endpoint (extension v2.3.2)
- 2026-08-04: Extension "Open App" button moved from the printer row to the popup footer; dead ⚙ settings gear now toggles an inline App URL panel (save/reset via `chrome.storage.local`)

### Added
- 2026-08-06: SCSM search service implemented (`~/projects/scsm-search`) — read-only Node/TS API over CiresonAnalytics (`SM_WorkItem_Incident`/`SM_WorkItem_ServiceRequest`) + ServiceManager user view; `/v1/search/tickets|users`, `/v1/users/:id/tickets`; per-consumer API keys; SEARCH_MODE fts/like
- 2026-08-06: SCSM search service design spec — read-only search API over the CiresonAnalytics warehouse (`docs/superpowers/specs/2026-08-06-scsm-search-service-design.md`), validating/refining `docs/scsm-search-architecture.md` (Express 5 + TypeScript, `mssql`, zod, per-consumer API keys, `/v1/` prefix, SEARCH_MODE fts/like fallback); n8n consumes it, PCM Compass app + extension later
- 2026-08-05: Extension update banner now has an "Update now" button — one-click `chrome.runtime.reload()` (equivalent to the chrome://extensions ↻; re-reads the manifest from disk), shown only when the on-disk `version.json` differs from the loaded manifest (extension v2.3.4)
- 2026-08-04: Extension auto-prefixes printer hostnames with `P-` when hostname-shaped (`BPKL2` → `P-BPKL2`); serials/MACs/other search terms pass through untouched; Open SVCP now only accepts hostname-shaped input. Detection regex derived from a live workbook scan (`^(p-)?[a-z]{3,12}\d{1,3}$`); new `normalizePrinterHostname` in `url_helpers.js` with node tests (extension v2.3.3)
- 2026-08-04: Extension reload-nudge — `bin/build-extension.sh` writes `version.json` (from manifest) into the package; popup compares it to the manifest and shows a reload banner on mismatch (extension v2.3.2)
- 2026-08-04: User-facing extension changelog — in-extension `changelog.html` with a popup footer link ("What's new") and live version read from the manifest (extension v2.3.1)
- 2026-08-04: `tests/build_extension.test.js` now guards that every popup script + runtime file (css, icons, changelog) is listed in `EXT_FILES` and exists in `browser_extension/`
- 2026-08-04: AGENTS.md "Extension CI/CD (Nextcloud)" section — documents the Nextcloud shared-folder deploy pipeline, client sync ("Always keep on this device"), load-unpacked path, and update semantics (next popup open vs. manifest reload)
- 2026-08-04: Grouper group lookup — 7 preset groups (Papercut staff, Azure staff/students, MS licenses, Acrobat) + free-text group open; Python+JS builders, 2 new API endpoints, web card, extension popup section
- 2026-08-03: `enrich_row_with_svcp` helper (`modules/printer_search/svcp.py`) — attaches optional `svcp_url` to printer search result rows via `search_all_sheets`, plus pytest coverage
- 2026-08-03: `GET /api/status` endpoint — returns app + extension versions; app `VERSION` file (repo root) as source of truth, exposed via `Config.APP_VERSION` and footer
- 2026-08-03: `build_svcp_url` helper (`modules/printer_search/svcp.py`) — sanitized SVCP URL construction with strict hostname validation, plus pytest coverage
- 2026-08-03: Quick Links categorized into 5 groups (Portals, Printing, Identity, SIS Omnia, NAC) — grouped data model with legacy migration, category admin endpoints, sectioned web UI + extension popup
- 2026-08-03: `major-improvements-implementation-status.md` — program tracking for tests, CI, and security hardening (baseline audit + findings + planned streams)
- 2026-08-03: AGENTS.md overhauled — current module structure, API endpoint table, security model, and hardening-gap tracking
- 2026-07-21: Extension build script (`bin/build-extension.sh`) — packages extension as ZIP, uploads to Nextcloud WebDAV
- 2026-07-21: Extension download page (`/download-extension`) with install instructions for Chrome, Edge, Brave, Opera, Firefox
- 2026-07-21: Extension tab reuse — IDM and Grouper buttons switch to existing tabs instead of opening duplicates
- 2026-07-21: SVCP link on printer hostname column — opens printer web interface at `https://{hostname}.svcp.nwu.ac.za`
- 2026-07-21: Hardcoded quick links fallback in extension — works offline without Flask server
- 2026-07-21: INSTALL.md — installation guide for all browsers, ships inside extension ZIP
- 2026-07-21: User lookup module — URL builder with IDM consolidation, IDM password, and Grouper URL construction
- 2026-07-21: User lookup API endpoint — `GET /api/user-lookup/urls` returning JSON with IDM and Grouper URLs
- 2026-07-20: PCM Compass design spec — multi-functional IT helpdesk toolkit with Flask dashboard + Chrome extension
- 2026-07-20: Dashboard base template (base.html, dashboard.html) with sidebar nav, NWU green branding, and 4 tool cards
- 2026-07-20: Shared CSS (compass.css) and JS (compass.js) for dashboard UI
- 2026-07-20: Printer search module — Excel data engine with search and admin routes
- 2026-07-20: Quick links module — JSON file storage with CRUD API and dashboard cards
- 2026-07-20: Flask page routes blueprint (templates/routes.py) for dashboard, printer search, user lookup, quick links, download extension

### Changed
- 2026-08-04: Extension v2.3.1 — popup footer with version + "What's new" changelog link; INSTALL.md + download page now document the Nextcloud synced-folder install as primary (ZIP as fallback)
- 2026-08-04: Extension v2.3.0 — Grouper Groups section (preset chips + manual Open); person button renamed to "Grouper User" in web UI
- 2026-08-03: Extension v2.2.1 — permanent app URL updated to `http://196.252.15.214:5000` (DEFAULT_APP_URL + host_permissions; old IP removed)
- 2026-08-03: Printer search web results render the API's escaped `svcp_url` link instead of concatenating raw hostname into an `href` (bad hostnames show plain text)
- 2026-08-03: Extension v2.2.0 — Open SVCP button in popup opens `https://{hostname}.svcp.nwu.ac.za` via `buildSvcpUrl` (mirrors `modules/printer_search/svcp.py`), reusing the SVCP tab
- 2026-08-03: Download-extension fallback version now derives from `browser_extension/manifest.json` instead of a hardcoded `2.1.0`; `package.json` synced to app `VERSION` (0.2.0)
- 2026-08-03: Post-review polish — AGENTS.md API docs for grouped links; route test renames + auth coverage; migration rewrite assertion
- 2026-08-03: Extension popup quick links — grouped by category (`DEFAULT_CATEGORIES`) with scrollable sections; consumes `GET /api/links` `{categories}` shape
- 2026-07-22: Extension distribution — individual files uploaded to `pcm-compass/` subfolder, ZIP + docs in root of Nextcloud share
- 2026-07-21: Extension v2.1.0 — tab reuse, offline quick links, SVCP portal link
- 2026-07-21: Dockerfile updated — includes browser_extension/, runs build script during Docker build
- 2026-07-21: docker-compose.yml — mounts static/dist/ for persistent extension packages
- 2026-07-20: Project restructured — monolithic app.py split into Flask app factory, config module, core utilities, and feature blueprints under modules/
- 2026-07-20: Chrome extension rewritten — renamed from "NWU Quick Links" to "PCM Compass" v2.0.0 with three tool sections (Printer Search, User Lookup, Quick Links), chrome.storage for app URL, and autocomplete history
- 2026-07-20: Dockerfile updated — removed legacy workbook_url.txt COPY, updated for new directory structure
- 2026-07-20: Grouper module rewritten — from URL builder to authenticated proxy with Basic Auth and HTML parsing
- 2026-07-20: IDM module rewritten — from URL builder to authenticated proxy with form POST auth and HTML parsing
- 2026-07-20: Grouper template updated — in-page results display with error handling for badRole
- 2026-07-20: IDM template updated — in-page results display with fallback for IDM-specific passwords
- 2026-07-21: Dashboard and nav consolidated — removed old IDM Lookup and Grouper entries, single User Lookup entry

### Removed
- 2026-07-21: Deleted `modules/idm_lookup/` — replaced by user_lookup URL builder
- 2026-07-21: Deleted `modules/grouper/` — replaced by user_lookup URL builder
- 2026-07-21: Deleted `templates/idm_lookup.html` and `templates/grouper.html`
- 2026-07-21: Deleted `core/http_client.py` — no authenticated proxy
- 2026-07-21: Deleted `browser_extension/settings.html` — options_page removed from manifest
- 2026-07-21: Removed `cryptography` dependency from requirements.txt
- 2026-07-21: Removed AES-GCM credential encryption from `core/auth.py` (kept bcrypt admin auth)

### Fixed
- 2026-08-03: Extension tab reuse for IDM/Grouper/printer search — Chrome match patterns can't match query strings, so reuse now matches path prefixes and navigates in place (no duplicate tabs)
- 2026-07-22: Extension tab navigation — IDM/Grouper buttons now pass real URLs to `chrome.tabs.create()` instead of wildcard patterns
- 2026-07-22: Docker build — added `zip` package to production image, made Nextcloud upload optional (skipped when curl unavailable)
