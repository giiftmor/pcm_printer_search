# PCM Compass — SCSM Search UI/UX Improvements Design

Date: 2026-08-11
Status: Approved (companion mockup session)
Predecessor: `docs/superpowers/specs/2026-08-10-scsm-search-compass-integration-design.md` (the live page this refines). This spec covers **UI/UX improvements to the SCSM Search page** plus the small scsm-search backend additions they require.

## 1. Purpose

The SCSM Search page shipped per the Aug-10 spec works, but the desk wants tighter visual design and easier scannability:

1. **Result list spacing** — rows feel cramped compared to the airy mockup; increase padding and breathing room.
2. **Ticket type as abbreviations** — render `SR` / `IR` (from `servicerequest` / `incident`) as `<abbr>` chips instead of the full `SERVICEREQUEST` / `INCIDENT` (and the current fallback `TICKET` chip).
3. **Color to distinguish status and ticket type** — color-coded type chips (SR vs IR) and status badges (Active/Resolved/Closed/Pending/Cancelled).
4. **Remove the portal URL from result rows** — show it only in the detail pane.
5. **Detail pane: four separate containers** for readability — ① header (type + title + status + link), ② users, ③ dates (created / resolved / closed), ④ the work searched (Description/ResolutionDescription body).
6. **Fix the missing `ticketType` bug** — search-result rows currently never carry `ticketType` (the search projection omits it and `enrich_rows` only builds the URL), so the chip falls back to the generic `TICKET`. Rows must be stamped with their type.

**Non-goals:** no new libraries, no extension changes, no admin features, no changes to the API *contract* beyond adding additive fields.

## 2. Locked Design (approved in companion)

Full mockup: `.superpowers/brainstorm/2055392-1786434065/content/proposed-redesign.html` (also `current-layout.html` for the "as-is" reference).

### 2.1 Result list (master pane)

- Row padding bumped from `.6rem .8rem` to `.9rem .9rem`; snippet gains `.4rem` top margin and a flex-wrap meta line.
- Title line: type `<abbr>` chip + `workItemId` (green) + `· title`.
  - **SR** chip: NWU green `#006633` on white text, rounded `4px`, letter-spaced.
  - **IR** chip: amber `#b26a00` on white text, same shape.
  - `<abbr title="Service Request">SR</abbr>` / `<abbr title="Incident">IR</abbr>` (accessibility: real abbreviation semantics).
- Meta line (replaces the removed URL line + old snippet): a **status badge** plus `Affected: X · Created by: Y · date`.
  - Status badge colors (light bg / dark text): `Active` = green (`#e6f4ec`/`#006633`), `Resolved` = blue (`#e7eefb`/`#2b5a9e`), `Closed` = gray (`#eef0f2`/`#8b949e`), `Pending` = gray, `Cancelled` = red, **unknown status** → neutral gray. Case-insensitive match.
- **Portal URL removed** from result rows entirely (was `.scsm-url` on each row).

### 2.2 Detail pane (four containers)

Each container is a bordered, rounded box (`1px #e6e9ec`, `8px` radius, `.8rem` padding) stacked with `.8rem` gaps.

1. **Header** — type `<abbr>` chip + workItemId (bold) + title, status badge aligned right, and an `Open in SCSM ↗` button.
2. **Users** — Affected / Created by / Assigned to (clickable person buttons preserved — they drill into that user's relationship tabs).
3. **Dates** — Created / Resolved / Closed, rendered from `createdDate` / `resolvedDate` / `closedDate` (absent fields render as `—`).
4. **Work** — the ticket `description` body; **fallback** to `resolutionDescription` when description is empty; `—` when both are absent.

## 3. Data / Backend Changes

### 3.1 scsm-search API (additive; existing consumers unaffected)

Verified real columns exist on both `CiresonAnalytics.dbo.SM_WorkItem_Incident` and `SM_WorkItem_ServiceRequest`: `Description`, `ResolutionDescription`, `ResolvedDate`, `ClosedDate` (confirmed by public Cireson queries and Microsoft DW schema).

- **`src/db/queries/tickets.ts` → `ticketColumns()`:** add `Description, ResolutionDescription, ResolvedDate, ClosedDate` to both the SR and Incident projections (both kinds). This flows into `/v1/search/tickets`, `/v1/users/:id/tickets`, and the count queries need no change.
- **`src/types/ticket.ts`:**
  - `TicketRow` gains `Description: string | null; ResolutionDescription: string | null; ResolvedDate: Date | string | null; ClosedDate: Date | string | null`.
  - `TicketResult` gains `description: string | null; resolutionDescription: string | null; resolvedDate: string | null; closedDate: string | null`.
- **`src/serializers/ticket.ts`:** map the new fields (ISO string for dates, `null` passthrough).
- **Tests (`tests/queryBuilders-tickets.test.ts`, `tests/routes-search.test.ts`, `tests/queryBuilders-users.test.ts`, `tests/routes-users.test.ts`):** assert the new projection columns and the new response fields.

### 3.2 PCM Compass

- **`modules/scsm_search/engine.py` → `enrich_rows()`:** stamp `ticketType` on every row (`out["ticketType"] = ticket_type or out.get("ticketType")`) so search results carry their type for the SR/IR chips. Keep row-level `ticketType` (from `/v1/users/:id/tickets`) winning when present.
- **`modules/scsm_search/routes.py`:** no change (passes through new fields automatically).
- **`templates/scsm_search.html`:** per Section 2. Vanilla JS additions:
  - Type-abbr map: `{incident: 'IR', servicerequest: 'SR'}` with `title` text.
  - Status color map (Section 2.1) with neutral fallback.
  - Render the four detail containers; wire the resolved/closed date fields; description→resolution fallback.
  - Remove URL rendering from result rows.
- **Tests (`tests/test_scsm_search_engine.py`, `tests/test_scsm_search_routes.py`):** `enrich_rows` stamps `ticketType`; route responses include description/resolved/closed fields.

## 4. Configuration

No new env keys. `SCSM_API_URL`, `SCSM_API_KEY`, `SCSM_PORTAL_BASE` unchanged.

## 5. Testing Plan

- **scsm-search repo:** `npm test` (query builder + serializer + route suites).
- **Compass repo (pcm-test image):** `python -m pytest -p no:cacheprovider -q tests/test_scsm_search_engine.py tests/test_scsm_search_routes.py tests/test_scsm_search_page.py`.
- **Manual smoke:** run `app.py` in dev, search a ticket ID, verify: SR/IR abbr chips, status colors, no URL in rows, 4-container detail with all three dates, work body; click a person → tabs still work.

## 6. Risks

1. **Description can be long** — Work container uses `line-height 1.5` and normal wrapping; no truncation. Fine for desk use.
2. **Warehouse refresh cadence** — `ResolvedDate`/`ClosedDate` are as stale as the 24h warehouse refresh; accepted (same as existing data).
3. **Unknown statuses** — any status string outside the map renders neutral gray (safe default, never breaks layout).
4. **`ticketType` stamping changes chip output** — a genuine bugfix; the generic `TICKET` chip disappears in favor of correct SR/IR.

## 7. Scope Rollup

- **In:** scsm-search additive columns/fields + tests; Compass `enrich_rows` ticketType fix + test; SCSM Search page result-list + detail-pane redesign; page tests.
- **Out:** extension changes, admin UI, new filters, mobile layouts, API behavior changes.
