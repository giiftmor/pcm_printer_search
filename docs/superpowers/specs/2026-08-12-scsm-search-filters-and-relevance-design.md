# SCSM Search — Word-Based Matching, Filters, Relevance Ranking, Results Counter

Date: 2026-08-12

## 1. Overview

Improve the SCSM Search experience (Compass page `scsm_search.html` backed by the
`scsm-search` API) so that:

1. Search is **word-based**: every word in the query must appear somewhere in the ticket
   (AND across tokens, substring/contains per token) — not a single contiguous-phrase match.
2. **Tier/Queue and Location** are factored into *both* search matching and filters.
3. Results are ranked so that **adjacent** token matches are prioritized over scattered matches.
4. The page offers filters: **Tier/Queue dropdown**, **Status dropdown**, **Location text**,
   **date range (From/To)**, and a **sort** control (Relevance / Newest / A–Z).
5. The page shows a **results counter** equal to the number of rows actually rendered.
6. The **skeleton loader** occupies the full visible height of the results container.

## 2. Requirements

- Word-based matching (every word must appear). Matched fields: WorkItemId, Title,
  Description, ResolutionDescription, Tier/Queue, Location.
- Adjacent token matches ranked above scattered matches ("messy algorithm, we'll build it").
- Filters selected by the user: A-Z sort, Status, Date range, Tier/Queue, Location
  (search-by **and** filter).
- A-Z sort orders by **Title**.
- Location filter is a **text** filter (LIKE/contains), not a dropdown.
- Counter shows the number of rows **actually rendered on the page**.
- Skeleton loading list must occupy the whole visible size of the results container.

## 3. Data facts (verified against live `CiresonAnalytics`)

- `SM_WorkItem_Incident` (16,198 rows) and `SM_WorkItem_ServiceRequest` (24,672 rows)
  both have `Tier` (display-name text) and `TierId` (GUID).
- Tier values are service-desk queues: e.g. Incident = "Potch Staff Service Desk" (7,961),
  "Vaal Student Service Desk" (1,907), "Operations" (1,368), "Mafikeng Student Service Desk"
  (1,072), "Vaal Staff Service Desk" (910)… ~24 distinct incl. null. SR similar, ~23 distinct.
  → clean **dropdown filter** (exact match on `Tier`).
- CurrentLocation is custom per-kind text columns storing formatted
  `Campus – Building – Room` strings ("Vaal - VC - A21-105", "Mafikeng - MC\MC-A2F-G31 - G31"):
  - Incident: `CurrentLocation_DC52702B_4C6C_AE3D_56FA_5ED1522FDE0A` (3,041 distinct values,
    2,222 null, 54 empty)
  - ServiceRequest: `CurrentLocation_89125754_0643_0DA6_D2EB_50167E386A23`
  → **text filter** (contains), not a dropdown.
- Statuses: Incident = Closed / Active / Resolved / Pending / Canceled / User Comment (+ null);
  SR = Closed / In Progress / Completed / Submitted / On Hold / New.
- `Building` is a GUID, mostly sparse (n:1) — not used.

## 4. Design

### 4.1 Word-based matching (LIKE mode)

The deployed service runs `SEARCH_MODE=like` (`scsm-search/.env`). Today the LIKE branch
matches the **whole query string** as one substring (`Title LIKE '%'+@q+'%' OR …`). Change
it to tokenize on whitespace:

- `tokens = q.trim().split(/\s+/).filter(Boolean)`
- WHERE adds one OR-group per token:
  `(WorkItemId LIKE … OR Title LIKE … OR Description LIKE … OR ResolutionDescription LIKE … OR Tier LIKE … OR <LocationCol> LIKE …)`
  joined with `AND` across tokens.
- Each token is bound as its own parameter (`@tok0`, `@tok1`, …).
- **LIKE wildcard escaping**: user input is matched literally. Escape `\ % _ [` in each token
  and add `ESCAPE '\'` to every LIKE expression (new helper `escapeLike()` in `tickets.ts`).

FTS mode is unchanged (it already does `"word" AND "word"` via `CONTAINS`).

Location column mapping per kind:

| kind          | location column                                   |
|---------------|---------------------------------------------------|
| incident      | `CurrentLocation_DC52702B_4C6C_AE3D_56FA_5ED1522FDE0A` |
| servicerequest| `CurrentLocation_89125754_0643_0DA6_D2EB_50167E386A23` |

### 4.2 Relevance ranking (adjacent-first)

Applied in LIKE mode when `sort=relevance` (the default). Single-token queries have no
adjacency concept → keep `ORDER BY Created DESC`.

For n ≥ 2 tokens, define (generated in the SQL builder — token count is known at build time):

```
TEXT = ISNULL(Title,'') + ' ' + ISNULL(Description,'') + ' ' + ISNULL(ResolutionDescription,'')
POS_k   = NULLIF(CHARINDEX(@tok_k, TEXT), 0)
phrase  = tokens joined with a single space
```

Relevance (lower = better):

```
Relevance =
  CASE WHEN CHARINDEX(phrase, TEXT) > 0 THEN 0
  ELSE
    SUM over consecutive pairs k, k+1 of
      CASE WHEN POS_{k+1} IS NOT NULL AND POS_k IS NOT NULL AND POS_{k+1} > POS_k
           THEN POS_{k+1} - POS_k - LEN(@tok_k)     -- gap in chars; smaller = nearer
           ELSE 10000                               -- missing / out of order / duplicate
      END
  END
```

Notes:
- Phrase match (tokens contiguous, single space) → relevance 0 (top).
- In-order but separated tokens → small positive relevance (near-first).
- Missing from TEXT (matched only in WorkItemId/Tier/Location) or out of order → 10000+ (bottom),
  so content matches rank above ID/location-only matches. WorkItemId-only searches degrade to
  `ORDER BY Created DESC` because every row ties at the same relevance.
- Emitted as a SELECT alias `Relevance` and used in `ORDER BY Relevance ASC, Created DESC`.
  Not part of the public shape but serialized out (see 4.3) so the compass merge stays consistent.

### 4.3 scsm-search API changes

**Schema** (`src/schemas/searchParams.ts`):
- `tier: z.string().trim().max(100).optional()`
- `location: z.string().trim().max(200).optional()`
- `sort: z.enum(['relevance','newest','az']).default('relevance')`

**Queries** (`src/db/queries/tickets.ts`):
- `ticketColumns(kind)`: add `Tier` and the per-kind location column.
- `buildTicketWhere`: per-token OR-groups (4.1) + escaping; `tier` → `Tier = @tier`
  (exact); `location` → `<LocationCol> LIKE '%' + @location + '%' ESCAPE '\'` (contains).
  Filters apply to the data **and** count builders.
- `buildSearchTicketsQuery`:
  - `sort=az` → `ORDER BY Title ASC`
  - `sort=newest` → `ORDER BY Created DESC`
  - `sort=relevance` → SELECT `Relevance` alias (4.2) and `ORDER BY Relevance ASC, Created DESC`
- `buildCountTicketsQuery`: unchanged aside from shared WHERE (filters included, sort irrelevant).

**Types/serializer** (`src/types/ticket.ts`, `src/serializers/ticket.ts`):
- `TicketRow` gains `Tier: string | null`, `Location: string | null`, `Relevance?: number`.
- `TicketResult` gains `tier`, `location` (both `string | null`) and optional `relevance?: number`
  (present only when `sort=relevance`). `rowToTicket` maps them.

**Meta endpoint** — new `GET /v1/meta/filters` (new `src/routes/meta.ts`, registered in
`src/app.ts`; protected by the same API-key middleware):
- Returns `{ tiers: string[], statuses: string[] }`, distinct, nulls excluded, A–Z:
  `SELECT Tier … FROM incident UNION SELECT Tier … FROM SR …` (same for Status).
- Used to populate the Tier and Status dropdowns.

**Users** (`src/db/queries/users.ts`): same word-based AND across
`UserName`/`DisplayName`/`UPN` (per-token OR-groups, escaped). ORDER BY stays `DisplayName`
(already A–Z).

### 4.4 Compass proxy

- `engine.py search_tickets()`: add `tier`, `location`, `sort` to the passthrough key tuple
  (they arrive via `**filters`).
- `routes.py POST /tickets`: add `tier`, `location`, `sort` to the passthrough tuple.
- After merging incident + SR results, re-sort the merged list to match the chosen sort:
  - `relevance` → by `(relevance ?? MAX) asc, createdDate desc`
  - `newest` → by `createdDate desc`
  - `az` → by `title asc` (case-insensitive)
- Cache `/v1/meta/filters` at module level (TTL 60 min) to avoid re-hitting the API per page load.

### 4.5 Compass page UI (`scsm_search.html`, `compass.js`)

**Filter bar** — new row between the searchbar and tabs: Tier/Queue select, Status select,
Location text input, From/To date inputs, sort segmented control (Relevance · Newest · A–Z).
Any change re-runs `doSearch(q)` with the current filters. Tier/Status selects are populated
from `GET /api/scsm/meta/filters` (proxy pass-through); if meta fails, the Tier/Status
dropdowns are hidden (search still works).

**Results counter** — a new line under the searchbar (hidden when no query/error):
`N results` where N = number of rows actually rendered into `#scsm-results`
(`users.length + tickets.length` after `renderResults`, `rows.length` after
`renderRoleResults`). This is **not** the API total; the "All results (N)" tab count keeps
showing the total.

**Skeleton fills the container** — replace fixed `renderSkeletons(5)` / `renderSkeletons(3)`:
1. Render one probe skeleton row into `#scsm-results`.
2. `rowH = probe.offsetHeight || 68`.
3. `count = clamp(Math.ceil(resultsEl.clientHeight / rowH), 4, 40)`.
4. Re-render with `count` rows so the skeleton occupies the full visible area (no layout jump).
5. On window `resize` while skeletons are still active, re-run the fill (debounced).

### 4.6 Error handling

- Search errors: unchanged (status text). Counter hidden, skeletons replaced.
- Meta failure: dropdowns hidden; all other filters still work.
- `location`/`tier`/`sort` values flow through the same ScsmError handling as today.

## 5. Testing

**scsm-search** (`tests/queryBuilders-tickets.test.ts`):
- LIKE mode tokenizes: `q: 'printer jam'` → two OR-groups joined by `AND`, distinct params.
- Token OR-groups include `Tier` and the per-kind location column.
- Escaping: token containing `%`/`_`/`[` yields `ESCAPE '\'` and escaped param value.
- `tier` filter → `Tier = @tier`; `location` filter → contains on the location column.
- `sort=az` → `ORDER BY Title ASC`; `sort=relevance` → `Relevance` alias + `ORDER BY Relevance ASC,
  Created DESC`; `sort=newest` → `ORDER BY Created DESC`; single token + relevance → `Created DESC`.
- Count query includes tier/location filters.

**scsm-search** (`tests/routes-search.test.ts`):
- Pass-through of `tier`/`location`/`sort` as bound inputs.
- `GET /v1/meta/filters` returns tiers+statuses (new route test, fake pool).

**scsm-search** (`tests/queryBuilders-users.test.ts`): user search tokenizes per word.

**compass** (`tests/test_scsm_search_routes.py`, `test_scsm_search_engine.py`):
- POST `/tickets` forwards tier/location/sort; `search_tickets` maps them to query params.

Page render test stays as-is (counter/skeleton/filter bar are client-side; page test asserts
the page renders). Manual QA: skeleton fills viewport; counter matches rendered rows; filter
combos behave; adjacent-first ordering visible for multi-word queries.

## 6. Documentation

- `scsm-search/README.md`: document `sort`, `tier`, `location` params and `/v1/meta/filters`.
- `scsm-search/CHANGELOG.md` and `pcm-compass/CHANGELOG.md`: entries for this work.

## 7. Out of scope

- FTS-mode relevance ranking (FTS already ANDs words; ranking via `CONTAINSTABLE` RANK can come later).
- Pagination UI on the page (still top-25 per type, merged).
- Priority filter (not requested).
- Building/GUID-location resolution.

## 8. Changelog

- 2026-08-12: initial design (this doc).
