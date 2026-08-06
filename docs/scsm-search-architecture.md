# SCSM Search Compensator: Architecture and Design

## 1. Purpose

SCSM's native search is slow and imprecise. This project adds a lightweight, dedicated search service that sits alongside SCSM, queries ticket and user data directly against SQL Server using proper indexing, and exposes it through a clean API. n8n consumes this API for orchestration (bots, digests, notifications) rather than talking to SQL Server directly. A frontend (Next.js) can also consume the same API for an interactive search UI.

This is not a replacement for SCSM. It is a read layer that makes SCSM's data searchable the way it should have been from day one.

---

## 2. Goals and Non-Goals

**Goals**
- Fast, relevance-ranked search across Incidents and Service Requests
- Filter by status, priority, ticket type, date range, and affected user
- Search DomainUser by name or ID, and pivot from a user to their tickets
- Keep the service small, stateless, and easy to deploy alongside the existing stack
- Avoid adding load to the live SCSM OLTP database

**Non-Goals**
- No write operations. This service is read-only. Ticket creation, updates, and resolution stay inside SCSM itself.
- Not a general purpose SCSM API replacement. Scope is limited to search and lookup.
- Not responsible for authentication of end users beyond what's needed to protect the API itself (see Security).

---

## 3. High-Level Architecture

```
                    ┌─────────────────────┐
                    │   SQL Server         │
                    │   (DWDataMart or      │
                    │   read-only replica)  │
                    │                      │
                    │  Incident            │
                    │  ServiceRequest      │
                    │  DomainUser          │
                    └─────────┬────────────┘
                              │ mssql connection pool
                              ▼
                    ┌─────────────────────┐
                    │  scsm-search API     │
                    │  (Node/Express)      │
                    │                      │
                    │  /search/tickets     │
                    │  /search/users        │
                    │  /users/:id/tickets   │
                    └─────────┬────────────┘
                              │ HTTP/JSON
              ┌───────────────┼────────────────┐
              ▼                                ▼
     ┌─────────────────┐              ┌─────────────────┐
     │   n8n             │              │  Next.js frontend │
     │  (bots, digests,   │              │  (search UI,       │
     │  scheduled jobs)   │              │  typeahead)         │
     └─────────────────┘              └─────────────────┘
```

The API is the single source of truth for how SCSM data gets queried. Nothing else talks to SQL Server directly.

---

## 4. Tech Stack

| Layer | Choice | Reasoning |
|---|---|---|
| Language | TypeScript | Matches your existing stack, gives you compile-time safety on query params and response shapes |
| Runtime | Node.js | Already your primary backend runtime |
| Web framework | Express | Minimal, well understood, no need for anything heavier at this scope |
| DB driver | `mssql` (node-mssql, Tedious under the hood) | Native SQL Server support, connection pooling built in |
| Search | SQL Server Full Text Search | Native to SQL Server, no extra infrastructure, gives relevance ranking that `LIKE` cannot |
| Validation | `zod` | Validate and type query params in one step |
| Frontend (optional, separate concern) | Next.js | Matches your after hours stack, can be a thin client against this API |
| Orchestration | n8n | Existing tool, used for scheduled jobs and bot integrations, not for direct DB access |
| Deployment | Docker container, added to your existing Docker stack | Keeps it isolated, restart-safe, and consistent with how you already run services |

No ORM. At this scope (three tables, read-only, hand-tuned queries for full text search), an ORM adds abstraction you don't need and can get in the way of writing precise `CONTAINS()` clauses. Parameterized raw SQL through `mssql` is simpler and faster to reason about.

---

## 5. Data Source Strategy

Query against the **Data Warehouse (DWDataMart)** or a **read-only replica**, not the live ServiceManager OLTP database. SCSM's transactional database is sensitive to additional read load and lock contention. The warehouse is built for reporting-style queries and already exists in most SCSM deployments.

If DWDataMart's ETL cadence is too slow for your needs (it typically syncs on a schedule, not real time), the fallback is a SQL Server read replica or an availability group readable secondary pointed at the live database. Either option keeps read traffic off the primary.

Add SQL Server Full Text Search indexes on:
- `Incident.Title`, `Incident.Description`, `Incident.ResolutionDescription`
- `ServiceRequest.Title`, `ServiceRequest.Description`
- `DomainUser.DisplayName`

This is the single highest-leverage change in the whole project. It's what actually fixes "SCSM search is bad," independent of any application code on top of it.

---

## 6. Data Model

Three tables, related as a hub-and-spoke shape with DomainUser as the shared reference point.

```
DomainUser
├── Id (GUID, PK)
├── UserId (string, e.g. domain login)
├── DisplayName
└── Email

Incident
├── Id (GUID, PK)
├── Title
├── Description
├── Status
├── Priority
├── Impact / Urgency
├── AffectedUserId (FK → DomainUser.Id)
├── CreatedDate
└── ResolutionDescription

ServiceRequest
├── Id (GUID, PK)
├── Title
├── Description
├── Status
├── AffectedUserId (FK → DomainUser.Id)
├── CreatedDate
└── (workflow-specific fields as needed)
```

Incidents and Service Requests are queried separately, not via `UNION`, at least initially. They have different filter fields (Impact/Urgency only exists on Incidents), and separate queries make pagination and filter validation simpler per ticket type. A unified view can be added later if a single merged result list turns out to be genuinely needed.

---

## 7. API Design

All endpoints are read-only (`GET`). All filters are optional except where noted. Response bodies are JSON.

### `GET /search/tickets`

Query params:

| Param | Type | Notes |
|---|---|---|
| `q` | string | Full text search term, matched against title/description via `CONTAINS()` |
| `type` | `incident` \| `servicerequest` | Required, determines which table is queried |
| `status` | string | Exact match |
| `priority` | string | Incidents only |
| `userId` | string | Filters by affected user's `UserId` |
| `from`, `to` | ISO date | Filters `CreatedDate` range |
| `page`, `pageSize` | number | Pagination, default `pageSize` of 25 |

Response:

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

### `GET /search/users`

Query params: `q` (matches `DisplayName` or `UserId`), `page`, `pageSize`.

Response: list of DomainUser records with `id`, `userId`, `displayName`, `email`.

### `GET /users/:id/tickets`

Returns Incidents and Service Requests linked to a given DomainUser, merged with a `ticketType` discriminator field, sorted by `createdDate` descending. This is the one place merging both ticket types makes sense, since it's a "show me everything for this person" view rather than a filtered search.

---

## 8. UX Design

### Search bar behavior

- A single search input drives full text search. As the user types (debounced, ~300ms), the frontend fires `GET /search/tickets` and `GET /search/users` in parallel if no type is locked in yet, so a query like "jsmith" can surface both a matching user and any tickets whose title or description mentions that term.
- A type toggle (Incidents / Service Requests / Both) sits next to the search bar. Selecting "Both" means two calls under the hood, shown as two result sections, not a merged list, so priority and impact fields (Incident-only) can still be shown where relevant.

### Filters

- Status, priority, and date range live in a collapsible filter panel beside the results, not inline in the search bar. This keeps the search bar itself simple and keeps filters visually distinct from free text search.
- Selecting a user from a `/search/users` result populates the `userId` filter on the ticket search rather than opening a separate page. This keeps "find the person, then see their tickets" as a two-click flow instead of a page navigation.

### Results

- Ticket results show title, status badge, priority badge (Incidents only), affected user name, and created date, in a table or card list depending on your existing frontend patterns.
- Clicking a result can either link out to the ticket's SCSM console URL (if SCSM exposes a stable deep link pattern) or show a read-only detail panel pulled from the same API. Deep linking to SCSM is simpler and avoids duplicating ticket detail rendering.
- Pagination is standard next/previous, driven by the `page`/`total` fields in the response.

### Empty and loading states

- Empty search box shows nothing, not a default "recent tickets" list, to keep the tool focused on search rather than becoming a dashboard.
- No results state should suggest loosening filters (e.g., "no matches. try removing the date filter") rather than a bare "no results."

---

## 9. Project Structure

```
scsm-search/
  src/
    db/
      pool.ts              # shared mssql connection pool, single instance
      queries/
        tickets.ts          # query builders for Incident/ServiceRequest
        users.ts             # query builders for DomainUser
    routes/
      search.ts             # /search/tickets, /search/users
      users.ts               # /users/:id/tickets
    schemas/
      searchParams.ts        # zod schemas for query param validation
    types/
      ticket.ts
      domainUser.ts
    server.ts                 # express app bootstrap
  Dockerfile
  docker-compose.yml (or entry in your existing compose stack)
  package.json
  tsconfig.json
  .env.example
```

### Connection pool pattern

One pooled connection, created once at startup, reused across requests. Never open a new connection per request.

```typescript
// db/pool.ts
import sql from 'mssql';

const config: sql.config = {
  server: process.env.DB_SERVER!,
  database: process.env.DB_NAME!,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  options: { encrypt: true, trustServerCertificate: false },
  pool: { max: 10, min: 0, idleTimeoutMillis: 30000 }
};

let poolPromise: Promise<sql.ConnectionPool> | null = null;

export function getPool() {
  if (!poolPromise) {
    poolPromise = new sql.ConnectionPool(config).connect();
  }
  return poolPromise;
}
```

---

## 10. Security Considerations

- **Read-only DB account.** The SQL login this service uses should have `SELECT` only on the relevant tables/views. No write permissions, ever, regardless of how trusted the network is.
- **API authentication.** Since this sits behind n8n and an internal frontend, an API key or internal network restriction (only reachable from your Docker network, not exposed publicly) is likely sufficient. No need for full OAuth at this scope unless the frontend is internet facing.
- **Parameterized queries only.** Every query param goes through `mssql`'s parameterized query support, never string concatenation, to eliminate SQL injection risk.
- **No PII beyond what's needed.** DomainUser results should return only what's needed for identification and linking (name, ID, email), not additional HR or directory fields that might live in the same table.

---

## 11. Deployment

Add this as its own service in your existing Docker stack, alongside `vision` and `evo`, rather than embedding it inside another app's container. A minimal `Dockerfile`:

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY dist ./dist
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

Environment variables (`.env`, not committed):

```
DB_SERVER=
DB_NAME=
DB_USER=
DB_PASSWORD=
API_KEY=
PORT=3000
```

Point n8n's HTTP Request node at `http://scsm-search:3000/search/tickets` (using the Docker service name if on the same network) with the API key in a header.

---

## 12. Open Questions to Resolve Before Building

1. **DWDataMart sync frequency.** Confirm how stale the warehouse data is allowed to be for this use case. If near-real-time search is required, a read replica of the live DB may be necessary instead.
2. **SCSM deep link format.** Confirm whether SCSM exposes a predictable URL pattern for opening a specific ticket, to decide whether result rows link out or render inline.
3. **Filter parity between ticket types.** Decide up front whether Incidents and Service Requests will always be filtered/displayed separately, or whether a unified view becomes necessary later. Building two separate route handlers now, sharing query-building utilities, keeps this flexible without overengineering a unified schema too early.

---

## 13. Summary

Read-only Node/Express service, its own Docker container, backed by SQL Server Full Text Search against DWDataMart or a replica. n8n and any frontend talk to this service over HTTP, never to SQL Server directly. Three tables, two route groups, one connection pool. Small enough to build in a few focused sessions, and the full text indexes do more for search quality than any amount of application code on top.
