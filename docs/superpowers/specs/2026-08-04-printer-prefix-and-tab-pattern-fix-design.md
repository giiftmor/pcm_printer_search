# Printer P- Prefix Detection + Tab Match Pattern Fix — Design

Date: 2026-08-04
Status: Approved

## Problem

1. **Bug:** `printerHostPattern()` in `browser_extension/popup.js` builds the Chrome tab match pattern from `new URL(appUrl).host`, which includes the port (e.g. `196.252.15.214:5000`). Chrome match patterns do **not** allow ports, so `chrome.tabs.query` throws `Invalid url pattern '*://196.252.15.214:5000/*'`.
2. **UX:** Desk staff expect to type a printer hostname **without** the `P-` prefix and have it used anyway (hostnames are stored as `P-…`). The input is also used to search serials/MACs/other columns, so prefixing must be detection-based, not blanket.

## Inventory scan (live workbook, 557 rows)

| Field | Shape | Matches hostname pattern? |
|-------|-------|---------------------------|
| Hostname | 98% start `P-`/`p-`; dominant `P-` + 4 letters + 1–2 digits; some 5+ letter; some junk/notes `(Replaced)`, `NAS-LOAN2`, `RNP…` | — |
| Serial | length 10–12, digits/mixed alnum | **0** matches |
| MAC | `xx:xx:xx:xx:xx:xx` | **0** matches |

## Hostname detection

After trim + strip trailing parenthetical notes (`\s*\(.*\)$`):

```
^(?i)(p-)?[a-z]{3,12}\d{1,3}$
```

- Matches clean stems: `BPKL2`, `P-BPKL2`, `IBAVL1`, `SNSL12` (~508/557 clean rows).
- Does NOT match serials (`0000000000`, `A000A000000`), MACs, locations, `RNP…` junk.
- Hyphenated names (`NAS-LOAN2`, `chm-1-001`) are **out of scope** for v1.

## Changes

### `browser_extension/url_helpers.js`
Add `normalizePrinterHostname(raw)`:
- `null` for non-strings / empty / non-hostname-shaped input (serials, MACs, junk).
- Otherwise return `P-` + stem (strip existing `p-`/`P-`, preserve stem case).

`buildSvcpUrl` unchanged (still mirrors `modules/printer_search/svcp.py`).

### `browser_extension/popup.js`
- **Fix:** `printerHostPattern()` uses `new URL(appUrl).hostname` (no port). Also harden `findOrCreateTab` to fall back to `tabs.create` if `tabs.query` throws on a bad pattern.
- **Search:** `q = normalizePrinterHostname(v) || v` — hostname-shaped input searches `P-{stem}`; serials/MACs pass through untouched.
- **Open SVCP:** only proceeds when `normalizePrinterHostname(v)` is non-null (prevents serial/MAC SVCP attempts); URL built via `buildSvcpUrl(P-{stem})`.

### Web UI
Unchanged (sheet hostnames already carry `P-`; search box left as-is per approved scope).

## Versioning

Extension bump **2.3.2 → 2.3.3**. Update `manifest.json`, `version.json`, `tests/test_status_version.py`, `browser_extension/changelog.html`, `CHANGELOG.md`, status doc. Deploy via `bin/build-extension.sh`.

## Testing

- Node (`tests/url_helpers.test.js`): `normalizePrinterHostname` cases — bare `BPKL2`→`P-BPKL2`, `p-ivdl4`→`P-ivdl4`, already-prefixed, serial/MAC/junk→null, note-stripping.
- Node guard (`tests/build_extension.test.js`) unaffected.
- pytest suite unchanged (Python untouched).
- Manual smoke: search `BPKL2`, serial, MAC; Open SVCP `BPKL2`; app URL with port no longer throws.
