# PCM Compass — Design Spec

**Date:** 2026-07-20
**Status:** Approved
**Author:** opencode + user

## Overview

PCM Compass is a multi-functional IT service desk toolkit for NWU PCM (Potchefstroom) staff. It replaces the existing PCM Printer Search project with a modular dashboard application and Chrome extension.

**Project rename:** `pcm_printer_search` → `pcm-compass`

## Goals

- Consolidate daily IT desk tools into one place
- Dashboard-style web app (Flask) as primary interface
- Chrome extension as quick-access launcher
- Focus on functionality, security, and usability
- Modular architecture — each tool is self-contained

## Architecture

```
┌─────────────────────────────────────┐
│  Flask Web App (Primary UI)         │
│  ┌───────┐ ┌───────┐ ┌──────────┐  │
│  │Printer│ │IDM    │ │Grouper   │  │
│  │Search │ │Lookup │ │Groups    │  │
│  └───┬───┘ └───┬───┘ └────┬─────┘  │
│      │         │           │        │
│  ┌───┴─────────┴───────────┴─────┐  │
│  │     Core Engine / API Layer   │  │
│  └───────────────────────────────┘  │
└──────────────┬──────────────────────┘
               │ shared APIs
┌──────────────┴──────────────────────┐
│  Chrome Extension (Quick Access)    │
│  Popup with tool sections           │
│  Opens external NWU services        │
└─────────────────────────────────────┘
```

## Modules

### 1. Printer Data Search (existing — refactored)

- **Source:** Excel file from Nextcloud (auto-reloads every 60s)
- **Search:** hostname, serial, MAC, or any field content
- **Flask API:** `POST /api/printer/search`, `GET /api/printer/last-update`
- **Admin:** URL management, data reload, record CRUD
- **Extension:** Input field → opens web app with `?q=` parameter

### 2. IDM User Lookup (new)

- **Input:** NWU user ID (e.g. `31408362`)
- **Action:** Opens IDM profile page in new browser tab
- **URL pattern:** `https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Consolidation&USN={user_id}`
- **Auth:** Browser-native form login (no credentials stored in extension or Flask)
- **Extension:** Shared input with Grouper, two action buttons
- **Flask:** Redirect/route that constructs and opens the URL

### 3. Grouper Group Lookup (new)

- **Input:** NWU user ID (e.g. `31408362`)
- **Action:** Opens Grouper subject summary page in new browser tab
- **URL pattern:** `https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?id={user_id}&typeName=person&subjectId={user_id}&name={user_id}&subjectType=person&sourceId=NWUSource0`
- **Auth:** Browser-native HTTP Basic Auth dialog (no credentials stored)
- **Extension:** Shared input with IDM, second action button
- **Flask:** Redirect/route that constructs and opens the URL

### 4. Quick Links / Portal Launcher (new)

- **Configurable links** to SVCP portals, PaperCut admin, and other NWU tools
- **Extension:** Button bar with quick-launch links
- **Web app:** Dashboard card with link grid
- **SVCP pattern:** `https://{hostname}.svcp.nwu.ac.za`
- **Admin:** Add/edit/remove links via Flask admin panel

## Chrome Extension

### Popup Layout

```
┌──────────────────────────────┐
│  PCM Compass          [⚙️]   │
├──────────────────────────────┤
│  ┌────────────────────────┐  │
│  │ Printer Search          │  │
│  │ [hostname/serial____]  │  │
│  │ [Search] [Open App]    │  │
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │ User Lookup             │  │
│  │ [user ID___________]   │  │
│  │ [IDM Profile]          │  │
│  │ [Grouper Groups]       │  │
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │ Quick Links             │  │
│  │ [SVCP] [PaperCut] [+]  │  │
│  └────────────────────────┘  │
└──────────────────────────────┘
```

### Settings Page

- Flask App URL (e.g. `https://compass.nwu.ac.za`)
- Quick Links management (add/edit/remove)

### Storage

- `chrome.storage.local`: Flask URL, search history, quick links
- No NWU credentials stored — both IDM and Grouper use browser-native auth
- Autocomplete history for hostname and user ID fields (max 10 each)

### Manifest (MV3)

```json
{
  "manifest_version": 3,
  "name": "PCM Compass",
  "version": "2.0.0",
  "description": "Quick access to NWU PCM IT Service Desk tools",
  "permissions": ["tabs", "activeTab", "storage"],
  "host_permissions": [
    "*://*.nwu.ac.za/*",
    "http://localhost:5000/*",
    "http://196.252.43.75:5000/*"
  ]
}
```

## Flask App Structure

```
pcm-compass/
├── app.py                  # Flask app factory, config, middleware
├── config.py               # Settings (env vars, defaults)
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── .env.example
│
├── core/
│   ├── __init__.py
│   ├── auth.py             # Admin session management
│   └── http_client.py      # Shared requests wrapper (future use)
│
├── modules/
│   ├── __init__.py
│   ├── printer_search/
│   │   ├── __init__.py
│   │   ├── routes.py       # /api/printer/search, /api/printer/admin/*
│   │   └── engine.py       # Excel loading, parsing, search logic
│   │
│   ├── idm_lookup/
│   │   ├── __init__.py
│   │   ├── routes.py       # /api/idm/lookup → constructs IDM URL
│   │   └── engine.py       # URL construction, validation
│   │
│   ├── grouper/
│   │   ├── __init__.py
│   │   ├── routes.py       # /api/grouper/lookup → constructs Grouper URL
│   │   └── engine.py       # URL construction, validation
│   │
│   └── quick_links/
│       ├── __init__.py
│       ├── routes.py       # /api/links, /api/links/admin
│       └── engine.py       # Link storage (JSON file), CRUD
│
├── templates/
│   ├── base.html           # Dashboard shell (sidebar, header, NWU branding)
│   ├── dashboard.html      # Main dashboard / home
│   ├── printer_search.html
│   ├── idm_lookup.html
│   ├── grouper.html
│   └── quick_links.html
│
└── static/
    ├── css/
    │   └── compass.css     # NWU green branding, dashboard layout
    ├── js/
    │   └── compass.js      # Shared JS (auth, nav, API calls)
    └── img/
        └── nwu-logo.png
```

## Security Model

| Component | Auth Method | Storage |
|-----------|------------|---------|
| IDM Lookup | Browser-native form login | No credentials stored |
| Grouper Groups | Browser-native HTTP Basic Auth | No credentials stored |
| Flask Admin | Password (bcrypt-hashed) | Server-side session |
| Extension | No auth needed | Only Flask URL + local history |

**Key security decisions:**
- NWU credentials never touch our code — users authenticate directly with NWU services
- Flask admin password hashed with bcrypt
- Session-based auth for admin (Flask `session` with secure cookies)
- Extension stores only non-sensitive data (URLs, history, links)
- HTTPS required for production deployment

## Deployment

- **Docker Compose** (existing pattern)
- Flask behind reverse proxy for HTTPS
- Extension distributed as unpacked for internal use
- Health check: existing pattern (Python urllib check)
- Port: 5000 (configurable via env)

## Tech Stack

**Backend:**
- Python 3.11, Flask, Pandas, openpyxl, Gunicorn, Docker
- `python-dotenv` for env config
- `bcrypt` for admin password hashing (future hardening)

**Frontend:**
- Server-rendered HTML (Jinja2 templates)
- Vanilla JS for interactivity
- NWU green branding in CSS

**Extension:**
- Chrome Extension Manifest V3
- Vanilla JS (no frameworks)
- `chrome.storage.local` for settings/history

## File Rename Plan

| Old | New |
|-----|-----|
| `pcm_printer_search/` | `pcm-compass/` |
| `app.py` (monolith) | `app.py` + `core/` + `modules/` |
| `browser_extension/` | `browser_extension/` (same) |
| `templates/index.html` | `templates/base.html` + per-module templates |
| Docker image name | `pcm-compass` |

## Implementation Order

1. **Rename & restructure** — rename project, create module structure, move existing code
2. **Base dashboard** — `base.html` with sidebar nav, NWU branding, CSS
3. **Printer Search module** — refactor existing code into `modules/printer_search/`
4. **IDM Lookup module** — new route + template
5. **Grouper Lookup module** — new route + template
6. **Quick Links module** — configurable link storage + display
7. **Chrome extension** — redesign popup, add user lookup section
8. **Polish & test** — end-to-end testing, Docker build verification
