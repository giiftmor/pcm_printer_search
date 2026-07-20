# Changelog

## [Unreleased]

### Added
- 2026-07-20: PCM Compass design spec — multi-functional IT helpdesk toolkit with Flask dashboard + Chrome extension
- 2026-07-20: Dashboard base template (base.html, dashboard.html) with sidebar nav, NWU green branding, and 4 tool cards
- 2026-07-20: Shared CSS (compass.css) and JS (compass.js) for dashboard UI
- 2026-07-20: IDM lookup module — URL construction engine, API endpoint, and template
- 2026-07-20: Printer search module — Excel data engine with search and admin routes
- 2026-07-20: Grouper lookup module — URL construction engine with validation
- 2026-07-20: Quick links module — JSON file storage with CRUD API and dashboard cards
- 2026-07-20: Chrome extension settings.html — dedicated options page for Flask URL config
- 2026-07-20: Flask page routes blueprint (templates/routes.py) for dashboard, printer search, IDM, grouper, quick links

### Changed
- 2026-07-20: Project restructured — monolithic app.py split into Flask app factory, config module, core utilities, and feature blueprints under modules/
- 2026-07-20: Chrome extension rewritten — renamed from "NWU Quick Links" to "PCM Compass" v2.0.0 with three tool sections (Printer Search, User Lookup, Quick Links), chrome.storage for app URL, and autocomplete history
- 2026-07-20: Dockerfile updated — removed legacy workbook_url.txt COPY, updated for new directory structure

### Fixed
- 2026-07-20: Removed legacy monolithic templates/index.html (replaced by dashboard.html and module-specific templates)
