# Changelog

## [Unreleased]

### Added
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
- 2026-08-03: Extension popup quick links — grouped by category (`DEFAULT_CATEGORIES`) with scrollable sections; consumes `GET /api/links` `{categories}` shape
- 2026-07-22: Extension distribution — individual files uploaded to `pcm-compass/` subfolder, ZIP + docs in root of Nextcloud share
- 2026-07-21: Extension v2.1.0 — tab reuse, offline quick links, SVCP links
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
- 2026-07-22: Extension tab navigation — IDM/Grouper buttons now pass real URLs to `chrome.tabs.create()` instead of wildcard patterns
- 2026-07-22: Docker build — added `zip` package to production image, made Nextcloud upload optional (skipped when curl unavailable)
