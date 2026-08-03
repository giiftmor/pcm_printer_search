# Quick Links Categorization — Design Spec

**Date:** 2026-08-03
**Status:** Approved
**Author:** opencode + user

## Overview

PCM Compass's Quick Links module currently stores a flat list of `{id, name, url, icon}` objects in `quick_links.json`. As the helpdesk's portal inventory grows (NAC, Omnia, SCSM, Entra, Scopserve, PaperCut), a flat grid is no longer usable. This change introduces **category groups** so links are organized, navigable, and admin-manageable in both the Flask dashboard and the Chrome extension.

## Goals

- Group quick links into categories (two-level hierarchy: category → links)
- Replace the current 4-default seed set with the full helpdesk link inventory
- Categories are admin-manageable (add/remove), links are admin-manageable within categories
- Same grouping shown consistently in web UI and extension popup
- Backwards-compatible: legacy flat data auto-migrates to a single "General" category
- No regression to existing endpoints; extension keeps offline fallback

## Category Scheme (final)

| Category | Links |
|----------|-------|
| **Portals** | SCSM Support Portal, Scopserve |
| **Printing** | SVCP Portal, PaperCut Admin Portal |
| **Identity** | IDM, Grouper, Microsoft Entra |
| **SIS (Omnia)** | Omnia Password Reset, Omnia Profile Overview |
| **NAC** | MAN NAC, NAC 1 Campus B LAN, NAC 1 Campus B WIFI, NAC 2 Campus A LAN, NAC 2 Campus A WIFI |

Full seed inventory (13 links):

| Name | URL | Icon |
|------|-----|------|
| SCSM Support Portal | `https://support.nwu.ac.za/View/HomePage#/` | 🎫 |
| Scopserve | `http://143.160.36.111:5555/reports/telephony.php` | 📞 |
| SVCP Portal | `https://svcp.nwu.ac.za` | 🖨️ |
| PaperCut Admin Portal | `http://v-pcut-win1.nwu.ac.za:9191/app` | 🖨️ |
| IDM | `https://idm.nwu.ac.za` | 👤 |
| Grouper | `https://grp.nwu.ac.za/grouper/` | 👥 |
| Microsoft Entra | `https://entra.microsoft.com/#home` | 🪪 |
| Omnia (SIS Password Reset) | `https://omnia.nwu.ac.za/omnia/send_sis_password_info` | 🔑 |
| Omnia (SIS Profile Overview) | `https://omnia.nwu.ac.za/omnia/get_sis_provisioning_info_page` | 📋 |
| MAN NAC | `https://196.252.138.240:8443/gui/hosts/view` | 🌐 |
| NAC 1 (Campus B) LAN | `https://196.252.138.242:8443/gui/hosts/adapters` | 🏛️ |
| NAC 1 (Campus B) WIFI | `https://196.252.138.241:8443/gui/hosts/view` | 📶 |
| NAC 2 (Campus A) LAN | `https://196.252.138.243:8443/gui/hosts/adapters` | 🏛️ |
| NAC 2 (Campus A) WIFI | `https://196.252.138.244:8443/gui/hosts/view` | 📶 |

## Data Model

```json
{
  "categories": [
    {
      "id": "uuid",
      "name": "NAC",
      "links": [
        { "id": "uuid", "name": "MAN NAC", "url": "https://196.252.138.240:8443/gui/hosts/view", "icon": "🌐" }
      ]
    }
  ]
}
```

- Top-level key changes from `{"links": [...]}` to `{"categories": [...]}`.
- Category `id` and link `id` are both `uuid4` strings (matches existing convention).
- NAC's 3-level mental hierarchy (NAC → Campus → LAN/WIFI) flattens to category "NAC" with descriptive link names.

## Backwards Compatibility

`engine._load()` detects the legacy shape (`"links"` key present, no `"categories"` key) and wraps them in a single category `"General"` at read time. The file is left untouched on read (no implicit rewrite) unless a mutation occurs — on any subsequent save, the data is persisted in the new grouped shape. Seed defaults use the new shape when no file exists.

## API

### `GET /api/links`
Returns grouped structure:
```json
{ "categories": [ { "id": "...", "name": "Portals", "links": [ ... ] } ] }
```

### `POST /api/links` (admin)
Creates a link. Request body (JSON): `{ "category_id": "<uuid>", "name": "...", "url": "...", "icon": "..." }`.
- `category_id` is required — link is appended to that category.
- 400 if `category_id` missing/unknown or `name`/`url` missing.
- 201 with the created link on success.

### `DELETE /api/links/<link_id>` (admin)
Removes a link by its id (unchanged behavior, now scoped by category search).

### `POST /api/links/categories` (admin) — new
Creates a category. Body: `{ "name": "..." }`. 201 with created category.

### `DELETE /api/links/categories/<category_id>` (admin) — new
Removes an empty category. 409 if it still contains links (prevents orphaned data). 200 on success.

## Web UI (`templates/quick_links.html`)

- `linksGrid` renders **one section per category**: category heading + a grid of link cards.
- Admin "Add Link" form: existing Name/URL/Icon fields **plus a category `<select>`** populated from `GET /api/links` categories.
- Admin section gains a category manager: add-category input + delete button per category (delete disabled/blocked when non-empty, surfaced via 409 message).
- Remove-link buttons remain per-card (admin only), unchanged styling.

## Extension (`browser_extension/popup.js`, `popup.html`, `popup.css`)

- `DEFAULT_LINKS` restructured to the same category scheme (offline fallback identical to server seed).
- `renderLinks()` renders sections: category header + links in the `links-grid`; `popup.html` keeps a single `#quickLinks` container.
- The Quick Links area is **scrollable** (`max-height` + `overflow-y: auto`) because 13 links make the popup tall.
- All other popup sections (Printer Search, User Lookup) unchanged.

## Error Handling

- Non-admin calls to POST/DELETE endpoints return 403 (existing `admin_required`).
- Deleting a non-empty category returns 409 with a JSON message.
- Unknown `category_id` on link POST returns 400.
- Extension quick-links fetch failure falls back to `DEFAULT_LINKS` (existing behavior, now grouped).

## Testing

- **engine.py**: legacy→grouped migration on read; seed defaults grouped; add/remove link by category; add category; remove empty category; remove non-empty category raises/returns error; persistence round-trip.
- **routes.py**: grouped GET; POST link with/without `category_id` (400); POST category; DELETE empty (200) and non-empty (409) category; unauthenticated writes → 403.
- **urls.py / printer_search / user_lookup**: unaffected — regression check only.

## Out of Scope

- Ordering/reordering of links within a category (append-only for now).
- Nested (3-level) categories.
- Per-user link preferences.
- Changes to IDM/Grouper/Printer Search modules.

## Files

- Modify: `modules/quick_links/engine.py`
- Modify: `modules/quick_links/routes.py`
- Modify: `templates/quick_links.html`
- Modify: `browser_extension/popup.js`
- Modify: `browser_extension/popup.css`
- Modify: `quick_links.json` (reseed)
- Modify: `major-improvements-implementation-status.md` (add Stream 0 item)
- Modify: `CHANGELOG.md`, `~/projects/tailnet-changelog/CHANGELOG.md`
- Add: tests for engine + routes
