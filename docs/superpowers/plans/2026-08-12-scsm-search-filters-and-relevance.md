# SCSM Search Filters & Relevance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add word-based matching, adjacency-prioritized relevance ranking, tier/location/status/date filters, an A–Z sort, a rendered-row results counter, and container-filling skeletons to the SCSM Search feature.

**Architecture:** The `scsm-search` API (Node/TS, `CiresonAnalytics` SQL Server) owns query building — tokenized word matching, Tier/Location filters, and a SQL-computed `Relevance` column that orders LIKE-mode results so adjacent token matches rank first. The `pcm-compass` Flask module proxies the new params, re-sorts the merged incident+SR list, caches a new `/v1/meta/filters` endpoint, and renders the filter bar, counter, and filling skeletons on the page.

**Tech Stack:** scsm-search: Node ≥22, TypeScript, Express 5, mssql, zod, `node --test` (run with `node --import tsx --test tests/*.test.ts` or `npm test`). pcm-compass: Flask, `pytest` (runs on host with `python3 -m pytest -p no:cacheprovider -q`), vanilla JS in `scsm_search.html`.

## Global Constraints

- Deployed search mode is `SEARCH_MODE=like` (`scsm-search/.env`). FTS mode must remain byte-for-byte unchanged in behavior.
- All user input goes through bound parameters — never inlined. New LIKE expressions MUST use `ESCAPE '\'` with values passed through `escapeLike()`.
- Location columns (verified live):
  - incident: `CurrentLocation_DC52702B_4C6C_AE3D_56FA_5ED1522FDE0A`
  - servicerequest: `CurrentLocation_89125754_0643_0DA6_D2EB_50167E386A23`
- `sort` values are exactly `relevance` (default) | `newest` | `az`. `az` orders by `Title ASC`; `relevance` only applies in LIKE mode with ≥2 tokens; single-token relevance queries keep `ORDER BY Created DESC`.
- Results counter shows the number of rows actually rendered into `#scsm-results` — NOT the API total. The "All results (N)" tab keeps showing the total.
- No new dependencies in either repo.
- Run `npm run build` (tsc) in scsm-search and the full pytest suite in pcm-compass after each task's code change.
- All work is committed per-task in the repo the task belongs to. Commit messages follow each repo's existing style (`feat:`, `docs:`, `fix:`).

---

## File Structure

**scsm-search (repo root: `/home/evo/projects/scsm-search`)**

- Create: `src/db/escapeLike.ts` — shared LIKE-wildcard escaper
- Create: `src/db/queries/meta.ts` — distinct Tier/Status query
- Create: `src/routes/meta.ts` — `GET /v1/meta/filters` route
- Create: `tests/escapeLike.test.ts`, `tests/routes-meta.test.ts`
- Modify: `src/schemas/searchParams.ts` — add `tier`, `location`, `sort`
- Modify: `src/types/ticket.ts` — add `tier`, `location`, `relevance`
- Modify: `src/serializers/ticket.ts` — map new fields
- Modify: `src/db/queries/tickets.ts` — columns, tokenized matching, filters, relevance/sort
- Modify: `src/db/queries/users.ts` — tokenized word matching
- Modify: `src/app.ts` — register `/v1/meta`
- Modify: `src/routes/search.ts` — no logic change (params flow via schema+builders)
- Modify tests: `tests/validation.test.ts`, `tests/queryBuilders-tickets.test.ts`, `tests/queryBuilders-users.test.ts`, `tests/routes-search.test.ts`
- Modify: `README.md`, `CHANGELOG.md`

**pcm-compass (repo root: `/home/evo/projects/pcm-compass`)**

- Modify: `modules/scsm_search/engine.py` — passthrough `tier`/`location`/`sort`, `fetch_filters()` + cache
- Modify: `modules/scsm_search/routes.py` — passthrough params, merge sort, `GET /meta/filters`
- Modify: `templates/scsm_search.html` — filter bar, counter line, skeleton CSS, JS
- Modify tests: `tests/test_scsm_search_engine.py`, `tests/test_scsm_search_routes.py`, `tests/test_scsm_search_page.py`
- Modify: `CHANGELOG.md`

Cross-repo interface: `POST /api/scsm/tickets` body gains `{tier?, location?, sort?}`; ticket JSON gains `tier`, `location`, `relevance?`; new `GET /api/scsm/meta/filters` returns `{tiers: string[], statuses: string[]}`.

---

### Task 1: Schema params + LIKE-escaping helper

**Files:**
- Create: `src/db/escapeLike.ts`
- Create: `tests/escapeLike.test.ts`
- Modify: `src/schemas/searchParams.ts`
- Modify: `tests/validation.test.ts`

**Interfaces:**
- Produces: `escapeLike(s: string): string` (escapes `\`, `%`, `_`, `[`). `ticketSearchParamsSchema` now parses `tier?: string`, `location?: string`, `sort: 'relevance'|'newest'|'az'` (default `'relevance'`). Later tasks consume `escapeLike` and the new schema fields.

- [ ] **Step 1: Write the failing test** — create `tests/escapeLike.test.ts`:

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { escapeLike } from '../src/db/escapeLike.js';

test('escapeLike leaves plain text untouched', () => {
  assert.equal(escapeLike('printer jam'), 'printer jam');
});

test('escapeLike escapes LIKE wildcards', () => {
  assert.equal(escapeLike('50%_ok['), '50\\%\\_ok\\[');
});

test('escapeLike escapes a backslash itself', () => {
  assert.equal(escapeLike('a\\b'), 'a\\\\b');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --import tsx --test tests/escapeLike.test.ts`
Expected: FAIL — module `../src/db/escapeLike.js` not found.

- [ ] **Step 3: Write minimal implementation** — create `src/db/escapeLike.ts`:

```ts
export function escapeLike(s: string): string {
  return s
    .replace(/\\/g, '\\\\')
    .replace(/%/g, '\\%')
    .replace(/_/g, '\\_')
    .replace(/\[/g, '\\[');
}
```

- [ ] **Step 4: Add schema fields** — in `src/schemas/searchParams.ts`, inside `ticketSearchParamsSchema` (after `assignedUserId`, before `from`):

```ts
  tier: z.string().trim().max(100).optional(),
  location: z.string().trim().max(200).optional(),
  sort: z.enum(['relevance', 'newest', 'az']).default('relevance'),
```

- [ ] **Step 5: Add validation tests** — append to `tests/validation.test.ts`:

```ts
test('ticket search: parses tier, location and sort', () => {
  const p = ticketSearchParamsSchema.parse({
    type: 'incident', tier: 'Potch Staff Service Desk', location: 'A21', sort: 'az',
  });
  assert.equal(p.tier, 'Potch Staff Service Desk');
  assert.equal(p.location, 'A21');
  assert.equal(p.sort, 'az');
});

test('ticket search: sort defaults to relevance', () => {
  const p = ticketSearchParamsSchema.parse({ type: 'incident' });
  assert.equal(p.sort, 'relevance');
});

test('ticket search: rejects unknown sort', () => {
  assert.throws(() => ticketSearchParamsSchema.parse({ type: 'incident', sort: 'bogus' }));
});
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npm test`
Expected: PASS (escapeLike tests + validation tests), all existing 99 tests still pass.

- [ ] **Step 7: Commit**

```bash
git add src/db/escapeLike.ts tests/escapeLike.test.ts src/schemas/searchParams.ts tests/validation.test.ts
git commit -m "feat: add tier/location/sort search params and LIKE-escape helper"
```

---

### Task 2: Serializer + types for tier/location/relevance

**Files:**
- Modify: `src/types/ticket.ts`
- Modify: `src/serializers/ticket.ts`
- Modify: `tests/queryBuilders-tickets.test.ts` (append rowToTicket tests)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `TicketRow` gains `Tier: string | null`, `Location: string | null`, `Relevance?: number`; `TicketResult` gains `tier: string | null`, `location: string | null`, `relevance?: number`. `rowToTicket(row)` populates them. Later tasks emit these columns/aliases from SQL.

- [ ] **Step 1: Write the failing test** — append to `tests/queryBuilders-tickets.test.ts`:

```ts
test('rowToTicket maps tier, location and relevance', () => {
  const row = {
    Id: 'a', WorkItemId: 'IR1', Title: 't', Status: 'Active', Priority: '2',
    CreatedDate: new Date('2026-07-01T09:00:00Z'), AffectedUser: null, AffectedUserId: null,
    Tier: 'Potch Staff Service Desk', Location: 'Vaal - VC - A21-105', Relevance: 3,
  };
  const t = rowToTicket(row);
  assert.equal(t.tier, 'Potch Staff Service Desk');
  assert.equal(t.location, 'Vaal - VC - A21-105');
  assert.equal(t.relevance, 3);
});

test('rowToTicket maps null tier/location and omits relevance when absent', () => {
  const row = {
    Id: 'a', WorkItemId: 'IR1', Title: 't', Status: 'Active', Priority: '2',
    CreatedDate: '2026-07-01', AffectedUser: null, AffectedUserId: null, Tier: null, Location: null,
  };
  const t = rowToTicket(row);
  assert.equal(t.tier, null);
  assert.equal(t.location, null);
  assert.ok(!('relevance' in t));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --import tsx --test tests/queryBuilders-tickets.test.ts`
Expected: FAIL — `tier`/`location`/`relevance` missing on the result.

- [ ] **Step 3: Update types** — in `src/types/ticket.ts`:

`TicketRow`: add after `ResolutionDescription: string | null;`:
```ts
  Tier: string | null;
  Location: string | null;
  Relevance?: number;
```

`TicketResult`: add after `resolutionDescription: string | null;`:
```ts
  tier: string | null;
  location: string | null;
  relevance?: number;
```

- [ ] **Step 4: Update serializer** — in `src/serializers/ticket.ts`, inside `rowToTicket`'s `result` object (after `resolutionDescription`):

```ts
    tier: row.Tier ?? null,
    location: row.Location ?? null,
```

and after the existing `ticketType` block, before `return result;`:

```ts
  if (row.Relevance != null) {
    result.relevance = row.Relevance;
  }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test`
Expected: PASS — new rowToTicket tests + all 99 existing.

- [ ] **Step 6: Commit**

```bash
git add src/types/ticket.ts src/serializers/ticket.ts tests/queryBuilders-tickets.test.ts
git commit -m "feat: expose tier/location/relevance on ticket results"
```

---

### Task 3: LIKE-mode word-based matching + Tier/Location columns

**Files:**
- Modify: `src/db/queries/tickets.ts`
- Modify: `tests/queryBuilders-tickets.test.ts` (update 2 existing LIKE tests, add new)

**Interfaces:**
- Consumes: `escapeLike` (Task 1).
- Produces: `locationColumn(kind: TicketKind): string`; `ticketColumns` projects `Tier` and `<LocationCol> AS Location`; LIKE-mode `q` produces one escaped per-token OR-group (WorkItemId/Title/Description/ResolutionDescription/Tier/Location) joined by `AND`; tokens bound as `tok0..tokN`.

- [ ] **Step 1: Write/update the failing tests** — in `tests/queryBuilders-tickets.test.ts`:

Replace the body of `search tickets: like mode uses LIKE` (existing lines) with:

```ts
test('search tickets: like mode uses LIKE', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'printer' }, 'like');
  assert.ok(q.sql.includes("Title LIKE '%' + @tok0 + '%'"));
  assert.ok(!q.sql.includes('CONTAINS'));
});
```

Replace the body of `search tickets: q also matches WorkItemId in like mode` with:

```ts
test('search tickets: q also matches WorkItemId in like mode', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'IR1660031' }, 'like');
  assert.ok(q.sql.includes("WorkItemId LIKE '%' + @tok0 + '%'"));
  assert.equal(q.inputs.tok0, 'IR1660031');
});
```

Append:

```ts
test('search tickets: like mode tokenizes q into per-word AND groups', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'printer jam' }, 'like');
  assert.ok(q.sql.includes('WorkItemId LIKE \'%\' + @tok0 + \'%\''));
  assert.ok(q.sql.includes('WorkItemId LIKE \'%\' + @tok1 + \'%\''));
  assert.equal(q.inputs.tok0, 'printer');
  assert.equal(q.inputs.tok1, 'jam');
  assert.ok(q.sql.split('\n  AND ').length >= 3, 'two token groups plus any filters, joined by AND');
});

test('search tickets: like mode matches Tier and Location columns per token', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'a21' }, 'like');
  assert.ok(q.sql.includes('Tier LIKE \'%\' + @tok0 + \'%\''));
  assert.ok(q.sql.includes('CurrentLocation_DC52702B_4C6C_AE3D_56FA_5ED1522FDE0A LIKE \'%\' + @tok0 + \'%\''));
  const sr = buildSearchTicketsQuery({ ...base, type: 'servicerequest', q: 'a21' }, 'like');
  assert.ok(sr.sql.includes('CurrentLocation_89125754_0643_0DA6_D2EB_50167E386A23 LIKE \'%\' + @tok0 + \'%\''));
});

test('search tickets: like mode escapes LIKE wildcards in tokens', () => {
  const q = buildSearchTicketsQuery({ ...base, q: '50%_ok' }, 'like');
  assert.ok(q.sql.includes("ESCAPE '\\'"));
  assert.equal(q.inputs.tok0, '50\\%\\_ok');
});

test('search tickets: projects tier and location columns', () => {
  const q = buildSearchTicketsQuery(base, 'fts');
  assert.ok(q.sql.includes('Tier'));
  assert.ok(q.sql.includes('CurrentLocation_DC52702B_4C6C_AE3D_56FA_5ED1522FDE0A AS Location'));
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --import tsx --test tests/queryBuilders-tickets.test.ts`
Expected: FAIL — old `@q`/`@qId` assertions fail; new token tests fail (no `tok0`).

- [ ] **Step 3: Implement** — in `src/db/queries/tickets.ts`:

Add near the top (after imports):

```ts
import { escapeLike } from '../escapeLike.js';

const LOCATION_COL: Record<TicketKind, string> = {
  incident: 'CurrentLocation_DC52702B_4C6C_AE3D_56FA_5ED1522FDE0A',
  servicerequest: 'CurrentLocation_89125754_0643_0DA6_D2EB_50167E386A23',
};

export function locationColumn(kind: TicketKind): string {
  return LOCATION_COL[kind];
}
```

Replace `ticketColumns` with:

```ts
function ticketColumns(kind: TicketKind): string {
  const base =
    kind === 'servicerequest'
      ? `Id, WorkItemId, Title, Status, Priority, Created AS CreatedDate, ResolvedDate, ClosedDate, Description, ResolutionDescription, Tier, ${locationColumn(kind)} AS Location`
      : `Id, WorkItemId, Title, Status, NULL AS Priority, Created AS CreatedDate, ResolvedDate, ClosedDate, Description, ResolutionDescription, Tier, ${locationColumn(kind)} AS Location`;
  return `${base}, AffectedUser, AffectedUserId, CreatedByUser, CreatedByUserId, AssignedUser, AssignedUserId`;
}
```

Replace the `else` branch inside `if (p.q)` in `buildTicketWhere` with:

```ts
    } else {
      const tokens = p.q.trim().split(/\s+/).filter(Boolean);
      if (tokens.length) {
        const groups = tokens.map((token, i) => {
          inputs[`tok${i}`] = escapeLike(token);
          return `(WorkItemId LIKE '%' + @tok${i} + '%' ESCAPE '\\'
  OR Title LIKE '%' + @tok${i} + '%' ESCAPE '\\'
  OR Description LIKE '%' + @tok${i} + '%' ESCAPE '\\'
  OR ResolutionDescription LIKE '%' + @tok${i} + '%' ESCAPE '\\'
  OR Tier LIKE '%' + @tok${i} + '%' ESCAPE '\\'
  OR ${locationColumn(p.type)} LIKE '%' + @tok${i} + '%' ESCAPE '\\')`;
        });
        where.push(groups.join('\n  AND '));
      }
    }
```

(Leave the `fts` branch untouched, including `workItemIdCond` and `inputs.qId`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS. (Existing FTS-mode tests unchanged and passing.)

- [ ] **Step 5: Commit**

```bash
git add src/db/queries/tickets.ts tests/queryBuilders-tickets.test.ts
git commit -m "feat: word-based AND matching across ticket content, tier and location"
```

---

### Task 4: Tier and Location filters

**Files:**
- Modify: `src/db/queries/tickets.ts`
- Modify: `tests/queryBuilders-tickets.test.ts`

**Interfaces:**
- Consumes: `locationColumn` (Task 3), `escapeLike` (Task 1).
- Produces: `SearchTicketsParams` gains `tier?: string`, `location?: string`. `buildTicketWhere` adds `Tier = @tier` (exact) and `<LocationCol> LIKE '%' + @location + '%' ESCAPE '\'` (contains). Shared by data + count builders.

- [ ] **Step 1: Write the failing tests** — append to `tests/queryBuilders-tickets.test.ts`:

```ts
test('search tickets: tier filter binds exactly', () => {
  const q = buildSearchTicketsQuery({ ...base, tier: 'Potch Staff Service Desk' }, 'fts');
  assert.ok(q.sql.includes('Tier = @tier'));
  assert.equal(q.inputs.tier, 'Potch Staff Service Desk');
});

test('search tickets: location filter uses contains on the location column', () => {
  const q = buildSearchTicketsQuery({ ...base, location: 'A21' }, 'fts');
  assert.ok(q.sql.includes("CurrentLocation_DC52702B_4C6C_AE3D_56FA_5ED1522FDE0A LIKE '%' + @location + '%' ESCAPE '\\'"));
  assert.equal(q.inputs.location, 'A21');
  const sr = buildSearchTicketsQuery({ ...base, type: 'servicerequest', location: 'A21' }, 'fts');
  assert.ok(sr.sql.includes('CurrentLocation_89125754_0643_0DA6_D2EB_50167E386A23 LIKE'));
});

test('search tickets: location filter escapes LIKE wildcards', () => {
  const q = buildSearchTicketsQuery({ ...base, location: '50%' }, 'like');
  assert.equal(q.inputs.location, '50\\%');
});

test('count tickets includes tier and location filters', () => {
  const q = buildCountTicketsQuery({ ...base, tier: 'T', location: 'A21' }, 'like');
  assert.ok(q.sql.includes('Tier = @tier'));
  assert.ok(q.sql.includes('CurrentLocation_DC52702B_4C6C_AE3D_56FA_5ED1522FDE0A LIKE'));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --import tsx --test tests/queryBuilders-tickets.test.ts`
Expected: FAIL — no `Tier = @tier` in SQL.

- [ ] **Step 3: Implement** — in `src/db/queries/tickets.ts`:

Add to `SearchTicketsParams` (after `priority?: string;`):
```ts
  tier?: string;
  location?: string;
```

In `buildTicketWhere`, after the `priority` block:

```ts
  if (p.tier) {
    where.push('Tier = @tier');
    inputs.tier = p.tier;
  }
  if (p.location) {
    where.push(`${locationColumn(p.type)} LIKE '%' + @location + '%' ESCAPE '\\'`);
    inputs.location = escapeLike(p.location);
  }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/queries/tickets.ts tests/queryBuilders-tickets.test.ts
git commit -m "feat: add tier and location ticket filters"
```

---

### Task 5: Relevance ranking + sort ordering

**Files:**
- Modify: `src/db/queries/tickets.ts`
- Modify: `tests/queryBuilders-tickets.test.ts`
- Modify: `tests/routes-search.test.ts`

**Interfaces:**
- Consumes: `buildTicketWhere` (Tasks 3-4), tokens bound as `tok0..tokN`.
- Produces: `SearchTicketsParams` gains `sort: 'relevance'|'newest'|'az'`. `buildSearchTicketsQuery` honors `sort`: `az` → `ORDER BY Title ASC`; `relevance` (LIKE mode, ≥2 tokens) → SELECT a computed `Relevance` column and `ORDER BY Relevance ASC, Created DESC`; otherwise `ORDER BY Created DESC`. New bound input `phrase` (tokens joined by single space).

- [ ] **Step 1: Write the failing tests** — append to `tests/queryBuilders-tickets.test.ts`:

```ts
test('search tickets: sort az orders by Title', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'x', sort: 'az' }, 'like');
  assert.ok(q.sql.includes('ORDER BY Title ASC'));
});

test('search tickets: sort newest orders by Created desc', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'x', sort: 'newest' }, 'like');
  assert.ok(q.sql.includes('ORDER BY Created DESC'));
  assert.ok(!q.sql.includes('AS Relevance'));
});

test('search tickets: sort relevance adds a Relevance column and orders by it', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'printer jam', sort: 'relevance' }, 'like');
  assert.ok(q.sql.includes('AS Relevance'));
  assert.ok(q.sql.includes('ORDER BY Relevance ASC, Created DESC'));
  assert.equal(q.inputs.phrase, 'printer jam');
});

test('search tickets: single-token relevance query keeps Created DESC and no Relevance column', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'printer', sort: 'relevance' }, 'like');
  assert.ok(q.sql.includes('ORDER BY Created DESC'));
  assert.ok(!q.sql.includes('AS Relevance'));
});

test('search tickets: relevance sort is ignored in fts mode', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'printer jam', sort: 'relevance' }, 'fts');
  assert.ok(!q.sql.includes('AS Relevance'));
  assert.ok(q.sql.includes('ORDER BY Created DESC'));
});
```

Append to `tests/routes-search.test.ts` (after the existing `like mode passes q through raw` test):

```ts
test('GET /v1/search/tickets binds tier/location/sort params', async () => {
  const { pool, calls } = capturingPool([[ticketRow], [{ Total: 1 }]]);
  const res = await request(makeApp(pool, 'like'))
    .get('/v1/search/tickets')
    .query({ type: 'incident', q: 'printer', tier: 'T', location: 'A21', sort: 'az' });
  assert.equal(res.status, 200);
  assert.equal(calls[0].tier, 'T');
  assert.equal(calls[0].location, 'A21');
  assert.equal(calls[0].sort, 'az');
});
```

Also UPDATE the existing `GET /v1/search/tickets in like mode passes q through raw` test: change `assert.equal(calls[0].q, 'printer%');` to `assert.equal(calls[0].tok0, 'printer\\%');` and add `assert.ok(!('q' in calls[0]));`.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --import tsx --test tests/queryBuilders-tickets.test.ts tests/routes-search.test.ts`
Expected: FAIL — `ORDER BY Title ASC` / `AS Relevance` missing; route still binds raw `q`.

- [ ] **Step 3: Implement** — in `src/db/queries/tickets.ts`:

Add to `SearchTicketsParams`:
```ts
  sort?: 'relevance' | 'newest' | 'az';
```

Add a helper (place after `roleFilter`):

```ts
function buildRelevanceExpr(
  tokens: string[],
  kind: TicketKind,
  inputs: Record<string, string | number | Date>
): string {
  const text =
    "ISNULL(Title, N'') + N' ' + ISNULL(Description, N'') + N' ' + ISNULL(ResolutionDescription, N'')";
  const pos = tokens.map((_, i) => `NULLIF(CHARINDEX(@tok${i}, ${text}), 0)`);
  inputs.phrase = tokens.join(' ');
  const pairs: string[] = [];
  for (let i = 0; i < tokens.length - 1; i++) {
    pairs.push(
      `CASE WHEN ${pos[i + 1]} IS NOT NULL AND ${pos[i]} IS NOT NULL AND ${pos[i + 1]} > ${pos[i]} ` +
        `THEN ${pos[i + 1]} - ${pos[i]} - LEN(@tok${i}) ELSE 10000 END`
    );
  }
  const sum = pairs.length ? `(${pairs.join(' + ')})` : '0';
  return `CASE WHEN CHARINDEX(@phrase, ${text}) > 0 THEN 0 ELSE ${sum} END`;
}
```

Replace the body of `buildSearchTicketsQuery` with:

```ts
export function buildSearchTicketsQuery(
  p: SearchTicketsParams,
  searchMode: 'fts' | 'like'
): PreparedQuery {
  const { where, inputs } = buildTicketWhere(p, searchMode);
  inputs.offset = (p.page - 1) * p.pageSize;
  inputs.pageSize = p.pageSize;
  const whereSql = where.length ? `WHERE ${where.join('\n  AND ')}` : '';
  const tokens = (p.q ?? '').trim().split(/\s+/).filter(Boolean);
  const sort = p.sort ?? 'relevance';
  let selectExtra = '';
  let orderBy = 'ORDER BY Created DESC';
  if (searchMode === 'like' && sort === 'relevance' && tokens.length >= 2) {
    selectExtra = `, ${buildRelevanceExpr(tokens, p.type, inputs)} AS Relevance`;
    orderBy = 'ORDER BY Relevance ASC, Created DESC';
  } else if (sort === 'az') {
    orderBy = 'ORDER BY Title ASC';
  }
  return {
    sql: `SELECT ${ticketColumns(p.type)}${selectExtra}
FROM ${ticketTable(p.type)}
${whereSql}
${orderBy}
OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY;`,
    inputs,
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS. (All fts tests, existing like tests, and the two updated tests.)

- [ ] **Step 5: Commit**

```bash
git add src/db/queries/tickets.ts tests/queryBuilders-tickets.test.ts tests/routes-search.test.ts
git commit -m "feat: adjacency-prioritized relevance ranking and sort ordering"
```

---

### Task 6: User search word-based matching

**Files:**
- Modify: `src/db/queries/users.ts`
- Modify: `tests/queryBuilders-users.test.ts`

**Interfaces:**
- Consumes: `escapeLike` (Task 1).
- Produces: `buildSearchUsersQuery`/`buildCountUsersQuery` match every word of `q` (tokens bound `uq0..uqN`) across `UserName`/`DisplayName`/`UPN`.

- [ ] **Step 1: Write/update the failing tests** — in `tests/queryBuilders-users.test.ts`:

Replace the bodies of the three `q`-related tests:

```ts
test('search users: q matches username, displayname, or upn per word', () => {
  const q = buildSearchUsersQuery({ q: 'john smith', page: 1, pageSize: 25 });
  assert.ok(q.sql.includes('@uq0'));
  assert.ok(q.sql.includes('@uq1'));
  assert.equal(q.inputs.uq0, 'john');
  assert.equal(q.inputs.uq1, 'smith');
  assert.ok(q.sql.includes('UserName_6AF77E23_669B_123F_B392_323C17097BBD'));
  assert.ok(q.sql.includes('UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02'));
  assert.ok(q.sql.includes('ServiceManager.dbo.MTV_System$Domain$User'));
  assert.ok(q.sql.includes('ESCAPE'));
});

test('search users: value is parameterized, never inlined', () => {
  const q = buildSearchUsersQuery({ q: "x' OR 1=1 --", page: 1, pageSize: 25 });
  assert.ok(q.sql.includes('@uq0'));
  assert.ok(!q.sql.includes("x'"));
});

test('count users mirrors the where clause', () => {
  const q = buildCountUsersQuery({ q: 'smith' });
  assert.ok(q.sql.startsWith('SELECT COUNT(*) AS Total'));
  assert.ok(q.sql.includes('@uq0'));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --import tsx --test tests/queryBuilders-users.test.ts`
Expected: FAIL — no `@uq0`; old `@q` assertions fail.

- [ ] **Step 3: Implement** — in `src/db/queries/users.ts`:

Add import + replace `userWhere`:

```ts
import { escapeLike } from '../escapeLike.js';
```

```ts
function userWhere(q?: string): { where: string[]; inputs: Record<string, string> } {
  const where: string[] = [];
  const inputs: Record<string, string> = {};
  if (q) {
    const tokens = q.trim().split(/\s+/).filter(Boolean);
    const groups = tokens.map((token, i) => {
      inputs[`uq${i}`] = escapeLike(token);
      return `(${USERNAME_COL} LIKE '%' + @uq${i} + '%' ESCAPE '\\' OR u.DisplayName LIKE '%' + @uq${i} + '%' ESCAPE '\\' OR ${UPN_COL} LIKE '%' + @uq${i} + '%' ESCAPE '\\')`;
    });
    where.push(groups.join('\n  AND '));
  }
  return { where, inputs };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/queries/users.ts tests/queryBuilders-users.test.ts
git commit -m "feat: word-based AND matching in user search"
```

---

### Task 7: `GET /v1/meta/filters` endpoint

**Files:**
- Create: `src/db/queries/meta.ts`
- Create: `src/routes/meta.ts`
- Create: `tests/routes-meta.test.ts`
- Modify: `src/app.ts`
- Modify: `README.md`, `CHANGELOG.md`

**Interfaces:**
- Produces: `GET /v1/meta/filters` (API-key protected) → `{ tiers: string[], statuses: string[] }` (distinct, nulls excluded, A–Z). Compass Task 9 consumes it.

- [ ] **Step 1: Write the failing test** — create `tests/routes-meta.test.ts`:

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import express from 'express';
import type { ConnectionPool } from 'mssql';
import { metaRouter } from '../src/routes/meta.js';
import { errorHandler } from '../src/middleware/errorHandler.js';

function fakePool(recordSets: unknown[][]): ConnectionPool {
  let call = 0;
  return {
    request() {
      return {
        input() {},
        async query() {
          return { recordset: recordSets[Math.min(call++, recordSets.length - 1)] ?? [] };
        },
      };
    },
  } as unknown as ConnectionPool;
}

test('GET /v1/meta/filters groups distinct tiers and statuses', async () => {
  const rows = [
    { FilterType: 'tier', Value: 'Potch Staff Service Desk' },
    { FilterType: 'tier', Value: 'Operations' },
    { FilterType: 'status', Value: 'Closed' },
  ];
  const app = express();
  app.use('/v1/meta', metaRouter({ pool: fakePool([rows]) }));
  app.use(errorHandler);
  const res = await request(app).get('/v1/meta/filters');
  assert.equal(res.status, 200);
  assert.deepEqual(res.body, {
    tiers: ['Potch Staff Service Desk', 'Operations'],
    statuses: ['Closed'],
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --import tsx --test tests/routes-meta.test.ts`
Expected: FAIL — `../src/routes/meta.js` not found.

- [ ] **Step 3: Implement** — create `src/db/queries/meta.ts`:

```ts
import type { PreparedQuery } from '../exec.js';

export interface FilterRow {
  FilterType: 'tier' | 'status';
  Value: string;
}

export function buildFiltersQuery(): PreparedQuery {
  return {
    sql: `SELECT 'tier' AS FilterType, Tier AS Value
FROM CiresonAnalytics.dbo.SM_WorkItem_Incident WHERE Tier IS NOT NULL
UNION
SELECT 'tier', Tier FROM CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest WHERE Tier IS NOT NULL
UNION
SELECT 'status', Status FROM CiresonAnalytics.dbo.SM_WorkItem_Incident WHERE Status IS NOT NULL
UNION
SELECT 'status', Status FROM CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest WHERE Status IS NOT NULL
ORDER BY Value;`,
    inputs: {},
  };
}
```

Create `src/routes/meta.ts`:

```ts
import { Router } from 'express';
import type { ConnectionPool } from 'mssql';
import { exec } from '../db/exec.js';
import { buildFiltersQuery, type FilterRow } from '../db/queries/meta.js';

export function metaRouter(opts: { pool: ConnectionPool }): Router {
  const router = Router();

  router.get('/filters', async (_req, res) => {
    const rows = await exec<FilterRow>(opts.pool, buildFiltersQuery());
    const tiers: string[] = [];
    const statuses: string[] = [];
    for (const row of rows) {
      if (row.FilterType === 'tier') tiers.push(row.Value);
      else statuses.push(row.Value);
    }
    res.json({ tiers, statuses });
  });

  return router;
}
```

In `src/app.ts`, add the import and registration:

```ts
import { metaRouter } from './routes/meta.js';
```
```ts
  app.use('/v1/meta', metaRouter({ pool }));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test && npm run build`
Expected: PASS (routes-meta test + all existing); `tsc` clean.

- [ ] **Step 5: Docs** — append to `scsm-search/CHANGELOG.md` a dated entry summarizing this feature set; update `scsm-search/README.md`'s search-params table with `tier`, `location`, `sort`, and document `GET /v1/meta/filters`.

- [ ] **Step 6: Commit**

```bash
git add src/db/queries/meta.ts src/routes/meta.ts tests/routes-meta.test.ts src/app.ts README.md CHANGELOG.md
git commit -m "feat: add /v1/meta/filters endpoint with tier and status values"
```

---

### Task 8: Compass proxy — params passthrough + merged sort

**Files:**
- Modify: `modules/scsm_search/engine.py`
- Modify: `modules/scsm_search/routes.py`
- Modify: `tests/test_scsm_search_engine.py`, `tests/test_scsm_search_routes.py`

**Interfaces:**
- Consumes: scsm-search `tier`/`location`/`sort` params and `relevance`/`title`/`createdDate` on results (Tasks 3-5).
- Produces: `search_tickets(..., tier=..., location=..., sort=...)` forwards them; `POST /api/scsm/tickets` accepts them and returns a list ordered by the requested sort.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scsm_search_engine.py`:

```python
def test_search_tickets_forwards_tier_location_sort(monkeypatch, api_key):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return FakeResp(200, {"results": [], "total": 0})

    monkeypatch.setattr(engine, "SCSM_API_URL", "http://scsm-search:3000")
    monkeypatch.setattr(engine.requests, "request", fake_request)
    engine.search_tickets(
        "printer",
        ticket_type="incident",
        tier="Potch Staff Service Desk",
        location="A21",
        sort="az",
    )
    assert captured["params"]["tier"] == "Potch Staff Service Desk"
    assert captured["params"]["location"] == "A21"
    assert captured["params"]["sort"] == "az"
```

Append to `tests/test_scsm_search_routes.py`:

```python
def test_tickets_forwards_tier_location_sort(client, monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(kwargs.get("params"))
        return FakeResp(200, {"results": [], "total": 0})

    monkeypatch.setattr(engine.requests, "request", fake_request)
    resp = client.post(
        "/api/scsm/tickets",
        json={"q": "x", "tier": "T", "location": "A21", "sort": "az"},
    )
    assert resp.status_code == 200
    assert [p.get("tier") for p in calls] == ["T", "T"]
    assert [p.get("location") for p in calls] == ["A21", "A21"]
    assert [p.get("sort") for p in calls] == ["az", "az"]


def test_tickets_az_sorts_by_title(client, monkeypatch):
    incident = {
        "results": [{
            "id": "a", "workItemId": "IR1", "title": "Zulu printer", "status": "Active",
            "priority": "2", "createdDate": "2026-07-01T09:00:00Z",
            "affectedUser": None, "createdByUser": None, "assignedUser": None,
        }],
        "total": 1,
    }
    servicerequest = {
        "results": [{
            "id": "b", "workItemId": "SR2", "title": "Alpha pc", "status": "Active",
            "priority": "3", "createdDate": "2026-08-01T09:00:00Z",
            "affectedUser": None, "createdByUser": None, "assignedUser": None,
        }],
        "total": 1,
    }
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        return FakeResp(200, incident if calls["n"] == 1 else servicerequest)

    monkeypatch.setattr(engine.requests, "request", fake_request)
    resp = client.post("/api/scsm/tickets", json={"q": "pc", "sort": "az"})
    assert resp.status_code == 200
    assert [r["workItemId"] for r in resp.get_json()["results"]] == ["SR2", "IR1"]


def test_tickets_relevance_sorts_by_relevance_then_newest(client, monkeypatch):
    incident = {
        "results": [{
            "id": "a", "workItemId": "IR1", "title": "printer jam", "status": "Active",
            "priority": "2", "createdDate": "2026-07-01T09:00:00Z", "relevance": 0,
            "affectedUser": None, "createdByUser": None, "assignedUser": None,
        }],
        "total": 1,
    }
    servicerequest = {
        "results": [{
            "id": "b", "workItemId": "SR2", "title": "jam printer", "status": "Active",
            "priority": "3", "createdDate": "2026-08-01T09:00:00Z", "relevance": 10000,
            "affectedUser": None, "createdByUser": None, "assignedUser": None,
        }],
        "total": 1,
    }
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        return FakeResp(200, incident if calls["n"] == 1 else servicerequest)

    monkeypatch.setattr(engine.requests, "request", fake_request)
    resp = client.post("/api/scsm/tickets", json={"q": "printer jam", "sort": "relevance"})
    assert resp.status_code == 200
    assert [r["workItemId"] for r in resp.get_json()["results"]] == ["IR1", "SR2"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_engine.py tests/test_scsm_search_routes.py`
Expected: FAIL — `tier` not forwarded; `az`/`relevance` ordering not applied.

- [ ] **Step 3: Implement** — in `modules/scsm_search/engine.py`, update the passthrough tuple in `search_tickets`:

```python
    for key in (
        "status", "priority", "affectedUserId", "createdByUserId", "assignedUserId",
        "from", "to", "tier", "location", "sort",
    ):
        if filters.get(key) is not None:
            params[key] = filters[key]
```

In `modules/scsm_search/routes.py`, add helpers (before the `tickets()` view) and update the route:

```python
_BIG = 10 ** 9


def _relevance(row):
    rel = row.get("relevance")
    return rel if isinstance(rel, (int, float)) else _BIG


def _apply_sort(merged, sort):
    merged.sort(key=lambda r: r.get("createdDate") or "", reverse=True)
    if sort == "az":
        merged.sort(key=lambda r: (r.get("title") or "").lower())
    elif sort == "relevance":
        merged.sort(key=_relevance)
```

In `tickets()`: extend the filter loop and replace the final sort:

```python
    for key in ("status", "priority", "from", "to", "tier", "location", "sort"):
        if body.get(key) is not None:
            filters[key] = body[key]
```

```python
    _apply_sort(merged, filters.get("sort"))
    return {"results": merged, "total": total, "page": 1}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_engine.py tests/test_scsm_search_routes.py`
Expected: PASS. (The existing `test_tickets_merges_sorts_and_enriches` still passes — default sort = newest.)

- [ ] **Step 5: Commit**

```bash
git add modules/scsm_search/engine.py modules/scsm_search/routes.py tests/test_scsm_search_engine.py tests/test_scsm_search_routes.py
git commit -m "feat: proxy tier/location/sort params and order merged results accordingly"
```

---

### Task 9: Compass meta filters proxy + cache

**Files:**
- Modify: `modules/scsm_search/engine.py`
- Modify: `modules/scsm_search/routes.py`
- Modify: `tests/test_scsm_search_engine.py`, `tests/test_scsm_search_routes.py`

**Interfaces:**
- Consumes: scsm-search `GET /v1/meta/filters` (Task 7).
- Produces: `engine.fetch_filters() -> dict` (cached 1h) and `GET /api/scsm/meta/filters`. Page filter bar (Task 10) consumes it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scsm_search_engine.py`:

```python
def test_fetch_filters_proxies_and_caches(monkeypatch, api_key):
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        assert url.endswith("/v1/meta/filters")
        return FakeResp(200, {"tiers": ["T1", "T2"], "statuses": ["Closed"]})

    monkeypatch.setattr(engine, "filters_cache", engine.FiltersCache())
    monkeypatch.setattr(engine.requests, "request", fake_request)
    first = engine.fetch_filters()
    second = engine.fetch_filters()
    assert first == {"tiers": ["T1", "T2"], "statuses": ["Closed"]}
    assert second == first
    assert calls["n"] == 1
```

Append to `tests/test_scsm_search_routes.py`:

```python
def test_meta_filters_proxies(client, monkeypatch):
    def fake_request(method, url, **kwargs):
        return FakeResp(200, {"tiers": ["T1"], "statuses": ["Closed"]})

    monkeypatch.setattr(engine.requests, "request", fake_request)
    resp = client.get("/api/scsm/meta/filters")
    assert resp.status_code == 200
    assert resp.get_json() == {"tiers": ["T1"], "statuses": ["Closed"]}
```

Update the `client` fixture in `tests/test_scsm_search_routes.py` to reset the cache so tests don't share state:

```python
    monkeypatch.setattr(engine, "filters_cache", engine.FiltersCache())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_engine.py tests/test_scsm_search_routes.py`
Expected: FAIL — `engine.FiltersCache` does not exist; `/api/scsm/meta/filters` returns 404.

- [ ] **Step 3: Implement** — in `modules/scsm_search/engine.py`, add after `related_cache = RelatedTicketsCache()`:

```python
META_FILTERS_TTL_SECONDS = 60 * 60


class FiltersCache:
    def __init__(self, ttl_seconds=None, clock=None):
        self._ttl = ttl_seconds if ttl_seconds is not None else META_FILTERS_TTL_SECONDS
        self._clock = clock or time.monotonic
        self._data = None
        self._loaded_at = None

    def get(self):
        if self._data is not None and self._clock() - self._loaded_at < self._ttl:
            return self._data
        return None

    def set(self, data):
        self._data = data
        self._loaded_at = self._clock()


filters_cache = FiltersCache()


def fetch_filters():
    cached = filters_cache.get()
    if cached is not None:
        return cached
    data = _request("GET", "/v1/meta/filters")
    filters_cache.set(data)
    return data
```

(`time` is already imported at module level.)

In `modules/scsm_search/routes.py`, add before `_spawn_warm`:

```python
@bp.get("/meta/filters")
@_scsm_route
def meta_filters():
    return engine.fetch_filters()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_engine.py tests/test_scsm_search_routes.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/scsm_search/engine.py modules/scsm_search/routes.py tests/test_scsm_search_engine.py tests/test_scsm_search_routes.py
git commit -m "feat: proxy and cache SCSM filter values for the page"
```

---

### Task 10: Page filter bar

**Files:**
- Modify: `templates/scsm_search.html`
- Modify: `tests/test_scsm_search_page.py`

**Interfaces:**
- Consumes: `POST /api/scsm/tickets` new body params (Task 8) and `GET /api/scsm/meta/filters` (Task 9).
- Produces: `#scsm-filters` bar with `#scsm-tier`, `#scsm-status`, `#scsm-location`, `#scsm-from`, `#scsm-to`, `.scsm-sort` buttons; re-runs the active search on change.

- [ ] **Step 1: Write the failing test** — update `tests/test_scsm_search_page.py`:

```python
def test_scsm_search_page_has_filter_bar():
    app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"))
    app.config["TESTING"] = True
    app.register_blueprint(pages_bp)
    resp = app.test_client().get("/scsm-search")
    assert resp.status_code == 200
    assert b"scsm-filters" in resp.data
    assert b"scsm-tier" in resp.data
    assert b"scsm-status" in resp.data
    assert b"scsm-location" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_page.py`
Expected: FAIL — no `scsm-filters` in markup.

- [ ] **Step 3: Implement** — in `templates/scsm_search.html`:

After the `.scsm-searchbar` closing `</div>` (line 15) and before `#scsm-tabs`, insert:

```html
    <div id="scsm-filters" class="scsm-filters">
      <select id="scsm-tier" aria-label="Tier / Queue"><option value="">All tiers</option></select>
      <select id="scsm-status" aria-label="Status"><option value="">All statuses</option></select>
      <input id="scsm-location" type="text" placeholder="Location contains…" autocomplete="off" aria-label="Location">
      <input id="scsm-from" type="date" aria-label="Created from">
      <input id="scsm-to" type="date" aria-label="Created to">
      <span class="scsm-sort" role="group" aria-label="Sort results">
        <button type="button" data-sort="relevance" class="active">Relevance</button>
        <button type="button" data-sort="newest">Newest</button>
        <button type="button" data-sort="az">A&ndash;Z</button>
      </span>
    </div>
```

Add CSS after `.scsm-tab .scsm-count` rule:

```css
  .scsm-filters { display: flex; flex-wrap: wrap; gap: .5rem; padding: .6rem .8rem 0; align-items: center; }
  .scsm-filters select, .scsm-filters input[type="text"], .scsm-filters input[type="date"] { padding: .35rem .5rem; font-size: .82rem; border: 1px solid #d0d7de; border-radius: 6px; background: #fff; color: #24292f; }
  .scsm-sort { display: inline-flex; border: 1px solid #d0d7de; border-radius: 6px; overflow: hidden; }
  .scsm-sort button { border: none; background: #fff; padding: .35rem .6rem; font-size: .82rem; cursor: pointer; color: #57606a; }
  .scsm-sort button.active { background: #006633; color: #fff; }
```

In the script, add element refs after the existing `resultsEl` ref:

```js
  var filtersEl = document.getElementById('scsm-filters');
  var tierEl = document.getElementById('scsm-tier');
  var statusEl = document.getElementById('scsm-status');
  var locationEl = document.getElementById('scsm-location');
  var fromEl = document.getElementById('scsm-from');
  var toEl = document.getElementById('scsm-to');
```

Add `filters` to `state`:

```js
    filters: { tier: '', status: '', location: '', from: '', to: '', sort: 'relevance' },
```

Add functions after `renderSkeletons`:

```js
  function getFiltersPayload() {
    var f = state.filters;
    var out = {};
    if (f.tier) out.tier = f.tier;
    if (f.status) out.status = f.status;
    if (f.location.trim()) out.location = f.location.trim();
    if (f.from) out.from = f.from;
    if (f.to) out.to = f.to;
    if (f.sort !== 'relevance') out.sort = f.sort;
    return out;
  }

  function loadFilterMeta() {
    fetch('/api/scsm/meta/filters').then(function (r) {
      if (!r.ok) throw new Error('meta');
      return r.json();
    }).then(function (data) {
      [['tiers', tierEl], ['statuses', statusEl]].forEach(function (pair) {
        var list = data[pair[0]] || [];
        list.forEach(function (v) {
          var o = document.createElement('option');
          o.value = v;
          o.textContent = v;
          pair[1].appendChild(o);
        });
        pair[1].hidden = !list.length;
      });
    }).catch(function () {
      tierEl.hidden = true;
      statusEl.hidden = true;
    });
  }

  function syncFiltersState() {
    state.filters.tier = tierEl.value;
    state.filters.status = statusEl.value;
    state.filters.location = locationEl.value;
    state.filters.from = fromEl.value;
    state.filters.to = toEl.value;
  }

  [tierEl, statusEl, locationEl, fromEl, toEl].forEach(function (el) {
    el.addEventListener('input', function () {
      syncFiltersState();
      if (state.query.length >= 2) doSearch(state.query);
    });
  });

  document.querySelectorAll('.scsm-sort button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.scsm-sort button').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      state.filters.sort = btn.getAttribute('data-sort');
      if (state.query.length >= 2) doSearch(state.query);
    });
  });
```

Call `loadFilterMeta()` after the function definitions (e.g. right after the `renderTabs` function body).

In `doSearch`, change the body to include filters:

```js
      fetch('/api/scsm/tickets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ q: q }, getFiltersPayload())) }),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_page.py`
Expected: PASS.

- [ ] **Step 5: Manual QA**

Run the app (`python3 app.py`), open `/scsm-search`, type a query, change filters, confirm the ticket API receives them and results re-render. Confirm Tier/Status selects populate from `/api/scsm/meta/filters`; if the meta endpoint is down, both selects hide.

- [ ] **Step 6: Commit**

```bash
git add templates/scsm_search.html tests/test_scsm_search_page.py
git commit -m "feat: add tier/status/location/date/sort filter bar to SCSM search"
```

---

### Task 11: Results counter (rendered rows)

**Files:**
- Modify: `templates/scsm_search.html`
- Modify: `tests/test_scsm_search_page.py`

**Interfaces:**
- Consumes: `renderResults` (search path) and `renderRoleResults` (role path) call counts.
- Produces: `#scsm-count` line showing the number of rows rendered (e.g. "42 results"). Hidden when 0.

- [ ] **Step 1: Write the failing test** — extend the page test:

```python
def test_scsm_search_page_has_counter_line():
    app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"))
    app.config["TESTING"] = True
    app.register_blueprint(pages_bp)
    resp = app.test_client().get("/scsm-search")
    assert b"scsm-count" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_page.py`
Expected: FAIL — no `scsm-count`.

- [ ] **Step 3: Implement** — in `templates/scsm_search.html`:

Insert after the `.scsm-searchbar` div (or after `#scsm-filters`):

```html
    <div id="scsm-count" class="scsm-count" hidden></div>
```

Add CSS after `.scsm-status`:

```css
  .scsm-count { padding: .4rem .8rem 0; font-size: .8rem; color: #57606a; }
```

In the script, add a ref after `statusEl`:

```js
  var countEl = document.getElementById('scsm-count');
```

Add a helper after `setStatus`:

```js
  function setCount(n) {
    countEl.hidden = !n;
    countEl.textContent = n === 1 ? '1 result' : n + ' results';
  }
```

Call sites:
- In `renderResults`, after `resultsEl.innerHTML = html;`: `setCount(users.length + tickets.length);`
- In `renderRoleResults`, after `resultsEl.innerHTML = html;`: `setCount(rows.length);`
- In the `q.length < 2` branch of the query input handler, after `setStatus('');`: `setCount(0);`
- In `doSearch`'s failure paths (both `.then` non-ok and `.catch`), after `setStatus('Search failed…')`: `setCount(0);`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_page.py`
Expected: PASS.

- [ ] **Step 5: Manual QA**

Search "printer": counter shows the merged rendered row count (users + tickets, ≤ 50). Open a person's role tab: counter shows that role's rendered rows. Type <2 chars: counter disappears.

- [ ] **Step 6: Commit**

```bash
git add templates/scsm_search.html tests/test_scsm_search_page.py
git commit -m "feat: show rendered-row results counter on SCSM search"
```

---

### Task 12: Skeleton fills the container

**Files:**
- Modify: `templates/scsm_search.html`

**Interfaces:**
- Consumes: `renderSkeletons()` call sites (search + role-tab loading), `#scsm-results` container.
- Produces: `renderSkeletons()` with no count arg fills the visible container; re-fills on window resize while loading.

- [ ] **Step 1: Implement** — in `templates/scsm_search.html`, replace `renderSkeletons`:

```js
  var SKELETON_ROW =
    '<div class="scsm-skeleton" aria-hidden="true">' +
      '<div class="scsm-skeleton-bar scsm-skeleton-chip"></div>' +
      '<div class="scsm-skeleton-bar scsm-skeleton-title"></div>' +
      '<div class="scsm-skeleton-meta">' +
        '<div class="scsm-skeleton-bar scsm-skeleton-badge"></div>' +
        '<div class="scsm-skeleton-bar scsm-skeleton-text"></div>' +
        '<div class="scsm-skeleton-bar scsm-skeleton-text short"></div>' +
      '</div>' +
    '</div>';

  function renderSkeletons() {
    resultsEl.innerHTML = SKELETON_ROW;
    var probe = resultsEl.firstChild;
    var rowH = probe && probe.offsetHeight ? probe.offsetHeight : 68;
    var count = Math.max(4, Math.min(40, Math.ceil(resultsEl.clientHeight / rowH)));
    var html = '';
    for (var i = 0; i < count; i++) html += SKELETON_ROW;
    resultsEl.innerHTML = html;
    state.skeletons = true;
  }
```

Add `skeletons: false` to `state`.

Update call sites:
- `doSearch`: `renderSkeletons(5)` → `renderSkeletons()`
- `loadRoleTickets`: `renderSkeletons(3)` → `renderSkeletons()`

Clear the flag when content replaces skeletons — add `state.skeletons = false;` in:
- `renderResults` (before `resultsEl.innerHTML = html;`)
- `renderRoleResults` (before `resultsEl.innerHTML = html;`)
- the `q.length < 2` branch (with `clearList();`)
- both `doSearch` failure paths

Add the resize handler after the `renderSkeletons` definition:

```js
  var skeletonResizeTimer = null;
  window.addEventListener('resize', function () {
    clearTimeout(skeletonResizeTimer);
    skeletonResizeTimer = setTimeout(function () {
      if (state.skeletons) renderSkeletons();
    }, 150);
  });
```

- [ ] **Step 2: Run the page test**

Run: `python3 -m pytest -p no:cacheprovider -q tests/test_scsm_search_page.py`
Expected: PASS (page still renders).

- [ ] **Step 3: Manual QA**

Run the app, search, and confirm the skeleton list fills the whole visible results area (no whitespace gap below the 5th row) and the layout does not jump when results arrive. Resize the window mid-load and confirm the skeleton re-fills. Confirm role-tab loading also fills the container. With `prefers-reduced-motion`, shimmer is off but rows still fill.

- [ ] **Step 4: Docs + Commit**

Append a dated CHANGELOG entry to `pcm-compass/CHANGELOG.md` summarizing this feature set, then:

```bash
git add templates/scsm_search.html CHANGELOG.md
git commit -m "feat: fill the results container with skeleton rows while loading"
```

---

## Full-Suite Verification

Run at the end, in each repo:

- `scsm-search`: `npm test && npm run build`
- `pcm-compass`: `python3 -m pytest -p no:cacheprovider -q`
