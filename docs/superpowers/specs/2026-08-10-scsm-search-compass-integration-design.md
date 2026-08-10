# PCM Compass — SCSM Search Integration Design

Date: 2026-08-10
Status: Approved (design review, companion mockup session)

Predecessor: `docs/superpowers/specs/2026-08-06-scsm-search-service-design.md` — the scsm-search API service spec (already built and live at `http://scsm-search:3000`). This spec covers the **PCM Compass side**: the Flask module + page that consumes that API, plus the **scsm-search backend additions** it needs.

## 1. Purpose

Give the NWU PCM IT Service Desk a ticket + user search over SCSM data from inside the existing PCM Compass dashboard. The desk already has a live read-only search API (`scsm-search`). This work builds the Compass page that consumes it, and adds the small backend capabilities the page needs (ticket-number search, created-by / assigned user fields, per-role "other tickets").

**Non-goals (this batch):** Chrome extension changes, any direct SQL access from Flask, SCSM portal screen-scraping, admin CRUD on the API, n8n consumption of the new endpoints.

## 2. Pinned UI Design (approved 2026-08-10)

The page is a **split-pane agent workspace** (master-detail, as used by Zendesk Agent Workspace, ServiceNow Workspaces, and modern email clients), with a **search-engine-style result set + relationship tabs** layered on top. Full mockups persisted under `.superpowers/brainstorm/1486298-1786388298/content/` (`workspace-split.html`, `search-engine-tabs.html`).

```
┌──────────────────────────────────────────────────────────────────────────┐
│ SCSM              [ Search by ticket ID, keyword, or user name… ]   ⌘K   │
├───────────────────────────────────────────────┬──────────────────────────┤
│ All results · Affected user 5 · Created by 12 ·│  IR1660031        SR      │
│ Assigned 3                                     │  [Open in SCSM ↗]        │
│───────────────────────────────────────────────│──────────────────────────│
│ SR1659403 · Printer driver installation       │  PC Print Mobility…      │
│ support.nwu.ac.za/ServiceRequest/Edit/SR1659403│                          │
│ Created by B. Jones · affected C. Naidoo · C… │  Affected   C. Naidoo     │
│                                               │  Created by B. Jones      │
│ IR1659976 · PC Print Mobility printer offline │  Assigned   B. Jones      │
│ …                                             │  Created    2026-07-28    │
│                                               │  Priority   Low           │
└───────────────────────────────────────────────┴──────────────────────────┘
```

### 2.1 Master pane (search + results)

- **Search bar** is a persistent, focusable **spotlight input** (`⌘K` / `/` to focus, arrow keys to move, Enter to open selection). Typing searches as-you-go; no submit button.
- **Results** render **Google-style**: title line (work item ID + title), a green location line (the SCSM portal URL), and a one-line snippet (affected · created-by · status · date).
- **Result totals** shown above the list (`24,888 results`).
- **Relationship tabs** (search-engine "Images / Shop / Map" pattern) appear **only when the search narrows to people** — i.e. after a ticket-ID lookup or after clicking a user within a result. Tabs: `Affected user (n)` · `Created by (n)` · `Assigned (n)`, plus an implicit `All results`. Clicking a tab refocuses the result list to that role's tickets for the identified user.
- Plain keyword search (`printer`) shows **no tabs** — just `All results`.

### 2.2 Detail pane (overview)

- Clicking any result (or Enter with it focused) **loads the ticket into the right-hand pane**. Selection updates in place; no navigation, no modal, no page reload.
- Detail shows: ticket type chip (IR/SR), work item ID, status, title, key-value field grid (Affected, Created by, Assigned to, Created, Priority, Source), and an **`Open in SCSM ↗`** button that opens the portal URL in a new tab.

### 2.3 Relationship tabs = "Other tickets"

The old "Other tickets" section (affected / created-by / assigned with dedup) is **promoted to first-class result sets** — they are the tabs. Selecting a tab swaps the master result list to that user's tickets. This is where the background fetch + cache feeds the tab counts and lists.

### 2.4 Delay model (progressive disclosure)

The primary action must never wait on related-ticket fetches. Timeline:

1. Ticket-ID search → primary ticket renders **immediately** (one fast API call).
2. Relationship tabs appear with **placeholder counts** (`Affected user · · ·`) — "data coming".
3. A background fetch starts per identified person (affected / created-by / assigned GUIDs), fetching **all pages** (`pageSize=100` loop) in a daemon thread into an in-process cache.
4. Counts populate as each role's fetch completes: `Affected user (5)` → `Created by (12)` → `Assigned (3)`. A tab becomes clickable the moment its count lands.
5. Clicking a tab mid-fetch shows what arrived + a "loading more…" note; completed fetches are served instantly from the 30-minute TTL cache.

## 3. Decisions Locked In

- **Flask proxies scsm-search; the API key stays server-side** in the Flask `.env` (`SCSM_API_KEY`). The browser never sees it. No extension change.
- **No server-side redirect** for the portal link — per-row `scsm_url` is built in Flask and the page opens it in a new tab (same pattern as user_lookup / printer svcp links).
- **scsm-search backend additions are in scope** (Section 5) — the page depends on them.
- **Cache:** in-process `dict` + `threading.Lock`, TTL 30 min, daemon-thread full-page fetch per (user GUID, role). gunicorn 4 workers → 4 process-local caches; accepted, no Redis.
- **Dedup of "Other tickets" tabs:** tabs are shown for a user only if that role has a resolved user with ≥1 ticket, subject to the dedup matrix in Section 4.3. Tab identity = resolved user GUID, so the three tabs can point at up to two distinct people.
- **Vanilla JS + Jinja + existing `compass.css`** conventions; NWU green `#006633`. Dark split-pane look from the mockup is adapted to the site's light theme unless the mockup's dark theme is adopted site-wide (decided at implementation; both approved in the mockup session).
- **No new external libraries** (no cmdk, no grid framework).

## 4. Data Flow

```
Browser  ── POST /api/scsm/tickets ──▶ Flask (proxy, X-API-Key header)
   │  ◀─────────────────────────────── API key stays here
   │                                   │ requests.with-retry
   ▼                                   ▼
scsm-search API  ──▶ SQL Server (CiresonAnalytics + ServiceManager)
```

### 4.1 Compass page flow (search)

1. User types in the spotlight bar → `/api/scsm/tickets?q=…` (proxy).
2. Proxy calls `scsm-search` `/v1/search/tickets` for both types (`incident` + `servicerequest`) with a shared `pageSize`, merges, sorts by `createdDate` desc, enriches each row with `scsm_url`, returns `{results, total, page}`.
3. Rows render in the master pane; the top row auto-selects into the detail pane.
4. If the query resolved to a single ticket ID, the page also identifies its users from the row's `affectedUser` / `createdByUser` / `assignedUser` and kicks off the background "other tickets" fetch (Section 4.2).
5. The detail pane's `Open in SCSM ↗` opens `row.scsm_url` in a new tab.

### 4.2 Background "other tickets" fetch + cache

- Keys: `(user_guid, role)` where role ∈ `{affected, created_by, assigned}`.
- `engine` daemon thread loops `pageSize=100` pages of `/v1/users/:id/tickets?role=…` until `page*pageSize >= total`, accumulating rows. On completion, stores `{rows, total, fetched_at}` in the cache with TTL 30 min.
- Per-key **in-flight** guard: if a key is already being fetched, other callers wait on the same result (no duplicate fetches).
- The tab count comes from `total` of the completed fetch; the tab list comes from cached `rows`.
- Failure: a role's fetch error marks that tab unavailable; it can be re-triggered on click.

### 4.3 Dedup matrix (which tabs to show)

Compare **resolved user GUIDs** from the primary ticket row:

| Role | Shown if |
|---|---|
| `affected` | always (when affectedUser present) |
| `created_by` | `created_by ∉ {affected, assigned}` |
| `assigned` | present (when assignedUser present) |

A tab counts toward the display only when it passes the matrix. So for a ticket where affected == created-by == assigned, only the `Affected user` tab shows.

## 5. scsm-search Backend Additions

Small, additive changes to the live service (all backward-compatible; existing consumers unaffected).

### 5.1 `q` matches `WorkItemId`

`/v1/search/tickets` `q` currently matches Title/Description/ResolutionDescription only. Add `WorkItemId` matching so `q=IR1660031` finds the ticket. Applied in both FTS and `like` modes:
- `like`: `OR WorkItemId LIKE '%' + @q + '%'`
- `fts`: also `CONTAINS(WorkItemId, @q)` (or treat pure-`IR/SR`-prefixed queries as exact `WorkItemId = @q` — decision at implementation, same contract).

### 5.2 Ticket response gains `createdByUser` and `assignedUser`

- SQL projection adds `CreatedByUser, CreatedByUserId, AssignedUser, AssignedUserId` (both kinds).
- `TicketResult` gains:
  ```ts
  createdByUser:  { id, displayName } | null
  assignedUser:   { id, displayName } | null
  ```
  (`affectedUser` unchanged.) `TicketRow` gains the four columns. Serializer updated. Priority stays nullable as-is.

### 5.3 `/v1/users/:id/tickets` gains `role`

- New optional query param `role` ∈ `affected` (default) | `created_by` | `assigned`.
- Selects the `WHERE` column accordingly: `AffectedUserId` / `CreatedByUserId` / `AssignedUserId`.
- Count query updated to match the same role column.
- Response rows already carry `ticketType`; each also gets `scsm_url` built client-side in Flask (not in the API).

### 5.4 Tests (scsm-search repo)

- `queryBuilders-tickets.test.ts`: WorkItemId matching (fts + like), new columns in both projections.
- `routes-search.test.ts`: `createdByUser` / `assignedUser` in response.
- `queryBuilders-users.test.ts` / `routes-users.test.ts`: `role` variants (each role column + count + default).

## 6. Compass Module Structure

```
modules/scsm_search/
  __init__.py        # Blueprint 'scsm'
  engine.py          # scsm_url building, proxy calls, related-tickets cache
  routes.py          # /api/scsm/... proxies
templates/scsm_search.html   # split-pane page (base.html)
tests/test_scsm_search.py    # pytest: url builder, dedup, cache, routes (mock)
```

### 6.1 `engine.py`

- `SCSM_PORTAL_BASE = 'https://support.nwu.ac.za'` (default; env `SCSM_PORTAL_BASE`).
- `_KIND_SEGMENT = {'incident': 'Incident', 'servicerequest': 'ServiceRequest'}`.
- `build_scsm_url(work_item_id, ticket_type) -> Optional[str]` — returns
  `f"{base}/{segment}/Edit/{work_item_id}/"` or `None` for unknown kind (mirrors `printer_search/svcp.py::build_svcp_url`).
- `enrich_rows(rows, ticket_type=None) -> list[dict]` — adds `scsm_url` per row; row-level `ticketType` (from `/v1/users/:id/tickets`) wins over a request-level `ticket_type`.
- **Cache class** `RelatedTicketsCache` (`dict` + `threading.Lock`): `get(key)`, `start_fetch(key)` in-flight guard, TTL 30 min, daemon-thread full-page fetch loop.
- `search_tickets(q, **filters)`, `search_users(q)`, `user_tickets(user_id, role)` — thin clients over `requests` with the `SCSM_API_KEY` header and short timeout, raising typed errors the routes map to HTTP codes.

### 6.2 `routes.py` (all under `/api/scsm/`, JSON)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/scsm/tickets` | Search tickets (`q`, optional `status`/`priority`/dates). Proxies both types, merges, enriches, returns `{results, total, page}`. |
| POST | `/api/scsm/users` | Search users (`q`). Returns `{results, total}`. |
| GET | `/api/scsm/users/<user_id>/tickets?role=…` | Role tickets for one user; uses cache when warm, else triggers background fetch and returns `{results, total, ready:false}` with what's loaded so far. |
| POST | `/api/scsm/related` | Given a ticket row (or ID), resolves the dedup matrix (Section 4.3), returns `{tabs:[{role,label,user,count}], primary}` and kicks off background fetches. |

Error mapping: scsm-search 401 → 502; network/timeout → 503; 404 passthrough; 400/500 passthrough with the upstream error shape.

### 6.3 `templates/scsm_search.html`

Split-pane layout per Section 2. Vanilla JS: spotlight focus (`⌘K`/`/`), arrow-key result navigation, fetch proxy endpoints, render master results (Google-style rows), swap detail pane, render relationship tabs with placeholder → count states, "loading more…" on mid-fetch tab click. Reuses `compass.css`; small page-scoped additions.

## 7. Configuration (Flask `.env`)

| Key | Default | Notes |
|---|---|---|
| `SCSM_API_URL` | `http://scsm-search:3000` | Internal network; override for dev |
| `SCSM_API_KEY` | *(required)* | One of the scsm-search `API_KEYS` |
| `SCSM_PORTAL_BASE` | `https://support.nwu.ac.za` | Do **not** probe/curl — behind SSO |

Compass uses `requests` with `X-API-Key: <key>` and a ~5s timeout per call. If `SCSM_API_KEY` unset → `/api/scsm/*` return 503 `SCSM_NOT_CONFIGURED`; page shows a config banner.

## 8. Testing (Compass repo, pytest via pcm-test image)

- **`test_build_scsm_url`** — IR/SR paths, unknown kind → None, trailing-slash form.
- **`test_enrich_rows`** — per-row `scsm_url`; row-level `ticketType` wins over request-level.
- **`test_dedup_matrix`** — all six combinations of affected/created-by/assigned identities.
- **`test_cache`** — TTL expiry, in-flight single-fetch, full-page accumulation (mocked upstream).
- **`test_routes`** — proxies forward the key header, map errors (200/503/502/404), `SCSM_NOT_CONFIGURED` when key missing (mock `requests`).
- scsm-search additions tested in that repo (Section 5.4).

## 9. Risks / Prerequisites

1. **scsm-search additions must land first** (Section 5) — the page's tabs depend on `createdByUser`/`assignedUser`/`role`. Ship scsm-search first, smoke live, then the Compass page.
2. **FTS catalog still pending** — `SEARCH_MODE=like` in use; WorkItemId matching must work in both modes.
3. **Portal link correctness** — rely on the desk-verified deep-link formats; never fetch `support.nwu.ac.za`.
4. **Process-local caches** — 4 gunicorn workers × 30-min TTL means a tab may occasionally refetch after a new request hits a cold worker; acceptable.
5. **PII** — only identification fields (name/GUID) cross the API; matches the service's existing shaping.

## 10. Scope Rollup

- **In:** scsm-search additive endpoints + tests; Compass `modules/scsm_search/` (engine, routes, template, tests); `.env.example` entries; dashboard nav entry + page route.
- **Out:** extension changes, admin CRUD, n8n wiring, Redis, portal scraping, mobile layouts.
