# SCSM Search Service — Design

Date: 2026-08-06
Status: Approved (design review)

Companion doc: `docs/scsm-search-architecture.md` — this spec validates and refines that architecture for implementation. Where they differ, this spec wins.

## 1. Purpose

Build a read-only search API over SCSM ticket and user data, sourced from the **CiresonAnalytics** data warehouse. The API is the single query path into SCSM data — n8n consumes it now (bots, digests, scheduled jobs); the PCM Compass Flask app and Chrome extension consume it later. No other component talks to the warehouse directly.

## 2. Decisions Locked In

- **Stack:** TypeScript (strict) on **Node 24 LTS**, **Express 5**, **`mssql`** (Tedious) with a singleton connection pool, **zod** validation, **pino** logging, **`node:test` + `tsx`** for tests, `tsc` for the production build.
- **Scope of this build:** API service only. The search UI is a later, separate effort.
- **Deployment:** own Docker container on the same host as n8n, joined to the shared internal Docker network, **no published host port**.
- **Data source:** `CiresonAnalytics` warehouse, refreshed every 24h at 08:00 UTC. Data is at most ~24h stale — accepted.
- **Search:** SQL Server Full Text Search via `CONTAINS()` by default; `SEARCH_MODE=like` fallback if FTS indexes cannot be provisioned on the warehouse. Same API contract either way.
- **API versioning:** all routes under `/v1/` so later consumers (Flask app, extension) get a stable contract.
- **Auth:** per-consumer static API keys (`X-API-Key` header), constant-time comparison.
- **No ORM.** Hand-tuned parameterized SQL through `mssql`.

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
        tickets.ts          # Incident + ServiceRequest query builders
        users.ts            # DomainUser query builder
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

## 5. API Contract

All endpoints read-only (`GET`). All filters optional except where noted. JSON responses.

### `GET /healthz`

Unauthenticated. Returns 200 when the process is up and the connection pool is connected. Used by the Docker healthcheck.

### `GET /v1/search/tickets`

| Param | Type | Notes |
|---|---|---|
| `q` | string | FTS term via `CONTAINS()` (title/description/affected user name) — or `LIKE` in `like` mode |
| `type` | `incident` \| `servicerequest` | **Required**, selects table |
| `status` | string | Exact match |
| `priority` | string | Incidents only |
| `userId` | string | Filter by affected user's user id |
| `from`, `to` | ISO date | `CreatedDate` range |
| `page`, `pageSize` | number | Default `pageSize` 25 |

Response shape (stable):

```json
{
  "results": [
    {
      "id": "GUID",
      "title": "Printer not responding",
      "status": "Active",
      "priority": "2",
      "createdDate": "2026-07-01T09:00:00Z",
      "affectedUser": { "id": "GUID", "userId": "jsmith", "displayName": "John Smith" }
    }
  ],
  "page": 1,
  "pageSize": 25,
  "total": 134
}
```

### `GET /v1/search/users`

Params: `q` (DisplayName or UserId), `page`, `pageSize`. Response: list of `{id, userId, displayName, email}` — no additional HR/directory fields.

### `GET /v1/users/:id/tickets`

Merged Incidents and Service Requests for a DomainUser, `ticketType` discriminator, sorted `createdDate` descending. The only place the two types merge.

### Error shape

Uniform JSON: `{ "error": { "code": string, "message": string } }`.
- 400 — validation failure (zod)
- 401 — missing/invalid API key
- 500 — internal error
- 503 — DB pool unavailable

## 6. Data Layer

- **Singleton pool** in `db/pool.ts`: created once at server start, reused across requests, `encrypt: true`, `pool: { max: 10, min: 0, idleTimeoutMillis: 30000 }`.
- **Schema discovery is implementation task #1.** CiresonAnalytics table/column names are unknown and must be inspected first. Map warehouse columns to the canonical API shape once in `db/queries/`; API response fields stay fixed regardless of source column names.
- **Incidents and Service Requests** are separate query builders sharing utilities. Merged only in `/v1/users/:id/tickets`.
- **FTS:** `CONTAINS()` in `SEARCH_MODE=fts` (default). `SEARCH_MODE=like` fallback — same contract, worse ranking. Startup probe checks FTS catalog availability and logs a warning if missing. FTS provisioning is an accepted risk; the SQL administrator will handle it in parallel.
- **Parameterized queries only.** Every filter is an `mssql` input param; no string concatenation.

## 7. Security

- **Read-only SQL account** (`SELECT` only on the relevant warehouse tables). No write permissions.
- **Per-consumer API keys** from `API_KEYS` env (comma-separated: n8n, pcm-compass, extension later). Constant-time comparison in `auth.ts`; missing/unknown key → 401.
- **No published host port** — reachable only on the shared internal Docker network (`http://scsm-search:3000`).
- **Minimal PII** — response shaping returns only identification/linking fields.
- No rate limiting in v1 (internal-only, trusted consumers); future hardening if internet-facing.

## 8. Testing

- `node:test` + `tsx`. Suites:
  - `validation.test.ts` — zod coercion/edge cases (bad `type`, non-numeric page, invalid dates, missing required `type`).
  - `auth.test.ts` — key accept/reject.
  - `queryBuilders.test.ts` — generated SQL + bound params for each filter combo; no injection; FTS vs LIKE branches.
  - `routes.test.ts` — supertest against the app with a **mocked pool** (deterministic, no DB in CI).
- Manual smoke script against real CiresonAnalytics with env creds (not part of CI).

## 9. Deployment

- **Multi-stage Dockerfile:** build stage (`node:24-alpine`, `npm ci`, `tsc`) → runtime stage (prod deps + `dist/`, non-root user, `CMD ["node","dist/server.js"]`).
- **`compose.scsm-search.yml`:** service `scsm-search`, `env_file: .env`, joined to the n8n internal network, `restart: unless-stopped`, healthcheck `GET /healthz`.
- **`.env.example`:** `DB_SERVER`, `DB_NAME=CiresonAnalytics`, `DB_USER`, `DB_PASSWORD`, `API_KEYS`, `PORT=3000`, `SEARCH_MODE=fts`.
- n8n HTTP Request node: `http://scsm-search:3000/v1/search/tickets` + `X-API-Key` header.

## 10. Risks / Prerequisites

1. **FTS provisioning** — requires a DW SQL admin; without it, `SEARCH_MODE=like` fallback. In progress with the administrator.
2. **Schema mapping** — blocked on inspecting CiresonAnalytics; first implementation task.
3. **24h staleness** — accepted (warehouse refresh 08:00 UTC).
4. **SCSM deep-link format** — deferred with the UI work; does not affect the API service.
