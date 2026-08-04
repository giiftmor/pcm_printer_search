# Grouper Group Lookup — Design Spec

**Date:** 2026-08-04
**Status:** Approved
**Author:** opencode + user

## Overview

PCM Compass already opens a **Grouper person** (subject) page from `/user-lookup` (web) and the extension popup, using `populateSubjectSummary.do?…&typeName=person&sourceId=NWUSource`. The helpdesk now needs the same one-click convenience for **Grouper groups** — a limited, stable set of groups the desk uses daily, plus free-text lookup for anything else.

Grouper treats groups as subjects on the same `populateSubjectSummary.do` endpoint, with `typeName=group`, `subjectType=group`, and `sourceId=g:gsa`. A real example URL (for `nwu:groups:Adobe:Acrobat_fedID_users_include`) confirms the shape; **the group stem path alone is sufficient — no UUID is required** (verified with the user).

## Goals

- One-click open for 7 preset Grouper groups (web + extension)
- Free-text manual group lookup (stem or name) on both surfaces
- URL builder shared shape across Python and JS (kept in sync, like `svcp.py` ↔ `url_helpers.js`)
- No credentials stored — browser-native Grouper auth, same as today
- Person lookup (IDM/Grouper) unchanged
- Extension version bump to **2.3.0**

## URL Pattern

`buildGrouperGroupURL(groupName, description?)` — mirrors the verified example, minus the UUID:

```
https://grp.nwu.ac.za/grouper/populateSubjectSummary.do
  ?returnToLinkKey=subject.action.return-results
  &typeName=group
  &returnTo=%2FdoSearchSubjects.do
  &name={urlencode(groupName)}
  &subjectType=group
  &sourceId=g:gsa
  [&description={urlencode(description)}]   # optional short label
```

Rules:
- `groupName` trimmed; reject empty / whitespace-only (return null in JS, `None` in Python)
- All params URL-encoded (colon in `nwu:groups:…` → `%3A`)
- `description` optional, omitted when None/empty
- Existing **person** builder (`build_grouper_url` / `buildGrouperURL`) unchanged

## Preset Groups (single source of truth)

| id | label | name (stem) |
|----|-------|-------------|
| `papercut-staff` | Papercut Staff Include | `Papercut_pcm_staff_include` |
| `azure-staff` | Azure Staff | `nwu:groups:Azure:Azure_Include_Staff` |
| `ms-full-staff` | MS Full Staff License | `nwu:groups:mslicenses:msfed_include_full_staff_license` |
| `ms-activate` | MS Activate | `nwu:groups:mslicenses:ms_activate` |
| `azure-students` | Azure Students | `nwu:groups:Azure:Azure_Include_Students` |
| `acrobat` | Acrobat | `nwu:groups:Adobe:Acrobat_fedID_users` |
| `acrobat-include` | Acrobat Include | `nwu:groups:Adobe:Acrobat_fedID_users_include` |

- Stored as a hardcoded constant (not admin-CRUD — this is a small, stable list)
- Python source of truth: `modules/user_lookup/urls.py` `GROUPER_GROUP_PRESETS`
- Extension embeds the same list in `url_helpers.js` for offline use
- Assumption: Papercut stem is exactly `Papercut_pcm_staff_include` (no `nwu:groups:` prefix). Correct in one place if wrong.

## API

Two endpoints on the existing `user_lookup` blueprint:

1. `GET /api/user-lookup/grouper-presets`
   → `200 {"presets": [{"id", "label", "name", "url"}, …]}`
   URLs pre-built server-side for web rendering.

2. `GET /api/user-lookup/group-url?name=<stem>`
   - `name` present + non-empty → `200 {"url": "<built url>", "name": "<trimmed name>"}`
   - missing/empty → `400 {"error": "name is required"}`

## Web UI (`/user-lookup`)

Two cards stacked on the page:

1. **User Lookup** (unchanged) — input + IDM Consolidation / IDM Password / Grouper (person) buttons. Button label "Grouper" renamed to **Grouper User** for clarity.
2. **Grouper Groups** (new) —
   - Chip grid of 7 presets (short labels, NWU-green secondary style)
   - Input "Group path or name" + **Open** button
   - Enter key triggers Open
   - Click/Open → `window.open(url, '_blank', 'noopener,noreferrer')`
   - Presets loaded from `/api/user-lookup/grouper-presets`; manual URL from `/api/user-lookup/group-url`

## Extension Popup

New section **Grouper Groups** between User Lookup and Quick Links:

```
Grouper Groups
[Papercut Staff] [Azure Staff] [MS Full] [MS Activate]
[Azure Students] [Acrobat] [Acrobat Include]
[ input: group path or name  ]
[ Open ]
```

- Chip click / Open → `findOrCreateTab(url, { hostPattern: '*://grp.nwu.ac.za/*', pathPrefix: '/grouper/' })`
- Presets from embedded `GROUPER_GROUP_PRESETS` (offline-safe; no API dependency)
- Existing person **Grouper** button unchanged
- Manifest version → **2.3.0**

## Files

| Area | Touch |
|------|-------|
| `modules/user_lookup/urls.py` | `build_grouper_group_url` + `GROUPER_GROUP_PRESETS` |
| `modules/user_lookup/routes.py` | `grouper-presets` + `group-url` endpoints |
| `templates/user_lookup.html` | second card + chips + manual input |
| `static/css/compass.css` | chip styles (reuse existing classes where possible) |
| `browser_extension/url_helpers.js` | `buildGrouperGroupURL` + presets export |
| `browser_extension/popup.html` | Grouper Groups section |
| `browser_extension/popup.js` | chip rendering + open handlers + manual open |
| `browser_extension/popup.css` | section/chip styles |
| `browser_extension/manifest.json` | version → 2.3.0 |
| `tests/test_grouper_groups.py` | URL builder + route tests |
| `tests/url_helpers.test.js` | JS URL builder + presets tests |
| `CHANGELOG.md`, `AGENTS.md` | changelog + API table rows |

## Out of Scope

- Admin CRUD for group presets
- Grouper membership editing / group API
- UUID storage or lookup
- Changing the existing person Grouper URL builder
- History/autocomplete for group names (possible future nicety)

## Testing

- Unit (Python): URL encoding (`:` → `%3A`), empty/whitespace reject, each preset name builds correctly
- Route: presets 200 + shape; group-url 200 with name, 400 without
- Unit (node): JS builder mirrors Python; presets list matches Python count/names
- Manual: chip + free-text open real Grouper pages after browser auth
