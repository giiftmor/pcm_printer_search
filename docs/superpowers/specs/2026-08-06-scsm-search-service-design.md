# SCSM Search Service — Design

Date: 2026-08-06
Status: Approved (design review, real-schema pass)

Companion doc: `docs/scsm-search-architecture.md` — this spec validates and refines that architecture for implementation. Where they differ, this spec wins.

## 1. Purpose

Build a read-only search API over SCSM ticket and user data, sourced from the **CiresonAnalytics** data warehouse plus the **ServiceManager** user projection. The API is the single query path into SCSM data — n8n consumes it now (bots, digests, scheduled jobs); the PCM Compass Flask app and Chrome extension consume it later. No other component talks to SQL Server directly.

## 2. Decisions Locked In

- **Stack:** TypeScript (strict) on **Node 24 LTS**, **Express 5**, **`mssql`** (Tedious) with a singleton connection pool, **zod** validation, **pino** logging, **`node:test` + `tsx`** for tests, `tsc` for the production build.
- **Scope of this build:** API service only. The search UI is a later, separate effort.
- **Deployment:** own Docker container on the same host as n8n, joined to the shared internal Docker network, **no published host port**.
- **Data sources (same SQL Server instance, single pool, fully-qualified names):**
  - Tickets: `CiresonAnalytics.dbo.SM_WorkItem_Incident` and `CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest` (warehouse, refreshed every 24h at 08:00 UTC — data is at most ~24h stale, accepted).
  - Users: `ServiceManager.dbo.MTV_System$Domain$User` (live SCSM projection, always fresh).
  - The SQL account needs `SELECT` on both databases.
- **Search:** SQL Server Full Text Search via `CONTAINS()` on ticket Title/Description/ResolutionDescription by default; `SEARCH_MODE=like` fallback if FTS indexes cannot be provisioned on the warehouse. User search is always `LIKE`. Same API contract either way.
- **API versioning:** all routes under `/v1/` so later consumers (Flask app, extension) get a stable contract.
- **Auth:** per-consumer static API keys (`X-API-Key` header), constant-time comparison.
- **No ORM.** Hand-tuned parameterized SQL through `mssql`.
- **`affectedUser.userId` is resolved on demand** (via `/v1/search/users`), not joined per search — keeps read load off the live ServiceManager DB.

## 3. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | TypeScript (strict) | Compile-time safety on query params and response shapes |
| Runtime | Node 24 LTS (`node:24-alpine`) | Node 20 (doc) is EOL; 22 is conservative alternative |
| Web framework | Express 5 | Current major; native async error handling |
| DB driver | `mssql` (node-mssql / Tedious) | Native SQL Server, connection pooling built in |
| Validation | `zod` | Coerce + validate query params in one step |
| Logging | `pino` + `pino-http` | Structured JSON logs |
| Tests | `node:test` + `tsx` | Consistent with repo's existing `node --test` usage |
| Build/dev | `tsc` / `tsx watch` | |
| Auth | Per-consumer `X-API-Key` | Keys rotate/revoke independently |
| Deploy | Multi-stage Dockerfile + compose | Non-root runtime user, healthcheck |

## 4. Project Structure

```
scsm-search/
  src/
    db/
      pool.ts               # singleton mssql pool, created once at startup
      queries/
        tickets.ts          # Incident + ServiceRequest query builders (shared projection)
        users.ts            # DomainUser query builder + id resolution
    routes/
      search.ts             # /v1/search/tickets, /v1/search/users
      users.ts              # /v1/users/:id/tickets
      health.ts             # /healthz
    schemas/
      searchParams.ts       # zod schemas for query params
    middleware/
      auth.ts               # X-API-Key check (constant-time compare)
      errorHandler.ts       # zod→400, mssql→500/503, uniform JSON error shape
    types/
      ticket.ts
      domainUser.ts
    server.ts               # express bootstrap + pool init
  tests/
    validation.test.ts      # zod coercion/edge cases
    auth.test.ts            # key accept/reject
    queryBuilders.test.ts   # generated SQL + bound params, all filter combos
    routes.test.ts          # supertest against app with mocked pool
  Dockerfile
  compose.scsm-search.yml   # service snippet for the n8n host stack
  package.json
  tsconfig.json
  .env.example
  .env                     # not committed
```

## 5. Real Schema (verified 2026-08-06)

### `CiresonAnalytics.dbo.SM_WorkItem_Incident` and `SM_WorkItem_ServiceRequest`

The two tables are structurally near-identical. Columns used:

| Column | Notes |
|---|---|
| `Id` | GUID PK |
| `WorkItemId` | Human-readable ticket number (e.g. `IR1234`) — exposed in API |
| `Title` | FTS column |
| `Description` | FTS column |
| `ResolutionDescription` | FTS column |
| `Status` | Text, exact-match filter |
| `Priority` | Text, exact-match filter (both types — SR has it too) |
| `Impact`, `Urgency` | Text (both types) |
| `Created` | Creation timestamp; drives date filter + ordering |
| `AffectedUser`, `AffectedUserId` | Denormalized name + GUID |
| `CreatedByUser`, `CreatedByUserId` | For `createdByUserId` filter |
| `AssignedUser`, `AssignedUserId` | For `assignedUserId` filter |

All `NWU_*`, `AlertCustomField*`, `CIId_*`, `Deployment_*`, etc. columns are out of scope.

### `ServiceManager.dbo.MTV_System$Domain$User`

| Column | API field |
|---|---|
| `BaseManagedEntityId` | `id` (GUID; matches ticket `*UserId` columns) |
| `DisplayName` | `displayName` |
| `UserName_6AF77E23_669B_123F_B392_323C17097BBD` | `userId` (domain login, e.g. `jsmith`) |
| `UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02` | `upn` (e.g. `jsmith@nwu.ac.za`) |

No `Email` column exists in the projection — the API exposes `upn` instead of the doc's `email`.

## 6. SQL Query Set

All queries parameterized. Pagination pattern: `ORDER BY ... OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY`, with a parallel `COUNT(*)` for `total`.

### 6.1 Ticket search (Incident; ServiceRequest is identical, table name swapped)

```sql
SELECT
    i.Id, i.WorkItemId, i.Title, i.Status, i.Priority,
    i.Impact, i.Urgency, i.Created AS CreatedDate,
    i.AffectedUser, i.AffectedUserId
FROM CiresonAnalytics.dbo.SM_WorkItem_Incident i
WHERE (@status   IS NULL OR i.Status  = @status)
  AND (@priority IS NULL OR i.Priority = @priority)
  AND (@from     IS NULL OR i.Created >= @from)
  AND (@to       IS NULL OR i.Created <  DATEADD(DAY, 1, @to))
  -- SEARCH_MODE=fts:
  AND (@q IS NULL OR CONTAINS((i.Title, i.Description, i.ResolutionDescription), @q))
  -- SEARCH_MODE=like:
  AND (@q IS NULL OR i.Title LIKE '%'+@q+'%' OR i.Description LIKE '%'+@q+'%'
                 OR i.ResolutionDescription LIKE '%'+@q+'%')
  AND (@affectedUserId IS NULL OR EXISTS (
        SELECT 1 FROM ServiceManager.dbo.MTV_System$Domain$User u
        WHERE u.BaseManagedEntityId = i.AffectedUserId
          AND u.UserName_6AF77E23_669B_123F_B392_323C17097BBD = @affectedUserId))
  AND (@createdByUserId IS NULL OR EXISTS (
        SELECT 1 FROM ServiceManager.dbo.MTV_System$Domain$User u
        WHERE u.BaseManagedEntityId = i.CreatedByUserId
          AND u.UserName_6AF77E23_669B_123F_B392_323C17097BBD = @createdByUserId))
  AND (@assignedUserId IS NULL OR EXISTS (
        SELECT 1 FROM ServiceManager.dbo.MTV_System$Domain$User u
        WHERE u.BaseManagedEntityId = i.AssignedUserId
          AND u.UserName_6AF77E23_669B_123F_B392_323C17097BBD = @assignedUserId))
ORDER BY i.Created DESC
OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY;
```

The user-role `EXISTS` clauses may also accept a UPN — the query builder binds the user identifier and matches `UserName_...` OR `UPN_...`.

### 6.2 User search

```sql
SELECT
    u.BaseManagedEntityId AS Id,
    u.UserName_6AF77E23_669B_123F_B392_323C17097BBD AS UserId,
    u.DisplayName,
    u.UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02 AS UPN
FROM ServiceManager.dbo.MTV_System$Domain$User u
WHERE (@q IS NULL OR u.DisplayName LIKE '%'+@q+'%'
                 OR u.UserName_6AF77E23_669B_123F_B392_323C17097BBD LIKE '%'+@q+'%'
                 OR u.UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02 LIKE '%'+@q+'%')
ORDER BY u.DisplayName
OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY;
```

Always `LIKE` — no FTS provisioning on the live-DB view.

### 6.3 `GET /v1/users/:id/tickets`

Step 1 — resolve `:id` (GUID, UserName, or UPN):

```sql
SELECT TOP (2) BaseManagedEntityId
FROM ServiceManager.dbo.MTV_System$Domain$User
WHERE BaseManagedEntityId = @id
   OR UserName_6AF77E23_669B_123F_B392_323C17097BBD = @id
   OR UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02 = @id;
```

- 1 match → step 2 with the resolved GUID
- 0 matches → 404
- 2+ matches → 400 (ambiguous)

Step 2 — fetch tickets:

```sql
SELECT 'incident'      AS TicketType, Id, WorkItemId, Title, Status, Priority, Created AS CreatedDate, AffectedUser, AffectedUserId
FROM CiresonAnalytics.dbo.SM_WorkItem_Incident          WHERE AffectedUserId = @userId
UNION ALL
SELECT 'servicerequest',          Id, WorkItemId, Title, Status, Priority, Created,                AffectedUser, AffectedUserId
FROM CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest    WHERE AffectedUserId = @userId
ORDER BY CreatedDate DESC
OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY;
```

## 7. API Contract

All endpoints read-only (`GET`). All filters optional except where noted. JSON responses.

### `GET /healthz`

Unauthenticated. Returns 200 when the process is up and the connection pool is connected. Used by the Docker healthcheck.

### `GET /v1/search/tickets`

| Param | Type | Notes |
|---|---|---|
| `q` | string | FTS term via `CONTAINS()` (title/description/resolution) — or `LIKE` in `like` mode |
| `type` | `incident` \| `servicerequest` | **Required**, selects table |
| `status` | string | Exact match |
| `priority` | string | Both types |
| `affectedUserId` | string | UserId or UPN; matches `AffectedUserId` |
| `createdByUserId` | string | UserId or UPN; matches `CreatedByUserId` |
| `assignedUserId` | string | UserId or UPN; matches `AssignedUserId` |
| `from`, `to` | ISO date | `Created` range |
| `page`, `pageSize` | number | Default `pageSize` 25 |

Response shape (stable):

```json
{
  "results": [
    {
      "id": "GUID",
      "workItemId": "IR1234",
      "title": "Printer not responding",
      "status": "Active",
      "priority": "2",
      "createdDate": "2026-07-01T09:00:00Z",
      "affectedUser": { "id": "GUID", "displayName": "John Smith" }
    }
  ],
  "page": 1,
  "pageSize": 25,
  "total": 134
}
```

`affectedUser.userId` is deliberately absent — resolved on demand via `/v1/search/users`.

### `GET /v1/search/users`

Params: `q` (DisplayName, UserId, or UPN), `page`, `pageSize`. Response: list of `{id, userId, displayName, upn}` — no additional HR/directory fields.

### `GET /v1/users/:id/tickets`

`:id` accepts GUID, UserId, or UPN (auto-detected). Merged Incidents and Service Requests, `ticketType` discriminator, sorted `createdDate` descending. The only place the two types merge.

### Error shape

Uniform JSON: `{ "error": { "code": string, "message": string } }`.
- 400 — validation failure / ambiguous user id
- 401 — missing/invalid API key
- 404 — user not found (`/v1/users/:id/tickets`)
- 500 — internal error
- 503 — DB pool unavailable

## 8. Data Layer

- **Singleton pool** in `db/pool.ts`: created once at server start, reused across requests, `encrypt: true`, `pool: { max: 10, min: 0, idleTimeoutMillis: 30000 }`.
- **One pool, two databases**, referenced by fully-qualified `db.schema.table` names. The `DB_USER` has `SELECT` on both CiresonAnalytics and ServiceManager.
- **Ticket query builders** share a single column projection constant; only the table name differs (Incident vs ServiceRequest). Merged only in `/v1/users/:id/tickets` (`UNION ALL`).
- **User query builder** covers `/v1/search/users` and `:id` resolution for `/v1/users/:id/tickets` and the user-role ticket filters.
- **FTS:** `CONTAINS()` in `SEARCH_MODE=fts` (default); `SEARCH_MODE=like` fallback — same contract, worse ranking. Startup probe checks FTS catalog availability and logs a warning if missing. FTS provisioning is an accepted risk; the SQL administrator will handle it in parallel.
- **Parameterized queries only.** Every filter is an `mssql` input param; no string concatenation.

## 9. Security

- **Read-only SQL account** (`SELECT` only on the relevant warehouse and user-view objects). No write permissions.
- **Per-consumer API keys** from `API_KEYS` env (comma-separated: n8n, pcm-compass, extension later). Constant-time comparison in `auth.ts`; missing/unknown key → 401.
- **No published host port** — reachable only on the shared internal Docker network (`http://scsm-search:3000`).
- **Minimal PII** — response shaping returns only identification/linking fields; no department, phone, office, employee id, etc.
- No rate limiting in v1 (internal-only, trusted consumers); future hardening if internet-facing.

## 10. Testing

- `node:test` + `tsx`. Suites:
  - `validation.test.ts` — zod coercion/edge cases (bad `type`, non-numeric page, invalid dates, missing required `type`, malformed `userId` values).
  - `auth.test.ts` — key accept/reject.
  - `queryBuilders.test.ts` — generated SQL + bound params for each filter combo; no injection; FTS vs LIKE branches; three user-role filters; `:id` resolution SQL; UNION ALL merge.
  - `routes.test.ts` — supertest against the app with a **mocked pool** (deterministic, no DB in CI).
- Manual smoke script against real CiresonAnalytics + ServiceManager with env creds (not part of CI).

## 11. Deployment

- **Multi-stage Dockerfile:** build stage (`node:24-alpine`, `npm ci`, `tsc`) → runtime stage (prod deps + `dist/`, non-root user, `CMD ["node","dist/server.js"]`).
- **`compose.scsm-search.yml`:** service `scsm-search`, `env_file: .env`, joined to the n8n internal network, `restart: unless-stopped`, healthcheck `GET /healthz`.
- **`.env.example`:** `DB_SERVER`, `DB_USER`, `DB_PASSWORD`, `API_KEYS`, `PORT=3000`, `SEARCH_MODE=fts`. (No `DB_NAME` — queries use fully-qualified names; default database is CiresonAnalytics.)
- n8n HTTP Request node: `http://scsm-search:3000/v1/search/tickets` + `X-API-Key` header.

## 12. Risks / Prerequisites

1. **FTS provisioning** — requires a DW SQL admin to create the FTS catalog/index on CiresonAnalytics ticket tables; without it, `SEARCH_MODE=like` fallback. In progress with the administrator.
2. **Cross-DB permissions** — the SQL account needs `SELECT` on both CiresonAnalytics ticket tables and `ServiceManager.dbo.MTV_System$Domain$User`.
3. **24h staleness** — accepted (warehouse refresh 08:00 UTC).
4. **SCSM deep-link format** — deferred with the UI work; does not affect the API service.
