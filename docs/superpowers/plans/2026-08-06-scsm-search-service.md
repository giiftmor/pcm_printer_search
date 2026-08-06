# SCSM Search Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only, Dockerized Node/TypeScript search API over SCSM ticket data (CiresonAnalytics warehouse) and user data (ServiceManager projection), consumed by n8n now and by PCM Compass later.

**Architecture:** Express 5 app backed by a singleton `mssql` connection pool. Query builders generate parameterized SQL with a shared column projection between Incident/ServiceRequest, `CONTAINS()` full-text search with a `LIKE` fallback, and a `UNION ALL` merge for per-user tickets. zod validates query params; a per-consumer `X-API-Key` protects all `/v1` routes; a uniform JSON error shape covers validation/DB/internal failures. Deployed as its own container on the n8n host's internal Docker network.

**Tech Stack:** TypeScript (strict), Node 24 LTS, Express 5, mssql (Tedious), zod, pino, node:test + tsx, supertest.

**Repository:** New git repo at `~/projects/scsm-search` (git init now, GitHub remote later). All commits below happen in that repo unless a task says otherwise.

## Global Constraints

- Runtime: Node >= 22 (Docker image `node:24-alpine`).
- SQL is parameterized only — never string-concatenate user input into SQL.
- Verbatim source-of-truth object/column names:
  - `CiresonAnalytics.dbo.SM_WorkItem_Incident`, `CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest`
  - `ServiceManager.dbo.MTV_System$Domain$User`
  - `BaseManagedEntityId`, `UserName_6AF77E23_669B_123F_B392_323C17097BBD`, `UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02`
- Ticket search columns for FTS/LIKE: `Title`, `Description`, `ResolutionDescription`.
- API version prefix `/v1/`; `/healthz` is unauthenticated, everything under `/v1/` requires `X-API-Key`.
- `SEARCH_MODE` env: `fts` (default) or `like`. User search is always `LIKE`.
- No ORM. No secrets in the repo; `.env` never committed.
- Scripts: `npm test` = `node --import tsx --test tests/*.test.ts`; `npm run build` = `tsc`; `npm run dev` = `tsx watch src/server.ts`.
- ESM (`"type": "module"`); imports use `.js` extensions (NodeNext resolution).

---

### Task 1: Scaffold + config + exec/pool + health + error handler

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/config.ts`
- Create: `src/db/exec.ts`
- Create: `src/db/pool.ts`
- Create: `src/routes/health.ts`
- Create: `src/middleware/errorHandler.ts`
- Test: `tests/config.test.ts`
- Test: `tests/health.test.ts`

**Interfaces:**
- Consumes: nothing (bootstrap).
- Produces:
  - `loadConfig(env?: NodeJS.ProcessEnv): AppConfig` from `src/config.ts` (`AppConfig = { dbServer, dbUser, dbPassword, apiKeys: string[], port: number, searchMode: 'fts'|'like' }`)
  - `exec<T>(pool: ConnectionPool, query: PreparedQuery): Promise<T[]>` and `PreparedQuery = { sql: string; inputs: Record<string, string|number|Date> }` from `src/db/exec.ts`
  - `makePool(config: AppConfig): sql.ConnectionPool` from `src/db/pool.ts`
  - `healthRouter(opts: { pool: ConnectionPool }): Router` from `src/routes/health.ts`
  - `errorHandler: ErrorRequestHandler` from `src/middleware/errorHandler.ts`

- [ ] **Step 1: Init repo and scaffolding files**

```bash
mkdir -p ~/projects/scsm-search/src/db ~/projects/scsm-search/src/routes ~/projects/scsm-search/src/middleware ~/projects/scsm-search/tests
cd ~/projects/scsm-search && git init
```

`package.json`:
```json
{
  "name": "scsm-search",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22" },
  "scripts": {
    "dev": "tsx watch src/server.ts",
    "build": "tsc",
    "start": "node dist/server.js",
    "test": "node --import tsx --test tests/*.test.ts"
  }
}
```

`tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "dist",
    "rootDir": "src",
    "sourceMap": true,
    "types": ["node"]
  },
  "include": ["src"]
}
```

`.gitignore`:
```
node_modules/
dist/
.env
*.log
```

`.env.example`:
```
DB_SERVER=
DB_USER=
DB_PASSWORD=
API_KEYS=
PORT=3000
SEARCH_MODE=fts
```

Install dependencies:
```bash
cd ~/projects/scsm-search && npm install express@^5 mssql@^11 zod@^3 pino@^9 pino-http@^10
cd ~/projects/scsm-search && npm install -D typescript@^5 tsx@^4 @types/node@^24 @types/express@^5 supertest@^7 @types/supertest@^6
```

- [ ] **Step 2: Write the failing config test**

`tests/config.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadConfig } from '../src/config.js';

test('config: parses defaults when env is empty', () => {
  const c = loadConfig({});
  assert.equal(c.dbServer, '');
  assert.deepEqual(c.apiKeys, []);
  assert.equal(c.port, 3000);
  assert.equal(c.searchMode, 'fts');
});

test('config: parses api keys and search mode', () => {
  const c = loadConfig({ API_KEYS: ' n8n-secret , compass-secret ', SEARCH_MODE: 'like', PORT: '5000' });
  assert.deepEqual(c.apiKeys, ['n8n-secret', 'compass-secret']);
  assert.equal(c.searchMode, 'like');
  assert.equal(c.port, 5000);
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/projects/scsm-search && npm test`
Expected: FAIL with "Cannot find module" / no test files.

- [ ] **Step 4: Implement `src/config.ts`**

```ts
export interface AppConfig {
  dbServer: string;
  dbUser: string;
  dbPassword: string;
  apiKeys: string[];
  port: number;
  searchMode: 'fts' | 'like';
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  return {
    dbServer: env.DB_SERVER ?? '',
    dbUser: env.DB_USER ?? '',
    dbPassword: env.DB_PASSWORD ?? '',
    apiKeys: (env.API_KEYS ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
    port: Number(env.PORT ?? 3000),
    searchMode: env.SEARCH_MODE === 'like' ? 'like' : 'fts',
  };
}
```

- [ ] **Step 5: Implement `src/db/exec.ts`, `src/db/pool.ts`, `src/routes/health.ts`, `src/middleware/errorHandler.ts`**

`src/db/exec.ts`:
```ts
import type { ConnectionPool, IResult } from 'mssql';

export interface PreparedQuery {
  sql: string;
  inputs: Record<string, string | number | Date>;
}

export async function exec<T>(pool: ConnectionPool, query: PreparedQuery): Promise<T[]> {
  const req = pool.request();
  for (const [key, value] of Object.entries(query.inputs)) {
    req.input(key, value);
  }
  const result: IResult<T> = await req.query<T>(query.sql);
  return result.recordset;
}
```

`src/db/pool.ts`:
```ts
import sql from 'mssql';
import type { AppConfig } from '../config.js';

export function makePool(config: AppConfig): sql.ConnectionPool {
  return new sql.ConnectionPool({
    server: config.dbServer,
    user: config.dbUser,
    password: config.dbPassword,
    database: 'CiresonAnalytics',
    options: { encrypt: true, trustServerCertificate: false },
    pool: { max: 10, min: 0, idleTimeoutMillis: 30000 },
  });
}
```

`src/routes/health.ts`:
```ts
import { Router } from 'express';
import type { ConnectionPool } from 'mssql';
import { exec } from '../db/exec.js';

export function healthRouter(opts: { pool: ConnectionPool }): Router {
  const router = Router();
  router.get('/', async (_req, res) => {
    await exec(opts.pool, { sql: 'SELECT 1 AS ok', inputs: {} });
    res.json({ status: 'ok' });
  });
  return router;
}
```

`src/middleware/errorHandler.ts`:
```ts
import type { ErrorRequestHandler } from 'express';
import { ZodError } from 'zod';

function isConnectionError(err: unknown): boolean {
  if (err && typeof err === 'object' && 'code' in err) {
    const code = String((err as { code?: unknown }).code);
    return ['ECONNREFUSED', 'ENOTFOUND', 'ETIMEOUT', 'ESOCKET'].includes(code);
  }
  return false;
}

export const errorHandler: ErrorRequestHandler = (err, _req, res, _next) => {
  if (err instanceof ZodError) {
    res.status(400).json({
      error: { code: 'VALIDATION', message: 'Invalid query parameters', details: err.flatten().fieldErrors },
    });
    return;
  }
  if (isConnectionError(err)) {
    res.status(503).json({ error: { code: 'DB_UNAVAILABLE', message: 'Database unavailable' } });
    return;
  }
  res.status(500).json({ error: { code: 'INTERNAL', message: 'Internal server error' } });
};
```

- [ ] **Step 6: Write the health route tests (test-first)**

`tests/health.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import express from 'express';
import type { ConnectionPool } from 'mssql';
import { healthRouter } from '../src/routes/health.js';
import { errorHandler } from '../src/middleware/errorHandler.js';

function fakePool(fail = false): ConnectionPool {
  return {
    request() {
      return {
        input() {},
        async query() {
          if (fail) {
            const err = new Error('connect ECONNREFUSED') as Error & { code: string };
            err.code = 'ECONNREFUSED';
            throw err;
          }
          return { recordset: [{ ok: 1 }] };
        },
      };
    },
  } as unknown as ConnectionPool;
}

function makeApp(pool: ConnectionPool) {
  const app = express();
  app.use('/healthz', healthRouter({ pool }));
  app.use(errorHandler);
  return app;
}

test('healthz returns 200 when pool responds', async () => {
  const res = await request(makeApp(fakePool())).get('/healthz');
  assert.equal(res.status, 200);
  assert.deepEqual(res.body, { status: 'ok' });
});

test('healthz returns 503 when pool is unreachable', async () => {
  const res = await request(makeApp(fakePool(true))).get('/healthz');
  assert.equal(res.status, 503);
  assert.equal(res.body.error.code, 'DB_UNAVAILABLE');
});

test('unknown route falls through to 404 with uniform shape', async () => {
  const res = await request(makeApp(fakePool())).get('/nope');
  assert.equal(res.status, 404);
  assert.equal(res.body.error.message, 'Not found');
});
```

The 404 fallback doesn't exist yet — add it in the health test setup by appending a catch-all after `errorHandler`:
```ts
  app.use(errorHandler);
  app.use((_req, res) => {
    res.status(404).json({ error: { code: 'NOT_FOUND', message: 'Not found' } });
  });
```
(Use this `makeApp` version — the catch-all comes after `errorHandler` so it still runs; the final ordering in `createApp` (Task 8) puts 404 before `errorHandler`.)

- [ ] **Step 7: Run all tests**

Run: `cd ~/projects/scsm-search && npm test`
Expected: all PASS (config + health suites).

- [ ] **Step 8: Verify the production build compiles**

Run: `cd ~/projects/scsm-search && npm run build`
Expected: `dist/` produced with no type errors.

- [ ] **Step 9: Commit**

```bash
cd ~/projects/scsm-search
git add .
git commit -m "chore: scaffold scsm-search (TS/Express 5), config, pool, exec, health, error handler"
```

---

### Task 2: Domain types + zod validation schemas

**Files:**
- Create: `src/types/domainUser.ts`
- Create: `src/types/ticket.ts`
- Create: `src/schemas/searchParams.ts`
- Test: `tests/validation.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - Types `DomainUserRow { Id, UserId, DisplayName, UPN }`, `TicketRow { Id, WorkItemId, Title, Status, Priority, CreatedDate, AffectedUser, AffectedUserId }`, `UserTicketRow = TicketRow & { TicketType }`, `TicketResult { id, workItemId, title, status, priority, createdDate, affectedUser, ticketType? }`
  - `ticketSearchParamsSchema`, `userSearchParamsSchema`, `userTicketsParamsSchema` (zod), with inferred types `TicketSearchParams`, `UserSearchParams`, `UserTicketsParams`

- [ ] **Step 1: Write the failing validation test**

`tests/validation.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  ticketSearchParamsSchema,
  userSearchParamsSchema,
  userTicketsParamsSchema,
} from '../src/schemas/searchParams.js';

test('ticket search: requires type', () => {
  assert.throws(() => ticketSearchParamsSchema.parse({}), (e: any) => e.issues?.[0].path[0] === 'type');
});

test('ticket search: rejects unknown type', () => {
  assert.throws(() => ticketSearchParamsSchema.parse({ type: 'change' }));
});

test('ticket search: coerces page params to numbers', () => {
  const p = ticketSearchParamsSchema.parse({ type: 'incident', page: '3', pageSize: '50' });
  assert.equal(p.page, 3);
  assert.equal(p.pageSize, 50);
});

test('ticket search: defaults page/pageSize', () => {
  const p = ticketSearchParamsSchema.parse({ type: 'incident' });
  assert.equal(p.page, 1);
  assert.equal(p.pageSize, 25);
});

test('ticket search: parses ISO dates', () => {
  const p = ticketSearchParamsSchema.parse({ type: 'incident', from: '2026-07-01', to: '2026-07-31T00:00:00Z' });
  assert.ok(p.from instanceof Date);
  assert.ok(p.to instanceof Date);
});

test('ticket search: rejects invalid page values', () => {
  assert.throws(() => ticketSearchParamsSchema.parse({ type: 'incident', page: '0' }));
  assert.throws(() => ticketSearchParamsSchema.parse({ type: 'incident', pageSize: '101' }));
});

test('ticket search: rejects invalid date', () => {
  assert.throws(() => ticketSearchParamsSchema.parse({ type: 'incident', from: 'not-a-date' }));
});

test('user search: defaults applied', () => {
  const p = userSearchParamsSchema.parse({});
  assert.equal(p.page, 1);
  assert.equal(p.pageSize, 25);
});

test('user tickets: defaults applied', () => {
  const p = userTicketsParamsSchema.parse({});
  assert.equal(p.page, 1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/scsm-search && npm test`
Expected: FAIL with "Cannot find module '../src/schemas/searchParams.js'".

- [ ] **Step 3: Implement types and schemas**

`src/types/domainUser.ts`:
```ts
export interface DomainUserRow {
  Id: string;
  UserId: string;
  DisplayName: string;
  UPN: string;
}
```

`src/types/ticket.ts`:
```ts
export type TicketType = 'incident' | 'servicerequest';

export interface TicketRow {
  Id: string;
  WorkItemId: string;
  Title: string;
  Status: string;
  Priority: string;
  CreatedDate: Date | string;
  AffectedUser: string | null;
  AffectedUserId: string | null;
}

export interface UserTicketRow extends TicketRow {
  TicketType: TicketType;
}

export interface AffectedUserResult {
  id: string;
  displayName: string;
}

export interface TicketResult {
  id: string;
  workItemId: string;
  title: string;
  status: string;
  priority: string;
  createdDate: string;
  affectedUser: AffectedUserResult | null;
  ticketType?: TicketType;
}
```

`src/schemas/searchParams.ts`:
```ts
import { z } from 'zod';

export const ticketSearchParamsSchema = z.object({
  q: z.string().trim().max(200).optional(),
  type: z.enum(['incident', 'servicerequest']),
  status: z.string().trim().max(100).optional(),
  priority: z.string().trim().max(100).optional(),
  affectedUserId: z.string().trim().max(256).optional(),
  createdByUserId: z.string().trim().max(256).optional(),
  assignedUserId: z.string().trim().max(256).optional(),
  from: z.coerce.date().optional(),
  to: z.coerce.date().optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(25),
});

export const userSearchParamsSchema = z.object({
  q: z.string().trim().max(200).optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(25),
});

export const userTicketsParamsSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(25),
});

export type TicketSearchParams = z.infer<typeof ticketSearchParamsSchema>;
export type UserSearchParams = z.infer<typeof userSearchParamsSchema>;
export type UserTicketsParams = z.infer<typeof userTicketsParamsSchema>;
```

- [ ] **Step 4: Run tests**

Run: `cd ~/projects/scsm-search && npm test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/scsm-search
git add src/types src/schemas tests/validation.test.ts
git commit -m "feat: domain types and zod query-param validation schemas"
```

---

### Task 3: API key auth middleware

**Files:**
- Create: `src/middleware/auth.ts`
- Test: `tests/auth.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `createAuthMiddleware(apiKeys: string[]): (req, res, next) => void` — returns a Router-level middleware that 401s (uniform error shape) on missing/invalid `x-api-key`.

- [ ] **Step 1: Write the failing auth test**

`tests/auth.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import express from 'express';
import { createAuthMiddleware } from '../src/middleware/auth.js';

function makeApp() {
  const app = express();
  app.use(createAuthMiddleware(['n8n-secret', 'compass-secret']));
  app.get('/protected', (_req, res) => res.json({ ok: true }));
  return app;
}

test('rejects missing API key with 401', async () => {
  const res = await request(makeApp()).get('/protected');
  assert.equal(res.status, 401);
  assert.equal(res.body.error.code, 'UNAUTHORIZED');
});

test('rejects wrong API key', async () => {
  const res = await request(makeApp()).get('/protected').set('x-api-key', 'wrong');
  assert.equal(res.status, 401);
});

test('accepts a valid API key', async () => {
  const res = await request(makeApp()).get('/protected').set('x-api-key', 'n8n-secret');
  assert.equal(res.status, 200);
});

test('accepts any configured key', async () => {
  const res = await request(makeApp()).get('/protected').set('x-api-key', 'compass-secret');
  assert.equal(res.status, 200);
});

test('empty key list rejects everything', async () => {
  const app = express();
  app.use(createAuthMiddleware([]));
  app.get('/x', (_req, res) => res.json({}));
  const res = await request(app).get('/x').set('x-api-key', 'anything');
  assert.equal(res.status, 401);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/scsm-search && npm test`
Expected: FAIL with "Cannot find module '../src/middleware/auth.js'".

- [ ] **Step 3: Implement `src/middleware/auth.ts`**

```ts
import { createHash, timingSafeEqual } from 'node:crypto';
import type { Request, Response, NextFunction } from 'express';

function constantTimeEqual(a: string, b: string): boolean {
  const ha = createHash('sha256').update(a).digest();
  const hb = createHash('sha256').update(b).digest();
  return timingSafeEqual(ha, hb);
}

export function createAuthMiddleware(apiKeys: string[]) {
  return function auth(req: Request, res: Response, next: NextFunction): void {
    const provided = req.header('x-api-key');
    if (!provided || !apiKeys.some((key) => constantTimeEqual(key, provided))) {
      res.status(401).json({ error: { code: 'UNAUTHORIZED', message: 'Missing or invalid API key' } });
      return;
    }
    next();
  };
}
```

- [ ] **Step 4: Run tests**

Run: `cd ~/projects/scsm-search && npm test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/scsm-search
git add src/middleware/auth.ts tests/auth.test.ts
git commit -m "feat: constant-time X-API-Key auth middleware"
```

---

### Task 4: User query builder

**Files:**
- Create: `src/db/queries/users.ts`
- Test: `tests/queryBuilders-users.test.ts`

**Interfaces:**
- Consumes: `PreparedQuery` from `src/db/exec.ts` (Task 1).
- Produces (used by Tasks 6, 7):
  - `buildSearchUsersQuery(p: { q?: string; page: number; pageSize: number }): PreparedQuery`
  - `buildCountUsersQuery(p: { q?: string }): PreparedQuery`
  - `buildResolveUserQuery(id: string): PreparedQuery` — `SELECT TOP (2) ... WHERE BaseManagedEntityId = @id OR UserName... = @id OR UPN... = @id`
  - Exported constants `USER_TABLE`, `USERNAME_COL`, `UPN_COL` (reused by the ticket builder in Task 5).

- [ ] **Step 1: Write the failing query-builder test**

`tests/queryBuilders-users.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildSearchUsersQuery,
  buildCountUsersQuery,
  buildResolveUserQuery,
} from '../src/db/queries/users.js';

test('search users: no q -> no WHERE clause, correct pagination', () => {
  const q = buildSearchUsersQuery({ page: 2, pageSize: 25 });
  assert.ok(!q.sql.includes('WHERE'));
  assert.deepEqual(q.inputs, { offset: 25, pageSize: 25 });
  assert.ok(q.sql.includes('ORDER BY u.DisplayName'));
  assert.ok(q.sql.includes('OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY'));
});

test('search users: q matches username, displayname, or upn', () => {
  const q = buildSearchUsersQuery({ q: 'jsmith', page: 1, pageSize: 25 });
  assert.ok(q.sql.includes('@q'));
  assert.equal(q.inputs.q, 'jsmith');
  assert.ok(q.sql.includes('UserName_6AF77E23_669B_123F_B392_323C17097BBD'));
  assert.ok(q.sql.includes('UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02'));
  assert.ok(q.sql.includes('ServiceManager.dbo.MTV_System$Domain$User'));
});

test('search users: value is parameterized, never inlined', () => {
  const q = buildSearchUsersQuery({ q: "x' OR 1=1 --", page: 1, pageSize: 25 });
  assert.ok(q.sql.includes('@q'));
  assert.ok(!q.sql.includes("x'"));
});

test('count users mirrors the where clause', () => {
  const q = buildCountUsersQuery({ q: 'smith' });
  assert.ok(q.sql.startsWith('SELECT COUNT(*) AS Total'));
  assert.ok(q.sql.includes('@q'));
});

test('resolve user: matches guid, username, or upn', () => {
  const q = buildResolveUserQuery('jsmith');
  assert.ok(q.sql.includes('BaseManagedEntityId = @id'));
  assert.ok(q.sql.includes('UserName_6AF77E23_669B_123F_B392_323C17097BBD = @id'));
  assert.ok(q.sql.includes('UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02 = @id'));
  assert.deepEqual(q.inputs, { id: 'jsmith' });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/scsm-search && npm test`
Expected: FAIL with "Cannot find module '../src/db/queries/users.js'".

- [ ] **Step 3: Implement `src/db/queries/users.ts`**

```ts
import type { PreparedQuery } from '../exec.js';

export const USER_TABLE = 'ServiceManager.dbo.MTV_System$Domain$User';
export const USERNAME_COL = 'u.UserName_6AF77E23_669B_123F_B392_323C17097BBD';
export const UPN_COL = 'u.UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02';

const USER_COLUMNS = `
  u.BaseManagedEntityId AS Id,
  ${USERNAME_COL} AS UserId,
  u.DisplayName,
  ${UPN_COL} AS UPN`;

export interface SearchUsersParams {
  q?: string;
  page: number;
  pageSize: number;
}

function userWhere(q?: string): { where: string[]; inputs: Record<string, string | number> } {
  const where: string[] = [];
  const inputs: Record<string, string> = {};
  if (q) {
    where.push(
      `(${USERNAME_COL} LIKE '%' + @q + '%' OR u.DisplayName LIKE '%' + @q + '%' OR ${UPN_COL} LIKE '%' + @q + '%')`
    );
    inputs.q = q;
  }
  return { where, inputs };
}

export function buildSearchUsersQuery(p: SearchUsersParams): PreparedQuery {
  const { where, inputs } = userWhere(p.q);
  inputs.offset = (p.page - 1) * p.pageSize;
  inputs.pageSize = p.pageSize;
  const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';
  return {
    sql: `SELECT ${USER_COLUMNS}
FROM ${USER_TABLE} u
${whereSql}
ORDER BY u.DisplayName
OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY;`,
    inputs,
  };
}

export function buildCountUsersQuery(p: { q?: string }): PreparedQuery {
  const { where, inputs } = userWhere(p.q);
  const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';
  return { sql: `SELECT COUNT(*) AS Total
FROM ${USER_TABLE} u
${whereSql};`, inputs };
}

export function buildResolveUserQuery(id: string): PreparedQuery {
  return {
    sql: `SELECT TOP (2) u.BaseManagedEntityId AS Id
FROM ${USER_TABLE} u
WHERE u.BaseManagedEntityId = @id
   OR ${USERNAME_COL} = @id
   OR ${UPN_COL} = @id;`,
    inputs: { id },
  };
}
```

- [ ] **Step 4: Run tests**

Run: `cd ~/projects/scsm-search && npm test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/scsm-search
git add src/db/queries/users.ts tests/queryBuilders-users.test.ts
git commit -m "feat: user query builders (search, count, id resolution)"
```

---

### Task 5: Ticket query builders + row serializer

**Files:**
- Create: `src/db/queries/tickets.ts`
- Create: `src/serializers/ticket.ts`
- Test: `tests/queryBuilders-tickets.test.ts`

**Interfaces:**
- Consumes: `PreparedQuery` (Task 1); `USER_TABLE` (Task 4); `TicketRow`/`TicketResult` types (Task 2).
- Produces (used by Tasks 6, 7):
  - `ticketTable(kind: 'incident'|'servicerequest'): string`
  - `buildTicketWhere(p: SearchTicketsParams, searchMode: 'fts'|'like'): { where: string[]; inputs: Record<string, string|number|Date> }`
  - `buildSearchTicketsQuery(p: SearchTicketsParams, searchMode: 'fts'|'like'): PreparedQuery`
  - `buildCountTicketsQuery(p: SearchTicketsParams, searchMode: 'fts'|'like'): PreparedQuery`
  - `buildUserTicketsQuery(userId: string, p: { page: number; pageSize: number }): PreparedQuery` (UNION ALL with `TicketType`)
  - `buildCountUserTicketsQuery(userId: string): PreparedQuery`
  - `rowToTicket(row: TicketRow): TicketResult` from `src/serializers/ticket.ts`
  - `SearchTicketsParams = { q?, type: 'incident'|'servicerequest', status?, priority?, affectedUserId?, createdByUserId?, assignedUserId?, from?, to?, page, pageSize }`

- [ ] **Step 1: Write the failing query-builder test**

`tests/queryBuilders-tickets.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildSearchTicketsQuery,
  buildCountTicketsQuery,
  buildUserTicketsQuery,
  buildCountUserTicketsQuery,
} from '../src/db/queries/tickets.js';
import { rowToTicket } from '../src/serializers/ticket.js';

const base = { type: 'incident', page: 1, pageSize: 25 } as const;

test('search tickets: selects the incident table', () => {
  const q = buildSearchTicketsQuery(base, 'fts');
  assert.ok(q.sql.includes('FROM CiresonAnalytics.dbo.SM_WorkItem_Incident'));
  assert.ok(!q.sql.includes('ServiceRequest'));
});

test('search tickets: selects the servicerequest table', () => {
  const q = buildSearchTicketsQuery({ ...base, type: 'servicerequest' }, 'fts');
  assert.ok(q.sql.includes('FROM CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest'));
});

test('search tickets: fts mode uses CONTAINS and strips quotes', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'printer "HP"' }, 'fts');
  assert.ok(q.sql.includes('CONTAINS((Title, Description, ResolutionDescription), @q)'));
  assert.equal(q.inputs.q, 'printer HP');
});

test('search tickets: like mode uses LIKE', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'printer' }, 'like');
  assert.ok(q.sql.includes("Title LIKE '%' + @q + '%'"));
  assert.ok(!q.sql.includes('CONTAINS'));
});

test('search tickets: all filters bind as parameters', () => {
  const q = buildSearchTicketsQuery(
    {
      ...base,
      status: 'Active',
      priority: '2',
      affectedUserId: 'jsmith',
      createdByUserId: 'jbloggs',
      assignedUserId: 'jdoe',
      from: new Date('2026-07-01'),
      to: new Date('2026-07-31'),
    },
    'fts'
  );
  assert.ok(q.sql.includes('Status = @status'));
  assert.ok(q.sql.includes('Priority = @priority'));
  assert.ok(q.sql.includes('AffectedUserId'));
  assert.ok(q.sql.includes('CreatedByUserId'));
  assert.ok(q.sql.includes('AssignedUserId'));
  assert.ok(q.sql.includes('Created >= @from'));
  assert.ok(q.sql.includes('DATEADD(DAY, 1, @to)'));
  assert.equal(q.inputs.status, 'Active');
  assert.equal(q.inputs.affectedUserId, 'jsmith');
  assert.ok(q.inputs.from instanceof Date);
});

test('search tickets: value is parameterized, never inlined', () => {
  const q = buildSearchTicketsQuery({ ...base, q: "'; DROP TABLE x; --" }, 'fts');
  assert.ok(q.sql.includes('@q'));
  assert.ok(!q.sql.includes('DROP'));
});

test('search tickets: pagination params', () => {
  const q = buildSearchTicketsQuery({ ...base, page: 3, pageSize: 50 }, 'fts');
  assert.deepEqual(q.inputs.offset, 100);
  assert.deepEqual(q.inputs.pageSize, 50);
  assert.ok(q.sql.includes('OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY'));
});

test('count tickets shares the where clause', () => {
  const q = buildCountTicketsQuery({ ...base, status: 'Active' }, 'fts');
  assert.ok(q.sql.startsWith('SELECT COUNT(*) AS Total'));
  assert.ok(q.sql.includes('Status = @status'));
});

test('user tickets: union all with discriminator and pagination', () => {
  const q = buildUserTicketsQuery('GUID', { page: 2, pageSize: 25 });
  assert.ok(q.sql.includes("'incident' AS TicketType"));
  assert.ok(q.sql.includes("SELECT 'servicerequest'"));
  assert.ok(q.sql.includes('UNION ALL'));
  assert.ok(q.sql.includes('ORDER BY CreatedDate DESC'));
  assert.deepEqual(q.inputs, { userId: 'GUID', offset: 25, pageSize: 25 });
});

test('count user tickets: subquery union', () => {
  const q = buildCountUserTicketsQuery('GUID');
  assert.ok(q.sql.includes('UNION ALL'));
  assert.ok(q.sql.includes('COUNT(*)'));
});

test('rowToTicket maps a row to the API shape', () => {
  const row = {
    Id: 'a',
    WorkItemId: 'IR1',
    Title: 't',
    Status: 'Active',
    Priority: '2',
    CreatedDate: new Date('2026-07-01T09:00:00Z'),
    AffectedUser: 'John Smith',
    AffectedUserId: 'g',
  };
  const t = rowToTicket(row);
  assert.equal(t.workItemId, 'IR1');
  assert.equal(t.createdDate, '2026-07-01T09:00:00.000Z');
  assert.deepEqual(t.affectedUser, { id: 'g', displayName: 'John Smith' });
});

test('rowToTicket handles a null affected user', () => {
  const row = {
    Id: 'a',
    WorkItemId: 'IR1',
    Title: 't',
    Status: 'Active',
    Priority: '2',
    CreatedDate: '2026-07-01',
    AffectedUser: null,
    AffectedUserId: null,
  };
  assert.equal(rowToTicket(row).affectedUser, null);
});

test('rowToTicket keeps ticketType when present', () => {
  const row = {
    Id: 'a',
    WorkItemId: 'IR1',
    Title: 't',
    Status: 'Active',
    Priority: '2',
    CreatedDate: '2026-07-01',
    AffectedUser: null,
    AffectedUserId: null,
    TicketType: 'incident',
  };
  assert.equal(rowToTicket(row).ticketType, 'incident');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/scsm-search && npm test`
Expected: FAIL with "Cannot find module '../src/db/queries/tickets.js'".

- [ ] **Step 3: Implement `src/db/queries/tickets.ts`**

```ts
import type { PreparedQuery } from '../exec.js';
import { USER_TABLE } from './users.js';

export type TicketKind = 'incident' | 'servicerequest';

export interface SearchTicketsParams {
  q?: string;
  type: TicketKind;
  status?: string;
  priority?: string;
  affectedUserId?: string;
  createdByUserId?: string;
  assignedUserId?: string;
  from?: Date;
  to?: Date;
  page: number;
  pageSize: number;
}

export function ticketTable(kind: TicketKind): string {
  return kind === 'incident'
    ? 'CiresonAnalytics.dbo.SM_WorkItem_Incident'
    : 'CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest';
}

const TICKET_COLUMNS = `Id, WorkItemId, Title, Status, Priority, Created AS CreatedDate, AffectedUser, AffectedUserId`;

const USERNAME_COL = 'u.UserName_6AF77E23_669B_123F_B392_323C17097BBD';
const UPN_COL = 'u.UPN_7641DFF7_7A20_DC04_FC1C_B6FA8715DA02';

function roleFilter(role: string, param: string): string {
  return `EXISTS (SELECT 1 FROM ${USER_TABLE} u
    WHERE u.BaseManagedEntityId = ${role}
      AND (${USERNAME_COL} = @${param} OR ${UPN_COL} = @${param}))`;
}

function sanitizeFtsTerm(q: string): string {
  return q.replace(/"/g, '');
}

export function buildTicketWhere(
  p: SearchTicketsParams,
  searchMode: 'fts' | 'like'
): { where: string[]; inputs: Record<string, string | number | Date> } {
  const where: string[] = [];
  const inputs: Record<string, string | number | Date> = {};
  if (p.status) {
    where.push('Status = @status');
    inputs.status = p.status;
  }
  if (p.priority) {
    where.push('Priority = @priority');
    inputs.priority = p.priority;
  }
  if (p.affectedUserId) {
    where.push(roleFilter('AffectedUserId', 'affectedUserId'));
    inputs.affectedUserId = p.affectedUserId;
  }
  if (p.createdByUserId) {
    where.push(roleFilter('CreatedByUserId', 'createdByUserId'));
    inputs.createdByUserId = p.createdByUserId;
  }
  if (p.assignedUserId) {
    where.push(roleFilter('AssignedUserId', 'assignedUserId'));
    inputs.assignedUserId = p.assignedUserId;
  }
  if (p.from) {
    where.push('Created >= @from');
    inputs.from = p.from;
  }
  if (p.to) {
    where.push('Created < DATEADD(DAY, 1, @to)');
    inputs.to = p.to;
  }
  if (p.q) {
    if (searchMode === 'fts') {
      where.push('CONTAINS((Title, Description, ResolutionDescription), @q)');
      inputs.q = sanitizeFtsTerm(p.q);
    } else {
      where.push(
        `(Title LIKE '%' + @q + '%' OR Description LIKE '%' + @q + '%' OR ResolutionDescription LIKE '%' + @q + '%')`
      );
      inputs.q = p.q;
    }
  }
  return { where, inputs };
}

export function buildSearchTicketsQuery(
  p: SearchTicketsParams,
  searchMode: 'fts' | 'like'
): PreparedQuery {
  const { where, inputs } = buildTicketWhere(p, searchMode);
  inputs.offset = (p.page - 1) * p.pageSize;
  inputs.pageSize = p.pageSize;
  const whereSql = where.length ? `WHERE ${where.join('\n  AND ')}` : '';
  return {
    sql: `SELECT ${TICKET_COLUMNS}
FROM ${ticketTable(p.type)}
${whereSql}
ORDER BY Created DESC
OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY;`,
    inputs,
  };
}

export function buildCountTicketsQuery(
  p: SearchTicketsParams,
  searchMode: 'fts' | 'like'
): PreparedQuery {
  const { where, inputs } = buildTicketWhere(p, searchMode);
  const whereSql = where.length ? `WHERE ${where.join('\n  AND ')}` : '';
  return { sql: `SELECT COUNT(*) AS Total
FROM ${ticketTable(p.type)}
${whereSql};`, inputs };
}

export interface UserTicketsParams {
  page: number;
  pageSize: number;
}

export function buildUserTicketsQuery(userId: string, p: UserTicketsParams): PreparedQuery {
  return {
    sql: `SELECT 'incident' AS TicketType, ${TICKET_COLUMNS}
FROM CiresonAnalytics.dbo.SM_WorkItem_Incident
WHERE AffectedUserId = @userId
UNION ALL
SELECT 'servicerequest', ${TICKET_COLUMNS}
FROM CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest
WHERE AffectedUserId = @userId
ORDER BY CreatedDate DESC
OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY;`,
    inputs: { userId, offset: (p.page - 1) * p.pageSize, pageSize: p.pageSize },
  };
}

export function buildCountUserTicketsQuery(userId: string): PreparedQuery {
  return {
    sql: `SELECT COUNT(*) AS Total FROM (
  SELECT Id FROM CiresonAnalytics.dbo.SM_WorkItem_Incident WHERE AffectedUserId = @userId
  UNION ALL
  SELECT Id FROM CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest WHERE AffectedUserId = @userId
) t;`,
    inputs: { userId },
  };
}
```

`src/serializers/ticket.ts`:
```ts
import type { TicketResult, TicketRow } from '../types/ticket.js';

export function rowToTicket(row: TicketRow): TicketResult {
  const createdDate =
    row.CreatedDate instanceof Date ? row.CreatedDate.toISOString() : String(row.CreatedDate);
  const result: TicketResult = {
    id: row.Id,
    workItemId: row.WorkItemId,
    title: row.Title,
    status: row.Status,
    priority: row.Priority,
    createdDate,
    affectedUser: row.AffectedUser
      ? { id: row.AffectedUserId ?? '', displayName: row.AffectedUser }
      : null,
  };
  if ('TicketType' in row && (row as { TicketType?: string }).TicketType) {
    result.ticketType = (row as { TicketType: TicketResult['ticketType'] }).TicketType;
  }
  return result;
}
```

- [ ] **Step 4: Run tests**

Run: `cd ~/projects/scsm-search && npm test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/scsm-search
git add src/db/queries/tickets.ts src/serializers/ticket.ts tests/queryBuilders-tickets.test.ts
git commit -m "feat: ticket query builders (search/count/user-union) and row serializer"
```

---

### Task 6: Search routes (`/v1/search/tickets`, `/v1/search/users`)

**Files:**
- Create: `src/routes/search.ts`
- Test: `tests/routes-search.test.ts`

**Interfaces:**
- Consumes: `exec` (Task 1), `buildSearchTicketsQuery`/`buildCountTicketsQuery` (Task 5), `buildSearchUsersQuery`/`buildCountUsersQuery` (Task 4), `ticketSearchParamsSchema`/`userSearchParamsSchema` (Task 2), `rowToTicket` (Task 5), `TicketRow`/`DomainUserRow` types (Task 2).
- Produces: `searchRouter(opts: { pool: ConnectionPool; searchMode: 'fts'|'like' }): Router` — routes `GET /tickets` and `GET /users` (mounted at `/v1/search` by Task 8).

- [ ] **Step 1: Write the failing route test**

`tests/routes-search.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import express from 'express';
import type { ConnectionPool } from 'mssql';
import { searchRouter } from '../src/routes/search.js';
import { errorHandler } from '../src/middleware/errorHandler.js';

function fakePool(recordSets: unknown[][]): ConnectionPool {
  let call = 0;
  return {
    request() {
      return {
        input(name: string, value: unknown) {
          this.inputs = this.inputs ?? {};
          this.inputs[name] = value;
        },
        async query(_sql: string) {
          return { recordset: recordSets[Math.min(call++, recordSets.length - 1)] ?? [] };
        },
      };
    },
  } as unknown as ConnectionPool;
}

function makeApp(pool: ConnectionPool) {
  const app = express();
  app.use('/v1/search', searchRouter({ pool, searchMode: 'fts' }));
  app.use(errorHandler);
  app.use((_req, res) => res.status(404).json({ error: { code: 'NOT_FOUND', message: 'Not found' } }));
  return app;
}

const ticketRow = {
  Id: 'a',
  WorkItemId: 'IR1',
  Title: 'Printer down',
  Status: 'Active',
  Priority: '2',
  CreatedDate: '2026-07-01T09:00:00Z',
  AffectedUser: 'John Smith',
  AffectedUserId: 'g',
};

test('GET /v1/search/tickets returns mapped results + pagination', async () => {
  const app = makeApp(fakePool([[ticketRow], [{ Total: 1 }]]));
  const res = await request(app).get('/v1/search/tickets').query({ type: 'incident', q: 'printer' });
  assert.equal(res.status, 200);
  assert.equal(res.body.results[0].workItemId, 'IR1');
  assert.equal(res.body.results[0].createdDate, '2026-07-01T09:00:00Z');
  assert.equal(res.body.total, 1);
  assert.equal(res.body.page, 1);
  assert.equal(res.body.pageSize, 25);
});

test('GET /v1/search/tickets without type -> 400 validation', async () => {
  const app = makeApp(fakePool([]));
  const res = await request(app).get('/v1/search/tickets').query({ q: 'x' });
  assert.equal(res.status, 400);
  assert.equal(res.body.error.code, 'VALIDATION');
});

test('GET /v1/search/users returns mapped users', async () => {
  const app = makeApp(
    fakePool([[{ Id: 'g', UserId: 'jsmith', DisplayName: 'John Smith', UPN: 'jsmith@nwu.ac.za' }], [{ Total: 1 }]])
  );
  const res = await request(app).get('/v1/search/users').query({ q: 'jsmith' });
  assert.equal(res.status, 200);
  assert.deepEqual(res.body.results[0], {
    id: 'g',
    userId: 'jsmith',
    displayName: 'John Smith',
    upn: 'jsmith@nwu.ac.za',
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/scsm-search && npm test`
Expected: FAIL with "Cannot find module '../src/routes/search.js'".

- [ ] **Step 3: Implement `src/routes/search.ts`**

```ts
import { Router } from 'express';
import type { ConnectionPool } from 'mssql';
import { exec } from '../db/exec.js';
import { buildSearchTicketsQuery, buildCountTicketsQuery } from '../db/queries/tickets.js';
import { buildSearchUsersQuery, buildCountUsersQuery } from '../db/queries/users.js';
import { ticketSearchParamsSchema, userSearchParamsSchema } from '../schemas/searchParams.js';
import { rowToTicket } from '../serializers/ticket.js';
import type { TicketRow } from '../types/ticket.js';
import type { DomainUserRow } from '../types/domainUser.js';

export function searchRouter(opts: { pool: ConnectionPool; searchMode: 'fts' | 'like' }): Router {
  const router = Router();

  router.get('/tickets', async (req, res) => {
    const p = ticketSearchParamsSchema.parse(req.query);
    const [rows, total] = await Promise.all([
      exec<TicketRow>(opts.pool, buildSearchTicketsQuery(p, opts.searchMode)),
      exec<{ Total: number }>(opts.pool, buildCountTicketsQuery(p, opts.searchMode)),
    ]);
    res.json({
      results: rows.map(rowToTicket),
      page: p.page,
      pageSize: p.pageSize,
      total: total[0]?.Total ?? 0,
    });
  });

  router.get('/users', async (req, res) => {
    const p = userSearchParamsSchema.parse(req.query);
    const [rows, total] = await Promise.all([
      exec<DomainUserRow>(opts.pool, buildSearchUsersQuery(p)),
      exec<{ Total: number }>(opts.pool, buildCountUsersQuery(p)),
    ]);
    res.json({
      results: rows.map((r) => ({ id: r.Id, userId: r.UserId, displayName: r.DisplayName, upn: r.UPN })),
      page: p.page,
      pageSize: p.pageSize,
      total: total[0]?.Total ?? 0,
    });
  });

  return router;
}
```

- [ ] **Step 4: Run tests**

Run: `cd ~/projects/scsm-search && npm test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/scsm-search
git add src/routes/search.ts tests/routes-search.test.ts
git commit -m "feat: /v1/search/tickets and /v1/search/users routes"
```

---

### Task 7: Users routes (`/v1/users/:id/tickets`)

**Files:**
- Create: `src/routes/users.ts`
- Test: `tests/routes-users.test.ts`

**Interfaces:**
- Consumes: `exec` (Task 1), `buildResolveUserQuery` (Task 4), `buildUserTicketsQuery`/`buildCountUserTicketsQuery` (Task 5), `userTicketsParamsSchema` (Task 2), `rowToTicket` (Task 5), `UserTicketRow` (Task 2).
- Produces: `usersRouter(opts: { pool: ConnectionPool }): Router` — route `GET /:id/tickets` (mounted at `/v1/users` by Task 8). `:id` accepts GUID, UserName, or UPN.

- [ ] **Step 1: Write the failing route test**

`tests/routes-users.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import express from 'express';
import type { ConnectionPool } from 'mssql';
import { usersRouter } from '../src/routes/users.js';
import { errorHandler } from '../src/middleware/errorHandler.js';

function fakePool(recordSets: unknown[][]): ConnectionPool {
  let call = 0;
  return {
    request() {
      return {
        input(name: string, value: unknown) {
          this.inputs = this.inputs ?? {};
          this.inputs[name] = value;
        },
        async query(_sql: string) {
          return { recordset: recordSets[Math.min(call++, recordSets.length - 1)] ?? [] };
        },
      };
    },
  } as unknown as ConnectionPool;
}

function makeApp(pool: ConnectionPool) {
  const app = express();
  app.use('/v1/users', usersRouter({ pool }));
  app.use(errorHandler);
  return app;
}

const ticketRow = {
  Id: 'a',
  WorkItemId: 'IR1',
  Title: 'Printer down',
  Status: 'Active',
  Priority: '2',
  CreatedDate: '2026-07-01T09:00:00Z',
  AffectedUser: 'John Smith',
  AffectedUserId: 'g',
  TicketType: 'incident',
};

test('resolves user id then returns merged tickets', async () => {
  const pool = fakePool([[{ Id: 'GUID' }], [ticketRow], [{ Total: 1 }]]);
  const res = await request(makeApp(pool)).get('/v1/users/jsmith/tickets');
  assert.equal(res.status, 200);
  assert.equal(res.body.results[0].ticketType, 'incident');
  assert.equal(res.body.total, 1);
  assert.equal(res.body.page, 1);
});

test('unknown user -> 404', async () => {
  const res = await request(makeApp(fakePool([[]]))).get('/v1/users/nobody/tickets');
  assert.equal(res.status, 404);
  assert.equal(res.body.error.code, 'NOT_FOUND');
});

test('ambiguous user -> 400', async () => {
  const res = await request(makeApp(fakePool([[{ Id: 'a' }, { Id: 'b' }]]))).get('/v1/users/x/tickets');
  assert.equal(res.status, 400);
  assert.equal(res.body.error.code, 'AMBIGUOUS');
});

test('validates pagination params', async () => {
  const res = await request(makeApp(fakePool([[]]))).get('/v1/users/jsmith/tickets').query({ page: '0' });
  assert.equal(res.status, 400);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/scsm-search && npm test`
Expected: FAIL with "Cannot find module '../src/routes/users.js'".

- [ ] **Step 3: Implement `src/routes/users.ts`**

```ts
import { Router } from 'express';
import type { ConnectionPool } from 'mssql';
import { exec } from '../db/exec.js';
import { buildResolveUserQuery } from '../db/queries/users.js';
import { buildUserTicketsQuery, buildCountUserTicketsQuery } from '../db/queries/tickets.js';
import { userTicketsParamsSchema } from '../schemas/searchParams.js';
import { rowToTicket } from '../serializers/ticket.js';
import type { UserTicketRow } from '../types/ticket.js';

export function usersRouter(opts: { pool: ConnectionPool }): Router {
  const router = Router();

  router.get('/:id/tickets', async (req, res) => {
    const p = userTicketsParamsSchema.parse(req.query);
    const resolved = await exec<{ Id: string }>(opts.pool, buildResolveUserQuery(String(req.params.id)));
    if (resolved.length === 0) {
      res.status(404).json({ error: { code: 'NOT_FOUND', message: 'User not found' } });
      return;
    }
    if (resolved.length > 1) {
      res.status(400).json({ error: { code: 'AMBIGUOUS', message: 'User id matches multiple users' } });
      return;
    }
    const userId = resolved[0].Id;
    const [rows, total] = await Promise.all([
      exec<UserTicketRow>(opts.pool, buildUserTicketsQuery(userId, p)),
      exec<{ Total: number }>(opts.pool, buildCountUserTicketsQuery(userId)),
    ]);
    res.json({
      results: rows.map(rowToTicket),
      page: p.page,
      pageSize: p.pageSize,
      total: total[0]?.Total ?? 0,
    });
  });

  return router;
}
```

- [ ] **Step 4: Run tests**

Run: `cd ~/projects/scsm-search && npm test`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/scsm-search
git add src/routes/users.ts tests/routes-users.test.ts
git commit -m "feat: /v1/users/:id/tickets route with GUID/UserName/UPN resolution"
```

---

### Task 8: App factory + server entry

**Files:**
- Create: `src/app.ts`
- Create: `src/server.ts`
- Test: `tests/app.test.ts`

**Interfaces:**
- Consumes: `createAuthMiddleware` (Task 3), `errorHandler` (Task 1), `healthRouter` (Task 1), `searchRouter` (Task 6), `usersRouter` (Task 7), `loadConfig`/`makePool` (Task 1).
- Produces:
  - `createApp({ pool, searchMode, apiKeys }: AppDeps): express.Express` from `src/app.ts`
  - `src/server.ts` — the Docker entry (`node dist/server.js`): loads config, builds pool, connects, `createApp`, listens.

- [ ] **Step 1: Write the failing app test**

`tests/app.test.ts`:
```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import type { ConnectionPool } from 'mssql';
import { createApp } from '../src/app.js';

function fakePool(): ConnectionPool {
  return {
    request() {
      return {
        input() {},
        async query() {
          return { recordset: [] };
        },
      };
    },
  } as unknown as ConnectionPool;
}

function makeApp() {
  return createApp({ pool: fakePool(), searchMode: 'fts', apiKeys: ['n8n-secret'] });
}

test('healthz is unauthenticated', async () => {
  const res = await request(makeApp()).get('/healthz');
  assert.equal(res.status, 200);
});

test('v1 routes require an api key', async () => {
  const res = await request(makeApp()).get('/v1/search/users');
  assert.equal(res.status, 401);
});

test('v1 routes accept a valid api key', async () => {
  const res = await request(makeApp()).get('/v1/search/users').set('x-api-key', 'n8n-secret');
  assert.equal(res.status, 200);
});

test('unknown route -> 404 JSON', async () => {
  const res = await request(makeApp()).get('/nope');
  assert.equal(res.status, 404);
  assert.equal(res.body.error.code, 'NOT_FOUND');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/scsm-search && npm test`
Expected: FAIL with "Cannot find module '../src/app.js'".

- [ ] **Step 3: Implement `src/app.ts` and `src/server.ts`**

`src/app.ts`:
```ts
import express from 'express';
import pinoHttp from 'pino-http';
import type { ConnectionPool } from 'mssql';
import { createAuthMiddleware } from './middleware/auth.js';
import { errorHandler } from './middleware/errorHandler.js';
import { healthRouter } from './routes/health.js';
import { searchRouter } from './routes/search.js';
import { usersRouter } from './routes/users.js';

export interface AppDeps {
  pool: ConnectionPool;
  searchMode: 'fts' | 'like';
  apiKeys: string[];
}

export function createApp({ pool, searchMode, apiKeys }: AppDeps): express.Express {
  const app = express();
  app.disable('x-powered-by');
  app.use(pinoHttp({ level: process.env.LOG_LEVEL ?? 'info' }));

  app.use('/healthz', healthRouter({ pool }));
  app.use('/v1', createAuthMiddleware(apiKeys));
  app.use('/v1/search', searchRouter({ pool, searchMode }));
  app.use('/v1/users', usersRouter({ pool }));

  app.use((_req, res) => {
    res.status(404).json({ error: { code: 'NOT_FOUND', message: 'Not found' } });
  });
  app.use(errorHandler);
  return app;
}
```

`src/server.ts`:
```ts
import { pino } from 'pino';
import { loadConfig } from './config.js';
import { makePool } from './db/pool.js';
import { createApp } from './app.js';

async function main(): Promise<void> {
  const config = loadConfig();
  if (!config.dbServer || config.apiKeys.length === 0) {
    throw new Error('DB_SERVER and API_KEYS must be set (see .env.example)');
  }
  const logger = pino();
  const pool = makePool(config);
  await pool.connect();
  const app = createApp({ pool, searchMode: config.searchMode, apiKeys: config.apiKeys });
  app.listen(config.port, () => {
    logger.info({ port: config.port, searchMode: config.searchMode }, 'scsm-search listening');
  });
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});
```

- [ ] **Step 4: Run tests and build**

Run: `cd ~/projects/scsm-search && npm test && npm run build`
Expected: all PASS; `dist/` builds without type errors.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/scsm-search
git add src/app.ts src/server.ts tests/app.test.ts
git commit -m "feat: app factory wiring auth, routers, health, error handler; server entry"
```

---

### Task 9: Docker, compose snippet, smoke script

**Files:**
- Create: `Dockerfile`
- Create: `compose.scsm-search.yml`
- Create: `scripts/smoke.sh`

**Interfaces:**
- Consumes: `dist/server.js` (Task 8 build), `src/server.ts` dev entry.
- Produces: container image `scsm-search`, a compose snippet to run on the n8n host, and a manual smoke script.

- [ ] **Step 1: Write the Dockerfile**

`Dockerfile`:
```dockerfile
FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
RUN addgroup -S app && adduser -S app -G app
USER app
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

- [ ] **Step 2: Write the compose snippet**

`compose.scsm-search.yml`:
```yaml
services:
  scsm-search:
    build: .
    image: scsm-search:latest
    container_name: scsm-search
    restart: unless-stopped
    env_file: .env
    networks:
      - n8n_default # TODO(ops): replace with the actual n8n host network name
    healthcheck:
      test:
        - CMD
        - node
        - -e
        - "fetch('http://localhost:3000/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

networks:
  n8n_default:
    external: true
```

- [ ] **Step 3: Write the smoke script**

`scripts/smoke.sh` (make executable with `chmod +x scripts/smoke.sh`):
```bash
#!/usr/bin/env bash
set -euo pipefail
# Manual smoke test against a running scsm-search instance.
# Requires .env with DB_SERVER/DB_USER/DB_PASSWORD/API_KEYS/PORT.
set -a
source .env
set +a
KEY="$(cut -d',' -f1 <<<"$API_KEYS")"
BASE="${SMOKE_BASE:-http://localhost:${PORT:-3000}}"

echo "== healthz =="
curl -fsS "$BASE/healthz"
echo
echo "== user search q=smith =="
curl -fsS -H "x-api-key: $KEY" "$BASE/v1/search/users?q=smith" | head -c 600
echo
echo "== ticket search type=incident q=printer =="
curl -fsS -H "x-api-key: $KEY" "$BASE/v1/search/tickets?type=incident&q=printer&pageSize=2" | head -c 600
echo
echo "== user tickets by UPN =="
UPN="${SMOKE_UPN:-jsmith@nwu.ac.za}"
curl -fsS -H "x-api-key: $KEY" "$BASE/v1/users/$UPN/tickets?pageSize=2" | head -c 600
echo
echo "OK"
```

- [ ] **Step 4: Verify the image builds**

Run: `cd ~/projects/scsm-search && docker build -t scsm-search:test .`
Expected: build succeeds; runtime stage has no `devDependencies` (only prod deps + `dist/`).

- [ ] **Step 5: Commit**

```bash
cd ~/projects/scsm-search
git add Dockerfile compose.scsm-search.yml scripts/smoke.sh
git commit -m "deploy: multi-stage Dockerfile, compose snippet, smoke script"
```

---

### Task 10: Housekeeping — local `.env`, docs pointer, changelog

**Files:**
- Create: `.env` (local only, gitignored)
- Modify: `../../pcm-compass/CHANGELOG.md` (the tracking repo)
- Modify: `../../pcm-compass/docs/superpowers/specs/2026-08-06-scsm-search-service-design.md` (optional: add a note that implementation is complete)

**Interfaces:**
- Consumes: `.env.example` (Task 1).
- Produces: a runnable local dev setup and a tracking entry in the pcm-compass changelog.

- [ ] **Step 1: Create local `.env` from the example**

```bash
cd ~/projects/scsm-search && cp .env.example .env
```
Fill `DB_SERVER`, `DB_USER`, `DB_PASSWORD`, and a comma-separated `API_KEYS` from ops. Verify the app boots against the real DB:

```bash
cd ~/projects/scsm-search && npm run dev
```
Expected: `"scsm-search listening"` logged; `curl -fsS localhost:3000/healthz` returns `{"status":"ok"}`. Then run `scripts/smoke.sh` and confirm each section returns data.

- [ ] **Step 2: Update the pcm-compass changelog**

In `~/projects/pcm-compass/CHANGELOG.md`, under `[Unreleased] > Added`, add a line:

```
- 2026-08-06: SCSM search service implemented (`~/projects/scsm-search`) — read-only Node/TS API over CiresonAnalytics (`SM_WorkItem_Incident`/`SM_WorkItem_ServiceRequest`) + ServiceManager user view; `/v1/search/tickets|users`, `/v1/users/:id/tickets`; per-consumer API keys; SEARCH_MODE fts/like
```

- [ ] **Step 3: Commit the housekeeping changes**

```bash
cd ~/projects/pcm-compass
git add CHANGELOG.md
git commit -m "docs: changelog entry for scsm-search service implementation"
```

---

## Self-Review Notes

- **Spec coverage:** ticket search + count (Tasks 5-6), user search + count (Tasks 4, 6), `/users/:id/tickets` resolve+merge (Task 7), health (Task 1), auth (Task 3), validation (Task 2), error shape (Task 1), Docker/compose/env/smoke (Task 9), the two-database fully-qualified queries and `SEARCH_MODE` fallback (Tasks 4-5), and the on-demand `affectedUser.userId` contract (Task 6 returns id+displayName only).
- **FTS provisioning:** not blocked — the service runs in `like` mode until the DW admin provisions the FTS catalog; the `SEARCH_MODE` env toggle is the switch.
- **Cross-database account:** the `DB_USER` needs `SELECT` on both `CiresonAnalytics.dbo.SM_WorkItem_*` and `ServiceManager.dbo.MTV_System$Domain$User` (noted in Task 9 ops checklist / smoke).
