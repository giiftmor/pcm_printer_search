# scsm-search Backend Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the three small capabilities the PCM Compass page needs to the existing scsm-search API: ticket-number (`WorkItemId`) matching on `q`, `createdByUser`/`assignedUser` on ticket responses, and a `role` parameter on `/v1/users/:id/tickets`.

**Architecture:** Pure additive changes to the existing scsm-search Express + SQL-Server service. Query builders in `src/db/queries/tickets.ts` gain the WorkItemId match and role-column parameterization; the projection gains creator/assignee columns; the ticket type + serializer surface them; `src/routes/users.ts` accepts and forwards `role`. No schema changes, no new dependencies, no breaking API changes.

**Tech Stack:** TypeScript 5, Express 5, mssql, zod 3. Tests: `node --import tsx --test` + supertest, `fakePool`/`capturingPool` mock patterns.

## Global Constraints

- **Repo:** `~/projects/scsm-search` — run every command from this directory.
- **Backward compatible:** existing responses keep `affectedUser`; the new `createdByUser`/`assignedUser` fields are additive and default to `null`.
- **Role enum exactly:** `affected | created_by | assigned`, default `affected`.
- **WorkItemId matching must work in BOTH `fts` and `like` modes** — the FTS catalog may not cover `WorkItemId` (FTS provisioning is pending), so never rely on `CONTAINS(WorkItemId, …)`.
- **All user input stays parameterized** — never string-concatenate a user value into SQL.
- **Test command:** `npm test` (runs `node --import tsx --test tests/*.test.ts`). **Typecheck:** `npx tsc --noEmit`. **Build:** `npm run build`.
- **No deploy in this plan** — deployment/restart of the live service happens once these tasks pass (before the Compass page work starts).
- Copy the spec's exact URL path `/v1/users/:id/tickets` and JSON shapes from `docs/superpowers/specs/2026-08-10-scsm-search-compass-integration-design.md` §5.

---

### Task 1: `q` matches `WorkItemId`

**Files:**
- Modify: `src/db/queries/tickets.ts:81-94` (`buildTicketWhere`'s `if (p.q)` block)
- Test: `tests/queryBuilders-tickets.test.ts`

**Interfaces:**
- Consumes: nothing from other tasks; existing `buildTicketWhere(p, searchMode)` signature.
- Produces: same `{ where, inputs }` shape; adds one extra input key `qId` (raw query) alongside the existing `q`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/queryBuilders-tickets.test.ts` (after the existing `like mode uses LIKE` test):

```ts
test('search tickets: q also matches WorkItemId in fts mode', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'IR1660031' }, 'fts');
  assert.ok(q.sql.includes("WorkItemId LIKE '%' + @qId + '%'"));
  assert.equal(q.inputs.qId, 'IR1660031');
});

test('search tickets: q also matches WorkItemId in like mode', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'IR1660031' }, 'like');
  assert.ok(q.sql.includes("WorkItemId LIKE '%' + @qId + '%'"));
  assert.equal(q.inputs.qId, 'IR1660031');
});

test('search tickets: WorkItemId and text matches share one OR group', () => {
  const q = buildSearchTicketsQuery({ ...base, q: 'printer IR1' }, 'fts');
  assert.match(
    q.sql,
    /\(\s*WorkItemId LIKE '%' \+ @qId \+ '%' OR CONTAINS\(\(Title, Description, ResolutionDescription\), @q\)\s*\)/
  );
});

test('search tickets: a q that sanitizes to empty still matches WorkItemId', () => {
  const q = buildSearchTicketsQuery({ ...base, q: '"' }, 'fts');
  assert.ok(q.sql.includes("WorkItemId LIKE '%' + @qId + '%'"));
  assert.equal(q.inputs.qId, '"');
  assert.ok(!('q' in q.inputs));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: the four new tests FAIL (no `WorkItemId LIKE` in output SQL yet).

- [ ] **Step 3: Implement the WorkItemId match**

Replace the `if (p.q) { ... }` block in `buildTicketWhere` (`src/db/queries/tickets.ts:81-94`) with:

```ts
  if (p.q) {
    const workItemIdCond = `WorkItemId LIKE '%' + @qId + '%'`;
    if (searchMode === 'fts') {
      const term = sanitizeFtsTerm(p.q);
      if (term) {
        where.push(
          `(WorkItemId LIKE '%' + @qId + '%' OR CONTAINS((Title, Description, ResolutionDescription), @q))`
        );
        inputs.q = term;
        inputs.qId = p.q;
      } else {
        where.push(workItemIdCond);
        inputs.qId = p.q;
      }
    } else {
      where.push(
        `(WorkItemId LIKE '%' + @qId + '%' OR Title LIKE '%' + @q + '%' OR Description LIKE '%' + @q + '%' OR ResolutionDescription LIKE '%' + @q + '%')`
      );
      inputs.q = p.q;
      inputs.qId = p.q;
    }
  }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: all tests pass, including the pre-existing `fts mode uses CONTAINS with a neutralized term`, `fts mode drops a term that sanitizes to empty`, `like mode uses LIKE`, and `value is parameterized, never inlined` tests.

- [ ] **Step 5: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/db/queries/tickets.ts tests/queryBuilders-tickets.test.ts
git commit -m "feat: match ticket search q against WorkItemId"
```

---

### Task 2: Ticket responses gain `createdByUser` and `assignedUser`

**Files:**
- Modify: `src/db/queries/tickets.ts:26-30` (`ticketColumns`)
- Modify: `src/types/ticket.ts`
- Modify: `src/serializers/ticket.ts`
- Test: `tests/queryBuilders-tickets.test.ts`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `TicketRow` gains `CreatedByUser`, `CreatedByUserId`, `AssignedUser`, `AssignedUserId: string | null`.
  - `UserResult` interface (`{ id: string; displayName: string }`) replaces `AffectedUserResult`.
  - `TicketResult` gains `createdByUser: UserResult | null` and `assignedUser: UserResult | null`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/queryBuilders-tickets.test.ts`:

```ts
test('search tickets: projects creator and assignee columns for both kinds', () => {
  const q = buildSearchTicketsQuery(base, 'fts');
  assert.ok(q.sql.includes('CreatedByUser, CreatedByUserId, AssignedUser, AssignedUserId'));
  const sr = buildSearchTicketsQuery({ ...base, type: 'servicerequest' }, 'fts');
  assert.ok(sr.sql.includes('CreatedByUser, CreatedByUserId, AssignedUser, AssignedUserId'));
});

test('rowToTicket maps createdByUser and assignedUser', () => {
  const row = {
    Id: 'a',
    WorkItemId: 'IR1',
    Title: 't',
    Status: 'Active',
    Priority: '2',
    CreatedDate: new Date('2026-07-01T09:00:00Z'),
    AffectedUser: 'John Smith',
    AffectedUserId: 'g',
    CreatedByUser: 'Jane Doe',
    CreatedByUserId: 'h',
    AssignedUser: 'Bob Roe',
    AssignedUserId: 'i',
  };
  const t = rowToTicket(row);
  assert.deepEqual(t.createdByUser, { id: 'h', displayName: 'Jane Doe' });
  assert.deepEqual(t.assignedUser, { id: 'i', displayName: 'Bob Roe' });
});

test('rowToTicket maps null createdBy and assigned users', () => {
  const row = {
    Id: 'a',
    WorkItemId: 'IR1',
    Title: 't',
    Status: 'Active',
    Priority: '2',
    CreatedDate: '2026-07-01',
    AffectedUser: null,
    AffectedUserId: null,
    CreatedByUser: null,
    CreatedByUserId: null,
    AssignedUser: null,
    AssignedUserId: null,
  };
  const t = rowToTicket(row);
  assert.equal(t.createdByUser, null);
  assert.equal(t.assignedUser, null);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: the projection test fails (columns absent) and the `rowToTicket` tests fail (fields undefined).

- [ ] **Step 3: Implement projection + types + serializer**

In `src/db/queries/tickets.ts`, replace `ticketColumns` with:

```ts
function ticketColumns(kind: TicketKind): string {
  const base =
    kind === 'servicerequest'
      ? `Id, WorkItemId, Title, Status, Priority, Created AS CreatedDate`
      : `Id, WorkItemId, Title, Status, NULL AS Priority, Created AS CreatedDate`;
  return `${base}, AffectedUser, AffectedUserId, CreatedByUser, CreatedByUserId, AssignedUser, AssignedUserId`;
}
```

In `src/types/ticket.ts`, replace the whole file body after the `TicketType` export with:

```ts
export interface UserResult {
  id: string;
  displayName: string;
}

export interface TicketRow {
  Id: string;
  WorkItemId: string;
  Title: string;
  Status: string;
  Priority: string | null;
  CreatedDate: Date | string;
  AffectedUser: string | null;
  AffectedUserId: string | null;
  CreatedByUser: string | null;
  CreatedByUserId: string | null;
  AssignedUser: string | null;
  AssignedUserId: string | null;
}

export interface UserTicketRow extends TicketRow {
  TicketType: TicketType;
}

export interface TicketResult {
  id: string;
  workItemId: string;
  title: string;
  status: string;
  priority: string | null;
  createdDate: string;
  affectedUser: UserResult | null;
  createdByUser: UserResult | null;
  assignedUser: UserResult | null;
  ticketType?: TicketType;
}
```

In `src/serializers/ticket.ts`, replace the whole file with:

```ts
import type { TicketResult, TicketRow, UserResult } from '../types/ticket.js';

function toUserResult(
  name: string | null | undefined,
  id: string | null | undefined
): UserResult | null {
  return name ? { id: id ?? '', displayName: name } : null;
}

export function rowToTicket(row: TicketRow): TicketResult {
  const createdDate =
    row.CreatedDate instanceof Date ? row.CreatedDate.toISOString() : String(row.CreatedDate);
  const result: TicketResult = {
    id: row.Id,
    workItemId: row.WorkItemId,
    title: row.Title,
    status: row.Status,
    priority: row.Priority ?? null,
    createdDate,
    affectedUser: toUserResult(row.AffectedUser, row.AffectedUserId),
    createdByUser: toUserResult(row.CreatedByUser, row.CreatedByUserId),
    assignedUser: toUserResult(row.AssignedUser, row.AssignedUserId),
  };
  if ('TicketType' in row && (row as { TicketType?: string }).TicketType) {
    result.ticketType = (row as { TicketType: TicketResult['ticketType'] }).TicketType;
  }
  return result;
}
```

> Note: `AffectedUserResult` was removed — `grep -rn "AffectedUserResult" src/ tests/` confirms it was only referenced inside `src/types/ticket.ts`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: all pass, including the pre-existing `rowToTicket` tests (rows without the new columns map new fields to `null`).

- [ ] **Step 5: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/db/queries/tickets.ts src/types/ticket.ts src/serializers/ticket.ts tests/queryBuilders-tickets.test.ts
git commit -m "feat: expose createdByUser and assignedUser on ticket responses"
```

---

### Task 3: `role` parameter on `/v1/users/:id/tickets`

**Files:**
- Modify: `src/schemas/searchParams.ts:26-30`
- Modify: `src/db/queries/tickets.ts:127-156` (`Pagination`, `buildUserTicketsQuery`, `buildCountUserTicketsQuery`)
- Modify: `src/routes/users.ts:24-28`
- Test: `tests/queryBuilders-tickets.test.ts`, `tests/routes-users.test.ts`

**Interfaces:**
- Consumes: `UserResult`/`TicketRow` from Task 2 (unchanged); `TicketType` already exported.
- Produces:
  - `export type UserTicketsRole = 'affected' | 'created_by' | 'assigned'`
  - `export function roleColumn(role: UserTicketsRole): string`
  - `export interface UserTicketsQueryParams extends Pagination { role?: UserTicketsRole }`
  - `buildUserTicketsQuery(userId: string, p: UserTicketsQueryParams): PreparedQuery`
  - `buildCountUserTicketsQuery(userId: string, role?: UserTicketsRole): PreparedQuery`
  - `userTicketsParamsSchema` gains `role: z.enum(['affected', 'created_by', 'assigned']).default('affected')`

- [ ] **Step 1: Write the failing tests**

Append to `tests/queryBuilders-tickets.test.ts`:

```ts
test('user tickets: role selects the role column', () => {
  const q = buildUserTicketsQuery('GUID', { page: 1, pageSize: 25, role: 'created_by' });
  assert.ok(q.sql.includes('WHERE CreatedByUserId = @userId'));
  const a = buildUserTicketsQuery('GUID', { page: 1, pageSize: 25, role: 'assigned' });
  assert.ok(a.sql.includes('WHERE AssignedUserId = @userId'));
});

test('user tickets: role defaults to affected', () => {
  const q = buildUserTicketsQuery('GUID', { page: 1, pageSize: 25 });
  assert.ok(q.sql.includes('WHERE AffectedUserId = @userId'));
});

test('count user tickets: role selects the role column', () => {
  const q = buildCountUserTicketsQuery('GUID', 'assigned');
  assert.ok(q.sql.includes('WHERE AssignedUserId = @userId'));
  const d = buildCountUserTicketsQuery('GUID');
  assert.ok(d.sql.includes('WHERE AffectedUserId = @userId'));
});

test('roleColumn maps each role to its column', () => {
  assert.equal(roleColumn('affected'), 'AffectedUserId');
  assert.equal(roleColumn('created_by'), 'CreatedByUserId');
  assert.equal(roleColumn('assigned'), 'AssignedUserId');
});
```

Update the imports at the top of `tests/queryBuilders-tickets.test.ts` to include `roleColumn`.

Append to `tests/routes-users.test.ts`:

```ts
test('role is forwarded to the count query', async () => {
  const { pool, calls } = capturingPool([[{ Id: 'GUID' }], [ticketRow], [{ Total: 1 }]]);
  const res = await request(makeApp(pool)).get('/v1/users/jsmith/tickets').query({ role: 'assigned' });
  assert.equal(res.status, 200);
  assert.deepEqual(calls[2], { userId: 'GUID' });
});

test('invalid role -> 400', async () => {
  const res = await request(makeApp(fakePool([[]]))).get('/v1/users/jsmith/tickets').query({ role: 'bogus' });
  assert.equal(res.status, 400);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — `roleColumn` not defined, and the SQL does not yet contain the role columns.

- [ ] **Step 3: Implement schema + query builders + route**

In `src/schemas/searchParams.ts`, replace `userTicketsParamsSchema` with:

```ts
export const userTicketsParamsSchema = z.object({
  role: z.enum(['affected', 'created_by', 'assigned']).default('affected'),
  ...paginationSchema,
});
```

(`UserTicketsParams` type auto-infers; no change needed to the `export type` lines.)

In `src/db/queries/tickets.ts`, replace the block from `export interface Pagination {` through the end of the file with:

```ts
export interface Pagination {
  page: number;
  pageSize: number;
}

export type UserTicketsRole = 'affected' | 'created_by' | 'assigned';

export function roleColumn(role: UserTicketsRole): string {
  switch (role) {
    case 'created_by':
      return 'CreatedByUserId';
    case 'assigned':
      return 'AssignedUserId';
    default:
      return 'AffectedUserId';
  }
}

export interface UserTicketsQueryParams extends Pagination {
  role?: UserTicketsRole;
}

export function buildUserTicketsQuery(userId: string, p: UserTicketsQueryParams): PreparedQuery {
  const col = roleColumn(p.role ?? 'affected');
  return {
    sql: `SELECT 'incident' AS TicketType, ${ticketColumns('incident')}
FROM CiresonAnalytics.dbo.SM_WorkItem_Incident
WHERE ${col} = @userId
UNION ALL
SELECT 'servicerequest', ${ticketColumns('servicerequest')}
FROM CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest
WHERE ${col} = @userId
ORDER BY CreatedDate DESC
OFFSET @offset ROWS FETCH NEXT @pageSize ROWS ONLY;`,
    inputs: { userId, offset: (p.page - 1) * p.pageSize, pageSize: p.pageSize },
  };
}

export function buildCountUserTicketsQuery(
  userId: string,
  role: UserTicketsRole = 'affected'
): PreparedQuery {
  const col = roleColumn(role);
  return {
    sql: `SELECT COUNT(*) AS Total FROM (
  SELECT Id FROM CiresonAnalytics.dbo.SM_WorkItem_Incident WHERE ${col} = @userId
  UNION ALL
  SELECT Id FROM CiresonAnalytics.dbo.SM_WorkItem_ServiceRequest WHERE ${col} = @userId
) t;`,
    inputs: { userId },
  };
}
```

In `src/routes/users.ts`, replace lines 24-28 with:

```ts
    const [rows, total] = await Promise.all([
      exec<UserTicketRow>(opts.pool, buildUserTicketsQuery(userId, p)),
      exec<{ Total: number }>(opts.pool, buildCountUserTicketsQuery(userId, p.role)),
    ]);
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: all pass, including the pre-existing `user tickets: union all with discriminator and pagination` and `binds the id and resolved user id as inputs` tests (default role keeps the same SQL/inputs).

- [ ] **Step 5: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/schemas/searchParams.ts src/db/queries/tickets.ts src/routes/users.ts tests/queryBuilders-tickets.test.ts tests/routes-users.test.ts
git commit -m "feat: add role filter to /v1/users/:id/tickets"
```

---

### Task 4: Full regression + build gate

**Files:**
- None (verification only).

**Interfaces:**
- Consumes: Tasks 1-3.

- [ ] **Step 1: Run the full test suite**

Run: `npm test`
Expected: ALL tests pass (existing + new).

- [ ] **Step 2: Typecheck**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Production build**

Run: `npm run build`
Expected: `dist/` regenerates with no errors.

- [ ] **Step 4: Confirm the API contract against the spec**

Review `src/routes/search.ts` and `src/routes/users.ts` — confirm the live endpoints now return `createdByUser`/`assignedUser` and accept `role`. Confirm response for `GET /v1/users/:id/tickets?role=affected` is unchanged for existing clients. No commit needed (already committed per task).

- [ ] **Step 5: Report deployment readiness**

State clearly in the handoff: the scsm-search additions are complete and tested; **deploy/restart of the live service is required before the Compass page plan** (manual: `docker compose` build + up on the ai-stack, then a smoke check of `/v1/search/tickets` and `/v1/users/:id/tickets?role=`).

---

## Self-Review

- **Spec coverage (§5):** 5.1 `q` matches `WorkItemId` → Task 1. 5.2 `createdByUser`/`assignedUser` → Task 2. 5.3 `role` param → Task 3. 5.4 tests → Tasks 1-3 plus Task 4 gate. ✓
- **Placeholder scan:** no TBD/TODO; every step has concrete code and run commands. ✓
- **Type consistency:** `roleColumn`, `UserTicketsRole`, `UserTicketsQueryParams`, `buildCountUserTicketsQuery(userId, role)` names are used identically in query builders, routes, and tests. `UserResult` is the only user-object type; `createdByUser`/`assignedUser` field names match the spec's JSON contract. ✓
