# Changelog

## [Unreleased]

### Added
- 2026-07-21: User lookup API endpoint — `GET /api/user-lookup/urls` returning JSON with IDM and Grouper URLs
- 2026-07-21: User lookup module — URL builder with IDM consolidation, IDM password, and Grouper URL construction
- 2026-07-20: PCM Compass design spec — multi-functional IT helpdesk toolkit with Flask dashboard + Chrome extension
- 2026-07-20: Dashboard base template (base.html, dashboard.html) with sidebar nav, NWU green branding, and 4 tool cards
- 2026-07-20: Shared CSS (compass.css) and JS (compass.js) for dashboard UI
- 2026-07-20: IDM lookup module — URL construction engine, API endpoint, and template
- 2026-07-20: Printer search module — Excel data engine with search and admin routes
- 2026-07-20: Grouper lookup module — URL construction engine with validation
- 2026-07-20: Quick links module — JSON file storage with CRUD API and dashboard cards
- 2026-07-20: Chrome extension settings.html — dedicated options page for Flask URL config
- 2026-07-20: Flask page routes blueprint (templates/routes.py) for dashboard, printer search, IDM, grouper, quick links
- 2026-07-20: AES-GCM credential encryption (core/auth.py) — encrypt_creds/decrypt_creds with PBKDF2 key derivation
- 2026-07-20: HTTP client wrapper (core/http_client.py) — shared requests with timeout and redirect control
- 2026-07-20: Authenticated Grouper proxy — Basic Auth on every request, badRole detection, HTML parsing
- 2026-07-20: Authenticated IDM proxy — form POST auth, JSESSIONID session reuse, error detection, HTML parsing
- 2026-07-20: Extension credential storage — AES-GCM encrypted passwords in chrome.storage.local with PIN
- 2026-07-20: Extension proxy integration — popup.js decrypts creds and calls Flask proxy API

### Changed
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
- 2026-07-21: Stripped AES-GCM encryption functions from `core/auth.py` (kept bcrypt admin auth)

### Fixed
- 2026-07-20: Removed legacy monolithic templates/index.html (replaced by dashboard.html and module-specific templates)
