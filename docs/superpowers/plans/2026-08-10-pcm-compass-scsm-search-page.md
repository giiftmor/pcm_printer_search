# PCM Compass SCSM Search Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an SCSM Search page to PCM Compass — a split-pane agent workspace with a spotlight search bar, Google-style results, relationship tabs ("Other tickets"), and a detail pane with an `Open in SCSM ↗` link — proxying the live scsm-search API and applying the pinned design from `docs/superpowers/specs/2026-08-10-scsm-search-compass-integration-design.md`.

**Architecture:** A self-contained `modules/scsm_search/` Flask module (engine + routes + blueprint) following the `user_lookup`/`printer_search` module pattern. The engine builds SCSM portal URLs, proxies to scsm-search over `requests` with the server-side API key, and maintains a 30-min TTL in-process cache (daemon thread, in-flight guard) for per-role "other tickets". Routes expose `/api/scsm/*` JSON endpoints; the page (`templates/scsm_search.html`, vanilla JS) consumes them. **Assumes the scsm-search backend additions plan has been implemented and deployed** (WorkItemId match, createdByUser/assignedUser, role param).

**Tech Stack:** Flask 2, Python 3.11, requests, threading; Jinja2 + vanilla JS; pytest (via Docker `pcm-test` image).

## Global Constraints

- **Repo:** `~/projects/pcm-compass` — run every command from this directory.
- **No new libraries** (no cmdk; `requests` is already used by `printer_search`). Vanilla JS + Jinja + scoped CSS in the template.
- **API key stays server-side only** (`SCSM_API_KEY` in `.env`), never sent to the browser. Do **not** add secrets to the extension or commit any `.env`.
- **No direct SQL from Flask.** All SCSM data goes through the scsm-search API proxy.
- **Do NOT curl `support.nwu.ac.za`** — it is behind NWU SSO. The portal base is only used to *build* display URLs.
- **JSON endpoints are `/api/scsm/...`.** NWU green `#006633` / `#4a8c6f` accents; light theme (site theme, not the dark mockup).
- **Env keys:** `SCSM_API_URL` (default `http://scsm-search:3000`), `SCSM_API_KEY` (required; unset → routes return 503 `SCSM_NOT_CONFIGURED`), `SCSM_PORTAL_BASE` (default `https://support.nwu.ac.za`).
- **Error mapping (spec §6.2):** upstream 401 → 502; network/timeout → 503; other statuses passthrough.
- **Test command (pytest via Docker):**
  `docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q"`
- **Related-tickets cache:** TTL 30 min, per-(user_id, role) key, in-flight guard so duplicate fetches never start, daemon threads, full-page loop (`pageSize=100`) until `total` reached.
- **Depends on** scsm-search being live with: `q` matching `WorkItemId`, `createdByUser`/`assignedUser` on ticket results, `role` on `/v1/users/:id/tickets`.

---

### Task 1: Config keys + engine URL builders + tests

**Files:**
- Modify: `config.py`
- Create: `modules/scsm_search/__init__.py`
- Create: `modules/scsm_search/engine.py`
- Test: `tests/test_scsm_search_engine.py`

**Interfaces:**
- Consumes: nothing (foundation).
- Produces:
  - `Config.SCSM_API_URL`, `Config.SCSM_API_KEY`, `Config.SCSM_PORTAL_BASE`.
  - `modules.scsm_search.engine` module constants `SCSM_API_URL`, `SCSM_API_KEY`, `SCSM_PORTAL_BASE` (read at import from `Config`), `REQUEST_TIMEOUT = 5`.
  - `_KIND_SEGMENT = {'incident': 'Incident', 'servicerequest': 'ServiceRequest'}`
  - `ROLE_LABELS = {'affected': 'Affected user', 'created_by': 'Created by', 'assigned': 'Assigned'}`
  - `def build_scsm_url(work_item_id, ticket_type) -> str | None`
  - `def enrich_rows(rows, ticket_type=None) -> list[dict]`
  - `class ScsmError(Exception)` with `status_code`/`code` attrs; `class ScsmNotConfigured(ScsmError)` (503/`SCSM_NOT_CONFIGURED`); `class ScsmUpstreamError(ScsmError)`.
  - Blueprint `bp` (name `scsm_search`, url_prefix `/api/scsm`) in `modules/scsm_search/__init__.py` — route registration lands in Task 4.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scsm_search_engine.py`:

```python
import pytest

from modules.scsm_search import engine

A = {"id": "A", "displayName": "Alice"}
B = {"id": "B", "displayName": "Bob"}
C = {"id": "C", "displayName": "Carol"}


@pytest.mark.parametrize("work_item_id,ticket_type,expected", [
    ("IR1660031", "incident", "https://support.nwu.ac.za/Incident/Edit/IR1660031/"),
    ("SR123", "servicerequest", "https://support.nwu.ac.za/ServiceRequest/Edit/SR123/"),
    ("  IR7  ", "incident", "https://support.nwu.ac.za/Incident/Edit/IR7/"),
    ("IR1660031", "INCIDENT", "https://support.nwu.ac.za/Incident/Edit/IR1660031/"),
    ("IR1660031", "ServiceRequest", "https://support.nwu.ac.za/ServiceRequest/Edit/IR1660031/"),
    ("IR1", "ticket", None),
    ("", "incident", None),
    (None, "incident", None),
    ("IR1", None, None),
])
def test_build_scsm_url(work_item_id, ticket_type, expected):
    assert engine.build_scsm_url(work_item_id, ticket_type) == expected


def test_enrich_rows_uses_row_ticket_type():
    rows = [{"workItemId": "IR1", "title": "x", "ticketType": "incident"}]
    out = engine.enrich_rows(rows)
    assert out[0]["scsm_url"] == "https://support.nwu.ac.za/Incident/Edit/IR1/"
    assert out[0]["title"] == "x"


def test_enrich_rows_defaults_to_request_level_type():
    rows = [{"workItemId": "SR2", "title": "y"}]
    out = engine.enrich_rows(rows, ticket_type="servicerequest")
    assert out[0]["scsm_url"] == "https://support.nwu.ac.za/ServiceRequest/Edit/SR2/"


def test_enrich_rows_unknown_type_leaves_none_url():
    rows = [{"workItemId": "IR1", "ticketType": "bogus"}]
    assert engine.enrich_rows(rows)[0]["scsm_url"] is None


def test_enrich_rows_handles_none():
    assert engine.enrich_rows(None) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q tests/test_scsm_search_engine.py"`
Expected: FAIL — `from modules.scsm_search import engine` raises ImportError (module does not exist).

- [ ] **Step 3: Implement config + engine foundation**

In `config.py`, add after `QUICK_LINKS_FILE`:

```python
    SCSM_API_URL = os.getenv("SCSM_API_URL", "http://scsm-search:3000")
    SCSM_API_KEY = os.getenv("SCSM_API_KEY", "")
    SCSM_PORTAL_BASE = os.getenv("SCSM_PORTAL_BASE", "https://support.nwu.ac.za")
```

Create `modules/scsm_search/__init__.py`:

```python
from flask import Blueprint

bp = Blueprint("scsm_search", __name__, url_prefix="/api/scsm")
```

Create `modules/scsm_search/engine.py`:

```python
import logging

from config import Config

logger = logging.getLogger(__name__)

SCSM_API_URL = Config.SCSM_API_URL.rstrip("/")
SCSM_API_KEY = Config.SCSM_API_KEY
SCSM_PORTAL_BASE = Config.SCSM_PORTAL_BASE.rstrip("/")
REQUEST_TIMEOUT = 5

_KIND_SEGMENT = {
    "incident": "Incident",
    "servicerequest": "ServiceRequest",
}

ROLE_LABELS = {
    "affected": "Affected user",
    "created_by": "Created by",
    "assigned": "Assigned",
}


class ScsmError(Exception):
    def __init__(self, status_code, message, code="SCSM_ERROR"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class ScsmNotConfigured(ScsmError):
    def __init__(self):
        super().__init__(503, "SCSM API is not configured. Set SCSM_API_KEY.", code="SCSM_NOT_CONFIGURED")


class ScsmUpstreamError(ScsmError):
    pass


def build_scsm_url(work_item_id, ticket_type):
    if not work_item_id or not ticket_type:
        return None
    kind = _KIND_SEGMENT.get(str(ticket_type).lower())
    if not kind:
        return None
    value = str(work_item_id).strip()
    if not value:
        return None
    return f"{SCSM_PORTAL_BASE}/{kind}/Edit/{value}/"


def enrich_rows(rows, ticket_type=None):
    enriched = []
    for row in rows or []:
        out = dict(row)
        kind = ticket_type or out.get("ticketType")
        out["scsm_url"] = build_scsm_url(out.get("workItemId"), kind)
        enriched.append(out)
    return enriched
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the same pytest command from Step 2.
Expected: PASS (all 7).

- [ ] **Step 5: Commit**

```bash
git add config.py modules/scsm_search/__init__.py modules/scsm_search/engine.py tests/test_scsm_search_engine.py
git commit -m "feat: add scsm_search engine URL builders and config keys"
```

---

### Task 2: Engine proxy clients + typed error mapping + tests

**Files:**
- Modify: `modules/scsm_search/engine.py`
- Test: `tests/test_scsm_search_engine.py`

**Interfaces:**
- Consumes: Task 1 constants, `ScsmError`/`ScsmNotConfigured`/`ScsmUpstreamError`.
- Produces:
  - `def _request(method, path, **kwargs) -> dict` — raises `ScsmNotConfigured` (key unset), `ScsmUpstreamError(503)` on timeout/network error, `ScsmUpstreamError(502)` on upstream 401, `ScsmUpstreamError(status, text)` on other 4xx/5xx, else returns `resp.json()`.
  - `def search_tickets(q, ticket_type=None, page=1, page_size=25, **filters) -> dict`
  - `def search_users(q, page=1, page_size=25) -> dict`
  - `def fetch_user_tickets_page(user_id, role, page, page_size) -> dict`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scsm_search_engine.py`:

```python
import requests


class FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(engine, "SCSM_API_KEY", "test-key")


def test_request_not_configured(monkeypatch):
    monkeypatch.setattr(engine, "SCSM_API_KEY", "")
    with pytest.raises(engine.ScsmNotConfigured):
        engine.search_tickets("printer")


def test_request_maps_401_to_502(monkeypatch, api_key):
    def fake_request(method, url, **kwargs):
        return FakeResp(401, {})
    monkeypatch.setattr(engine.requests, "request", fake_request)
    with pytest.raises(engine.ScsmUpstreamError) as ei:
        engine.search_tickets("printer")
    assert ei.value.status_code == 502


def test_request_maps_timeout_to_503(monkeypatch, api_key):
    def fake_request(method, url, **kwargs):
        raise requests.exceptions.Timeout()
    monkeypatch.setattr(engine.requests, "request", fake_request)
    with pytest.raises(engine.ScsmUpstreamError) as ei:
        engine.search_tickets("printer")
    assert ei.value.status_code == 503


def test_request_maps_network_error_to_503(monkeypatch, api_key):
    def fake_request(method, url, **kwargs):
        raise requests.exceptions.ConnectionError("boom")
    monkeypatch.setattr(engine.requests, "request", fake_request)
    with pytest.raises(engine.ScsmUpstreamError) as ei:
        engine.search_tickets("printer")
    assert ei.value.status_code == 503


def test_request_passes_through_other_status(monkeypatch, api_key):
    def fake_request(method, url, **kwargs):
        return FakeResp(500, {"error": "internal"})
    monkeypatch.setattr(engine.requests, "request", fake_request)
    with pytest.raises(engine.ScsmUpstreamError) as ei:
        engine.search_tickets("printer")
    assert ei.value.status_code == 500


def test_search_tickets_forwards_params_and_header(monkeypatch, api_key):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, "params": kwargs.get("params"), "headers": kwargs.get("headers")})
        return FakeResp(200, {"results": [], "total": 0})

    monkeypatch.setattr(engine.requests, "request", fake_request)
    engine.search_tickets("printer", ticket_type="incident", status="Active")
    assert captured["method"] == "GET"
    assert captured["url"] == "http://scsm-search:3000/v1/search/tickets"
    assert captured["params"]["type"] == "incident"
    assert captured["params"]["q"] == "printer"
    assert captured["params"]["status"] == "Active"
    assert captured["headers"]["X-API-Key"] == "test-key"


def test_search_users_forwards_q(monkeypatch, api_key):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return FakeResp(200, {"results": [], "total": 0})

    monkeypatch.setattr(engine.requests, "request", fake_request)
    engine.search_users("smith")
    assert captured["params"]["q"] == "smith"


def test_fetch_user_tickets_page_forwards_role(monkeypatch, api_key):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return FakeResp(200, {"results": [], "total": 7})

    monkeypatch.setattr(engine.requests, "request", fake_request)
    data = engine.fetch_user_tickets_page("GUID", "created_by", 2, 100)
    assert data["total"] == 7
    assert captured["params"]["role"] == "created_by"
    assert captured["params"]["page"] == 2
    assert captured["params"]["pageSize"] == 100
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q tests/test_scsm_search_engine.py"`
Expected: FAIL — `AttributeError: module 'modules.scsm_search.engine' has no attribute 'requests'` (clients not implemented).

- [ ] **Step 3: Implement the proxy clients**

In `modules/scsm_search/engine.py`, change the import block to:

```python
import logging

import requests

from config import Config
```

Then append to `engine.py`:

```python
def _headers():
    if not SCSM_API_KEY:
        raise ScsmNotConfigured()
    return {"X-API-Key": SCSM_API_KEY}


def _request(method, path, **kwargs):
    try:
        resp = requests.request(method, f"{SCSM_API_URL}{path}", headers=_headers(), timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.exceptions.Timeout:
        raise ScsmUpstreamError(503, "SCSM API timed out.") from None
    except requests.exceptions.RequestException as exc:
        raise ScsmUpstreamError(503, f"SCSM API unreachable: {exc}") from exc
    if resp.status_code == 401:
        raise ScsmUpstreamError(502, "SCSM API rejected the configured API key.")
    if resp.status_code >= 400:
        raise ScsmUpstreamError(resp.status_code, resp.text[:200])
    try:
        return resp.json()
    except ValueError:
        raise ScsmUpstreamError(502, "SCSM API returned a non-JSON response.") from None


def search_tickets(q, ticket_type=None, page=1, page_size=25, **filters):
    params = {"q": q, "page": page, "pageSize": page_size}
    if ticket_type:
        params["type"] = ticket_type
    for key in ("status", "priority", "affectedUserId", "createdByUserId", "assignedUserId", "from", "to"):
        if filters.get(key) is not None:
            params[key] = filters[key]
    return _request("GET", "/v1/search/tickets", params=params)


def search_users(q, page=1, page_size=25):
    return _request("GET", "/v1/search/users", params={"q": q, "page": page, "pageSize": page_size})


def fetch_user_tickets_page(user_id, role, page, page_size):
    return _request(
        "GET",
        f"/v1/users/{user_id}/tickets",
        params={"role": role, "page": page, "pageSize": page_size},
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the same pytest command from Step 2.
Expected: PASS (all 9).

- [ ] **Step 5: Commit**

```bash
git add modules/scsm_search/engine.py tests/test_scsm_search_engine.py
git commit -m "feat: add scsm_search proxy clients and error mapping"
```

---

### Task 3: Dedup matrix + related-tickets cache + tests

**Files:**
- Modify: `modules/scsm_search/engine.py`
- Test: `tests/test_scsm_search_engine.py`

**Interfaces:**
- Consumes: Task 2 `fetch_user_tickets_page` (passed in as a callback).
- Produces:
  - `def dedup_matrix(affected, created_by, assigned) -> list[dict]` — returns `[{role, id, displayName}]` in display order (affected, created_by, assigned) honoring the spec's dedup rules: affected always (if present); created_by only if its id is not `affected` or `assigned`; assigned if present and not `affected`.
  - `class RelatedTicketsCache`:
    - `__init__(self, ttl_seconds=None, clock=None)`
    - `get(user_id, role) -> dict | None` (fresh entry or None)
    - `set(user_id, role, results, total)`
    - `is_fetching(user_id, role) -> bool`
    - `warm(user_id, role, fetch_page, page_size=100)` — in-flight-guarded; loops pages until `total` reached; stores on success; releases the guard on failure.
  - Module singleton `related_cache = RelatedTicketsCache()`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scsm_search_engine.py`:

```python
@pytest.mark.parametrize("affected,created_by,assigned,expected", [
    (A, B, C, [("affected", "A"), ("created_by", "B"), ("assigned", "C")]),
    (A, A, C, [("affected", "A"), ("assigned", "C")]),
    (A, B, A, [("affected", "A"), ("created_by", "B")]),
    (A, B, B, [("affected", "A"), ("assigned", "B")]),
    (A, A, A, [("affected", "A")]),
    (None, B, None, [("created_by", "B")]),
    (None, None, C, [("assigned", "C")]),
    (None, None, None, []),
])
def test_dedup_matrix(affected, created_by, assigned, expected):
    roles = engine.dedup_matrix(affected, created_by, assigned)
    assert [(r["role"], r["id"]) for r in roles] == expected


def test_cache_set_get_roundtrip():
    cache = engine.RelatedTicketsCache()
    assert cache.get("GUID", "affected") is None
    cache.set("GUID", "affected", [{"id": "t1"}], 1)
    assert cache.get("GUID", "affected")["total"] == 1


def test_cache_ttl_expiry():
    clock = {"now": 100.0}
    cache = engine.RelatedTicketsCache(ttl_seconds=60, clock=lambda: clock["now"])
    cache.set("GUID", "affected", [], 0)
    assert cache.get("GUID", "affected") is not None
    clock["now"] = 160.0
    assert cache.get("GUID", "affected") is None


def test_cache_warm_accumulates_across_pages():
    cache = engine.RelatedTicketsCache()
    seen = []

    def fetch_page(user_id, role, page, page_size):
        seen.append((user_id, role, page, page_size))
        if page == 1:
            return {"results": ["t1"] * 100, "total": 250}
        if page == 2:
            return {"results": ["t2"] * 100, "total": 250}
        return {"results": ["t3"] * 50, "total": 250}

    cache.warm("GUID", "affected", fetch_page, page_size=100)
    entry = cache.get("GUID", "affected")
    assert entry is not None
    assert entry["total"] == 250
    assert len(entry["results"]) == 250
    assert seen == [
        ("GUID", "affected", 1, 100),
        ("GUID", "affected", 2, 100),
        ("GUID", "affected", 3, 100),
    ]


def test_cache_warm_is_noop_when_already_fetching():
    cache = engine.RelatedTicketsCache()
    assert cache._claim("GUID", "affected") is True
    cache.warm("GUID", "affected", lambda *a: {"results": [], "total": 0})
    assert cache.get("GUID", "affected") is None


def test_cache_warm_failure_releases_and_does_not_cache():
    cache = engine.RelatedTicketsCache()

    def fetch_page(user_id, role, page, page_size):
        raise engine.ScsmUpstreamError(503, "boom")

    cache.warm("GUID", "affected", fetch_page)
    assert cache.get("GUID", "affected") is None
    assert cache.is_fetching("GUID", "affected") is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q tests/test_scsm_search_engine.py"`
Expected: FAIL — `AttributeError: module ... has no attribute 'dedup_matrix'` / `RelatedTicketsCache`.

- [ ] **Step 3: Implement the dedup matrix and cache**

Append to `modules/scsm_search/engine.py`:

```python
import threading
import time


def dedup_matrix(affected, created_by, assigned):
    roles = []
    if affected and affected.get("id"):
        roles.append(("affected", affected))
    if (
        created_by
        and created_by.get("id")
        and created_by["id"] != (affected or {}).get("id")
        and created_by["id"] != (assigned or {}).get("id")
    ):
        roles.append(("created_by", created_by))
    if assigned and assigned.get("id") and assigned["id"] != (affected or {}).get("id"):
        roles.append(("assigned", assigned))
    return [
        {"role": role, "id": person["id"], "displayName": person.get("displayName")}
        for role, person in roles
    ]


class RelatedTicketsCache:
    TTL_SECONDS = 30 * 60

    def __init__(self, ttl_seconds=None, clock=None):
        self._ttl = ttl_seconds if ttl_seconds is not None else self.TTL_SECONDS
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._data = {}
        self._inflight = set()

    def get(self, user_id, role):
        with self._lock:
            entry = self._data.get((user_id, role))
            if entry is not None and self._clock() - entry["loaded_at"] < self._ttl:
                return entry
        return None

    def set(self, user_id, role, results, total):
        with self._lock:
            self._data[(user_id, role)] = {
                "results": results,
                "total": total,
                "loaded_at": self._clock(),
            }

    def is_fetching(self, user_id, role):
        with self._lock:
            return (user_id, role) in self._inflight

    def _claim(self, user_id, role):
        with self._lock:
            if (user_id, role) in self._inflight:
                return False
            self._inflight.add((user_id, role))
            return True

    def _release(self, user_id, role):
        with self._lock:
            self._inflight.discard((user_id, role))

    def warm(self, user_id, role, fetch_page, page_size=100):
        if not self._claim(user_id, role):
            return
        try:
            page = 1
            accumulated = []
            total = None
            while True:
                data = fetch_page(user_id, role, page, page_size)
                results = data.get("results") or []
                accumulated.extend(results)
                total = data.get("total")
                if total is None:
                    break
                if page * page_size >= total or not results:
                    break
                page += 1
            if total is not None:
                self.set(user_id, role, accumulated, total)
        except Exception:
            logger.exception("Related tickets fetch failed for %s/%s", user_id, role)
        finally:
            self._release(user_id, role)


related_cache = RelatedTicketsCache()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the same pytest command from Step 2.
Expected: PASS (all 18).

- [ ] **Step 5: Commit**

```bash
git add modules/scsm_search/engine.py tests/test_scsm_search_engine.py
git commit -m "feat: add related-tickets dedup matrix and cache"
```

---

### Task 4: Routes + blueprint registration + route tests

**Files:**
- Create: `modules/scsm_search/routes.py`
- Modify: `modules/scsm_search/__init__.py`
- Modify: `app.py`
- Test: `tests/test_scsm_search_routes.py`

**Interfaces:**
- Consumes: Task 1-3 engine surface (`enrich_rows`, `build_scsm_url`, `search_tickets`, `search_users`, `fetch_user_tickets_page`, `dedup_matrix`, `related_cache`, `ROLE_LABELS`, `ScsmError`), blueprint `bp`.
- Produces (all JSON, under `/api/scsm/`):
  - `POST /api/scsm/tickets` — body `{q, status?, priority?, from?, to?}` → proxies both types, merges, sorts `createdDate` desc, enriches, returns `{results, total, page}`.
  - `POST /api/scsm/users` — body `{q}` → `{results, total}`.
  - `GET /api/scsm/users/<user_id>/tickets?role=` → cached `{results, total, ready: true}` or kicks background warm + `{results: [], total: null, ready: false}`.
  - `POST /api/scsm/related` — body `{ticket}` → dedup tabs + kicks warm per role, returns `{tabs: [{role, label, user, count}], primary: {workItemId, ticketType, scsm_url}}`.
  - Error mapping via a shared decorator; unset key → 503 `SCSM_NOT_CONFIGURED`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scsm_search_routes.py`:

```python
import pytest
from flask import Flask

import modules.scsm_search.routes as routes_module
from modules.scsm_search import engine
from modules.scsm_search.routes import bp as scsm_bp


class FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(engine, "SCSM_API_KEY", "test-key")
    monkeypatch.setattr(engine, "related_cache", engine.RelatedTicketsCache())
    monkeypatch.setattr(
        engine,
        "fetch_user_tickets_page",
        lambda *a, **k: {"results": [], "total": 0},
    )
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(scsm_bp)
    return app.test_client()


def test_tickets_requires_q(client):
    resp = client.post("/api/scsm/tickets", json={})
    assert resp.status_code == 400


def test_tickets_merges_sorts_and_enriches(client, monkeypatch):
    incident = {
        "results": [{
            "id": "a", "workItemId": "IR1", "title": "Printer", "status": "Active",
            "priority": "2", "createdDate": "2026-07-01T09:00:00Z",
            "affectedUser": {"id": "g1", "displayName": "John"},
            "createdByUser": None, "assignedUser": None,
        }],
        "total": 1,
    }
    servicerequest = {
        "results": [{
            "id": "b", "workItemId": "SR2", "title": "New PC", "status": "Active",
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
    resp = client.post("/api/scsm/tickets", json={"q": "printer"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 2
    assert [r["workItemId"] for r in data["results"]] == ["SR2", "IR1"]
    assert data["results"][1]["scsm_url"] == "https://support.nwu.ac.za/Incident/Edit/IR1/"


def test_tickets_not_configured_returns_503(client, monkeypatch):
    monkeypatch.setattr(engine, "SCSM_API_KEY", "")
    resp = client.post("/api/scsm/tickets", json={"q": "x"})
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "SCSM_NOT_CONFIGURED"


def test_tickets_upstream_401_maps_to_502(client, monkeypatch):
    def fake_request(method, url, **kwargs):
        return FakeResp(401, {})

    monkeypatch.setattr(engine.requests, "request", fake_request)
    resp = client.post("/api/scsm/tickets", json={"q": "x"})
    assert resp.status_code == 502


def test_users_returns_proxied_results(client, monkeypatch):
    payload = {
        "results": [{"id": "g", "userId": "jsmith", "displayName": "John Smith", "upn": "j@nwu.ac.za"}],
        "total": 1,
    }

    def fake_request(method, url, **kwargs):
        return FakeResp(200, payload)

    monkeypatch.setattr(engine.requests, "request", fake_request)
    resp = client.post("/api/scsm/users", json={"q": "smith"})
    assert resp.status_code == 200
    assert resp.get_json()["results"][0]["userId"] == "jsmith"


def test_users_requires_q(client):
    resp = client.post("/api/scsm/users", json={})
    assert resp.status_code == 400


def test_user_tickets_miss_returns_not_ready(client):
    resp = client.get("/api/scsm/users/GUID/tickets?role=affected")
    assert resp.status_code == 200
    assert resp.get_json() == {"results": [], "total": None, "ready": False}


def test_user_tickets_warm_returns_cached(client):
    engine.related_cache.set("GUID", "affected", [{"id": "t1"}], 1)
    resp = client.get("/api/scsm/users/GUID/tickets?role=affected")
    assert resp.status_code == 200
    assert resp.get_json() == {"results": [{"id": "t1"}], "total": 1, "ready": True}


def test_user_tickets_invalid_role_400(client):
    resp = client.get("/api/scsm/users/GUID/tickets?role=bogus")
    assert resp.status_code == 400


def test_related_returns_deduped_tabs_and_kicks_fetch(client, monkeypatch):
    spawned = []
    monkeypatch.setattr(routes_module, "_spawn_warm", lambda u, r: spawned.append((u, r)))
    ticket = {
        "workItemId": "IR1", "ticketType": "incident",
        "affectedUser": {"id": "A", "displayName": "Alice"},
        "createdByUser": {"id": "B", "displayName": "Bob"},
        "assignedUser": {"id": "B", "displayName": "Bob"},
    }
    engine.related_cache.set("A", "affected", [{"id": "t1"}], 5)
    resp = client.post("/api/scsm/related", json={"ticket": ticket})
    assert resp.status_code == 200
    data = resp.get_json()
    assert [t["role"] for t in data["tabs"]] == ["affected", "assigned"]
    assert data["tabs"][0]["count"] == 5
    assert data["tabs"][1]["count"] is None
    assert data["primary"] == {
        "workItemId": "IR1",
        "ticketType": "incident",
        "scsm_url": "https://support.nwu.ac.za/Incident/Edit/IR1/",
    }
    assert spawned == [("B", "assigned")]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q tests/test_scsm_search_routes.py"`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.scsm_search.routes'`.

- [ ] **Step 3: Implement routes + registration**

Create `modules/scsm_search/routes.py`:

```python
import functools
import threading

from flask import request

from modules.scsm_search import bp
from modules.scsm_search import engine


def _scsm_route(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except engine.ScsmError as exc:
            return {"error": {"code": exc.code, "message": str(exc)}}, exc.status_code

    return wrapper


def _spawn_warm(user_id, role):
    threading.Thread(
        target=engine.related_cache.warm,
        args=(user_id, role, engine.fetch_user_tickets_page),
        daemon=True,
    ).start()


@bp.post("/tickets")
@_scsm_route
def tickets():
    body = request.get_json(silent=True) or {}
    q = (body.get("q") or "").strip()
    if not q:
        return {"error": {"code": "BAD_REQUEST", "message": "q is required"}}, 400
    filters = {}
    for key in ("status", "priority", "from", "to"):
        if body.get(key) is not None:
            filters[key] = body[key]
    merged = []
    total = 0
    for ticket_type in ("incident", "servicerequest"):
        data = engine.search_tickets(q, ticket_type=ticket_type, page_size=25, **filters)
        merged.extend(engine.enrich_rows(data.get("results") or [], ticket_type=ticket_type))
        total += data.get("total") or 0
    merged.sort(key=lambda r: r.get("createdDate") or "", reverse=True)
    return {"results": merged, "total": total, "page": 1}


@bp.post("/users")
@_scsm_route
def users():
    body = request.get_json(silent=True) or {}
    q = (body.get("q") or "").strip()
    if not q:
        return {"error": {"code": "BAD_REQUEST", "message": "q is required"}}, 400
    return engine.search_users(q, page_size=25)


@bp.get("/users/<user_id>/tickets")
@_scsm_route
def user_tickets(user_id):
    role = request.args.get("role", "affected")
    if role not in engine.ROLE_LABELS:
        return {"error": {"code": "BAD_REQUEST", "message": "role must be affected, created_by or assigned"}}, 400
    entry = engine.related_cache.get(user_id, role)
    if entry is not None:
        return {"results": entry["results"], "total": entry["total"], "ready": True}
    if not engine.related_cache.is_fetching(user_id, role):
        _spawn_warm(user_id, role)
    return {"results": [], "total": None, "ready": False}


@bp.post("/related")
@_scsm_route
def related():
    body = request.get_json(silent=True) or {}
    ticket = body.get("ticket") or {}
    roles = engine.dedup_matrix(
        ticket.get("affectedUser"),
        ticket.get("createdByUser"),
        ticket.get("assignedUser"),
    )
    tabs = []
    for r in roles:
        entry = engine.related_cache.get(r["id"], r["role"])
        count = entry["total"] if entry else None
        if entry is None and not engine.related_cache.is_fetching(r["id"], r["role"]):
            _spawn_warm(r["id"], r["role"])
        tabs.append({
            "role": r["role"],
            "label": engine.ROLE_LABELS[r["role"]],
            "user": r["displayName"],
            "count": count,
        })
    primary = {
        "workItemId": ticket.get("workItemId"),
        "ticketType": ticket.get("ticketType"),
        "scsm_url": engine.build_scsm_url(ticket.get("workItemId"), ticket.get("ticketType")),
    }
    return {"tabs": tabs, "primary": primary}
```

In `modules/scsm_search/__init__.py`, change to:

```python
from flask import Blueprint

bp = Blueprint("scsm_search", __name__, url_prefix="/api/scsm")

from modules.scsm_search import routes  # noqa: E402, F401
```

In `app.py`, add the import and registration (mirror the `user_lookup` lines):

```python
    from modules.user_lookup import bp as user_lookup_bp
    from modules.scsm_search import bp as scsm_search_bp

    app.register_blueprint(user_lookup_bp)
    app.register_blueprint(scsm_search_bp)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the same pytest command from Step 2.
Expected: PASS (all 10).

- [ ] **Step 5: Commit**

```bash
git add modules/scsm_search/routes.py modules/scsm_search/__init__.py app.py tests/test_scsm_search_routes.py
git commit -m "feat: add /api/scsm proxy routes"
```

---

### Task 5: Page route, template, nav + tests

**Files:**
- Modify: `templates/routes.py`
- Modify: `templates/base.html`
- Create: `templates/scsm_search.html`
- Test: `tests/test_scsm_search_page.py`

**Interfaces:**
- Consumes: `/api/scsm/*` routes from Task 4.
- Produces: page `GET /scsm-search`, nav item "SCSM Search", and the split-pane page with spotlight, Google-style results, relationship tabs, and a detail pane.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scsm_search_page.py`:

```python
import os

from flask import Flask

from templates.routes import pages_bp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_scsm_search_page_renders():
    app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"))
    app.config["TESTING"] = True
    app.register_blueprint(pages_bp)
    resp = app.test_client().get("/scsm-search")
    assert resp.status_code == 200
    assert b"SCSM Search" in resp.data
    assert b"scsm-query" in resp.data
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q tests/test_scsm_search_page.py"`
Expected: FAIL — 404 (route not registered yet).

- [ ] **Step 3: Add the page route**

In `templates/routes.py`, add after `user_lookup`:

```python
@pages_bp.route("/scsm-search")
def scsm_search():
    return render_template("scsm_search.html")
```

- [ ] **Step 4: Add the nav item**

In `templates/base.html`, add before the Download Extension link (after the User Lookup link):

```html
            <a href="/scsm-search" class="{% if request.path == '/scsm-search' %}active{% endif %}">
                <span class="icon">🧭</span>
                <span>SCSM Search</span>
            </a>
```

- [ ] **Step 5: Create the page template**

Create `templates/scsm_search.html`:

```html
{% extends "base.html" %}

{% block title %}PCM Compass - SCSM Search{% endblock %}

{% block header %}SCSM Search{% endblock %}

{% block content %}
<div class="scsm-layout">
  <section class="scsm-master">
    <div class="scsm-searchbar">
      <span class="scsm-search-icon">⌕</span>
      <input id="scsm-query" type="text" placeholder="Search by ticket ID, keyword, or user name…"
             autocomplete="off" spellcheck="false" aria-label="Search SCSM">
      <kbd class="scsm-kbd">Ctrl&nbsp;K</kbd>
    </div>
    <div id="scsm-tabs" class="scsm-tabs" hidden></div>
    <div id="scsm-status" class="scsm-status" hidden></div>
    <div id="scsm-results" class="scsm-results" aria-live="polite"></div>
  </section>

  <section class="scsm-detail">
    <div id="scsm-detail-empty" class="scsm-detail-empty">Select a ticket to see its details.</div>
    <div id="scsm-detail" class="scsm-detail-content" hidden></div>
  </section>
</div>

<style>
  .scsm-layout { display: flex; gap: 1rem; height: calc(100vh - 12rem); min-height: 30rem; }
  .scsm-master { flex: 3; display: flex; flex-direction: column; min-width: 0; border: 1px solid #d0d7de; border-radius: 8px; overflow: hidden; background: #fff; }
  .scsm-searchbar { display: flex; align-items: center; gap: .5rem; padding: .6rem .8rem; border-bottom: 1px solid #d0d7de; }
  .scsm-searchbar input { flex: 1; border: none; outline: none; font-size: 1rem; }
  .scsm-search-icon { color: #8b949e; }
  .scsm-kbd { border: 1px solid #d0d7de; border-radius: 4px; padding: .1rem .35rem; font-size: .7rem; color: #57606a; }
  .scsm-tabs { display: flex; gap: .25rem; padding: .4rem .8rem 0; border-bottom: 1px solid #d0d7de; }
  .scsm-tab { background: none; border: none; border-bottom: 2px solid transparent; padding: .4rem .6rem; cursor: pointer; color: #57606a; font-size: .85rem; }
  .scsm-tab.active { border-bottom-color: #006633; color: #006633; font-weight: 600; }
  .scsm-tab .scsm-count { color: #8b949e; margin-left: .25rem; }
  .scsm-results { flex: 1; overflow-y: auto; padding: .25rem 0; }
  .scsm-status { padding: .4rem .8rem; font-size: .8rem; color: #57606a; }
  .scsm-result { display: block; width: 100%; text-align: left; padding: .6rem .8rem; border: none; background: none; border-bottom: 1px solid #f0f2f5; cursor: pointer; }
  .scsm-result:hover { background: #f6f8fa; }
  .scsm-result .scsm-title { font-size: .95rem; color: #006633; }
  .scsm-result .scsm-url { font-size: .78rem; color: #4a8c6f; word-break: break-all; }
  .scsm-result .scsm-snippet { font-size: .82rem; color: #57606a; margin-top: .15rem; }
  .scsm-type-chip { font-size: .68rem; color: #006633; border: 1px solid #4a8c6f; border-radius: 10px; padding: 0 .4rem; margin-right: .35rem; }
  .scsm-detail { flex: 2; min-width: 0; border: 1px solid #d0d7de; border-radius: 8px; overflow-y: auto; background: #fff; }
  .scsm-detail-empty { padding: 1rem; color: #8b949e; }
  .scsm-detail-content { padding: 1rem; }
  .scsm-detail-content h3 { margin: 0 0 .4rem; font-size: 1.1rem; }
  .scsm-detail-content .scsm-url { font-size: .8rem; color: #4a8c6f; word-break: break-all; }
  .scsm-open { display: inline-block; margin-top: .8rem; padding: .45rem .9rem; background: #006633; color: #fff; border-radius: 6px; text-decoration: none; font-size: .9rem; }
  .scsm-open:hover { background: #004d26; }
  .scsm-field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .4rem .8rem; margin-top: .8rem; }
  .scsm-field-grid dt { color: #8b949e; font-size: .75rem; text-transform: uppercase; }
  .scsm-field-grid dd { margin: 0; font-size: .9rem; }
  .scsm-person { background: none; border: none; color: #006633; cursor: pointer; padding: 0; font-size: .9rem; text-decoration: underline; }
  .scsm-placeholder { padding: .6rem .8rem; color: #8b949e; }
</style>
{% endblock %}

{% block scripts %}
<script>
(function () {
  'use strict';
  var queryEl = document.getElementById('scsm-query');
  var tabsEl = document.getElementById('scsm-tabs');
  var statusEl = document.getElementById('scsm-status');
  var resultsEl = document.getElementById('scsm-results');
  var detailEmptyEl = document.getElementById('scsm-detail-empty');
  var detailEl = document.getElementById('scsm-detail');

  var state = {
    query: '',
    user: null,
    roles: [],
    activeRole: null,
    pollTimer: null,
    lastSearch: null,
    lastSearchData: null,
  };

  function esc(s) {
    var div = document.createElement('div');
    div.textContent = s == null ? '' : String(s);
    return div.innerHTML;
  }

  function setStatus(text) {
    statusEl.hidden = !text;
    statusEl.textContent = text || '';
  }

  function clearList() {
    resultsEl.innerHTML = '';
  }

  function exitPerson() {
    if (state.pollTimer) { clearTimeout(state.pollTimer); state.pollTimer = null; }
    state.user = null;
    state.roles = [];
    state.activeRole = null;
    renderTabs([]);
  }

  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      queryEl.focus();
      queryEl.select();
    }
  });

  var debounceTimer = null;
  queryEl.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      var q = queryEl.value.trim();
      if (q === state.query) return;
      exitPerson();
      state.query = q;
      if (q.length < 2) {
        clearList();
        setStatus('');
        detailEmptyEl.hidden = false;
        detailEl.hidden = true;
        return;
      }
      doSearch(q);
    }, 250);
  });

  function renderTabs(roles, allCount) {
    state.roles = roles;
    if (!roles.length) {
      tabsEl.hidden = true;
      tabsEl.innerHTML = '';
      return;
    }
    tabsEl.hidden = false;
    var html = '<button class="scsm-tab' + (state.activeRole === null ? ' active' : '') +
      '" data-role="all">All results' + (allCount != null ? ' <span class="scsm-count">(' + allCount + ')</span>' : '') + '</button>';
    roles.forEach(function (r) {
      var count = r.count != null ? ' <span class="scsm-count">(' + r.count + ')</span>' : ' <span class="scsm-count">…</span>';
      html += '<button class="scsm-tab' + (state.activeRole === r.role ? ' active' : '') +
        '" data-role="' + r.role + '">' + esc(r.label) + count + '</button>';
    });
    tabsEl.innerHTML = html;
    tabsEl.querySelectorAll('.scsm-tab').forEach(function (btn) {
      btn.addEventListener('click', function () { onTabClick(btn.getAttribute('data-role')); });
    });
  }

  function onTabClick(role) {
    if (state.pollTimer) { clearTimeout(state.pollTimer); state.pollTimer = null; }
    if (role === 'all') {
      state.activeRole = null;
      renderTabs(state.roles);
      if (state.lastSearchData) {
        setStatus('');
        renderResults(state.lastSearchData.tickets || [], state.lastSearchData.users || []);
      }
      return;
    }
    state.activeRole = role;
    renderTabs(state.roles);
    loadRoleTickets(role);
  }

  function doSearch(q) {
    setStatus('Searching…');
    clearList();
    state.lastSearch = q;
    Promise.all([
      fetch('/api/scsm/tickets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ q: q }) }),
      fetch('/api/scsm/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ q: q }) }),
    ]).then(function (rs) {
      return Promise.all(rs.map(function (r) { return r.json(); }));
    }).then(function (data) {
      if (state.query !== q) return;
      state.lastSearchData = { tickets: data[0].results || [], users: data[1].results || [] };
      setStatus('');
      renderTabs([], data[0].total);
      renderResults(state.lastSearchData.tickets, state.lastSearchData.users);
    }).catch(function () {
      setStatus('Search failed — is the SCSM API configured?');
    });
  }

  function renderResults(tickets, users) {
    var html = '';
    users.forEach(function (u) {
      html += '<button class="scsm-result" data-user-id="' + esc(u.id) + '" data-user-name="' + esc(u.displayName) + '">' +
        '<div class="scsm-title">' + esc(u.displayName) + '</div>' +
        '<div class="scsm-snippet">' + esc(u.userId) + ' · ' + esc(u.upn) + '</div></button>';
    });
    tickets.forEach(function (t) {
      html += '<button class="scsm-result" data-ticket-id="' + esc(t.id) + '">' +
        '<div class="scsm-title"><span class="scsm-type-chip">' + esc((t.ticketType || 'ticket').toUpperCase()) + '</span>' + esc(t.workItemId) + ' · ' + esc(t.title) + '</div>' +
        '<div class="scsm-url">' + esc(t.scsm_url || '') + '</div>' +
        '<div class="scsm-snippet">' + esc(snippet(t)) + '</div></button>';
    });
    if (!html) html = '<div class="scsm-placeholder">No results.</div>';
    resultsEl.innerHTML = html;

    resultsEl.querySelectorAll('[data-user-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        enterPerson({ id: btn.getAttribute('data-user-id'), displayName: btn.getAttribute('data-user-name') }, null);
      });
    });
    resultsEl.querySelectorAll('[data-ticket-id]').forEach(function (btn) {
      var id = btn.getAttribute('data-ticket-id');
      var t = tickets.filter(function (x) { return x.id === id; })[0];
      btn.addEventListener('click', function () { selectTicket(t); });
    });
  }

  function snippet(t) {
    var parts = [];
    if (t.affectedUser) parts.push('Affected: ' + t.affectedUser.displayName);
    if (t.createdByUser) parts.push('Created by: ' + t.createdByUser.displayName);
    parts.push('Status: ' + t.status);
    if (t.createdDate) parts.push(new Date(t.createdDate).toLocaleDateString());
    return parts.join(' · ');
  }

  function selectTicket(t) {
    detailEmptyEl.hidden = true;
    detailEl.hidden = false;
    var grid = '';
    [['affectedUser', 'Affected'], ['createdByUser', 'Created by'], ['assignedUser', 'Assigned to']].forEach(function (p) {
      var person = t[p[0]];
      if (!person) return;
      grid += '<dt>' + p[1] + '</dt><dd><button class="scsm-person" data-uid="' + esc(person.id) + '" data-name="' + esc(person.displayName) + '">' + esc(person.displayName) + '</button></dd>';
    });
    grid += '<dt>Created</dt><dd>' + esc(t.createdDate ? new Date(t.createdDate).toLocaleString() : '') + '</dd>';
    grid += '<dt>Status</dt><dd>' + esc(t.status) + '</dd>';
    grid += '<dt>Priority</dt><dd>' + esc(t.priority == null ? '—' : t.priority) + '</dd>';
    detailEl.innerHTML =
      '<h3><span class="scsm-type-chip">' + esc((t.ticketType || 'ticket').toUpperCase()) + '</span>' + esc(t.workItemId) + '</h3>' +
      '<p>' + esc(t.title) + '</p>' +
      '<div class="scsm-url">' + esc(t.scsm_url || '') + '</div>' +
      '<dl class="scsm-field-grid">' + grid + '</dl>' +
      (t.scsm_url ? '<a class="scsm-open" href="' + esc(t.scsm_url) + '" target="_blank" rel="noopener noreferrer">Open in SCSM ↗</a>' : '');
    detailEl.querySelectorAll('.scsm-person').forEach(function (btn) {
      btn.addEventListener('click', function () {
        enterPerson({ id: btn.getAttribute('data-uid'), displayName: btn.getAttribute('data-name') }, t);
      });
    });
  }

  function enterPerson(user, fromTicket) {
    if (state.pollTimer) { clearTimeout(state.pollTimer); state.pollTimer = null; }
    state.user = user;
    state.query = '';
    queryEl.value = '';
    if (fromTicket) {
      fetch('/api/scsm/related', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ticket: fromTicket }) })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!state.user || state.user.id !== user.id) return;
          state.activeRole = data.tabs.length ? data.tabs[0].role : null;
          renderTabs(data.tabs);
          if (state.activeRole) loadRoleTickets(state.activeRole);
        })
        .catch(function () { setStatus('Could not load related tickets.'); });
    } else {
      var roles = [
        { role: 'affected', label: 'Affected user', user: user, count: null },
        { role: 'created_by', label: 'Created by', user: user, count: null },
        { role: 'assigned', label: 'Assigned', user: user, count: null },
      ];
      state.activeRole = 'affected';
      renderTabs(roles);
      loadRoleTickets('affected');
    }
  }

  function loadRoleTickets(role) {
    if (!state.user) return;
    var url = '/api/scsm/users/' + encodeURIComponent(state.user.id) + '/tickets?role=' + encodeURIComponent(role);
    fetch(url).then(function (r) { return r.json(); }).then(function (data) {
      if (!state.user || state.activeRole !== role) return;
      if (data.ready) {
        updateTabCount(role, data.total);
        setStatus('');
        renderRoleResults(data.results || []);
        if (state.pollTimer) { clearTimeout(state.pollTimer); state.pollTimer = null; }
      } else {
        updateTabCount(role, null);
        setStatus('Loading related tickets…');
        renderPlaceholder();
        state.pollTimer = setTimeout(function () { loadRoleTickets(role); }, 2000);
      }
    }).catch(function () { setStatus('Could not load related tickets.'); });
  }

  function updateTabCount(role, count) {
    state.roles.forEach(function (r) { if (r.role === role) r.count = count; });
    renderTabs(state.roles);
  }

  function renderRoleResults(rows) {
    var html = rows.map(function (t) {
      return '<button class="scsm-result" data-ticket-id="' + esc(t.id) + '">' +
        '<div class="scsm-title"><span class="scsm-type-chip">' + esc((t.ticketType || 'ticket').toUpperCase()) + '</span>' + esc(t.workItemId) + ' · ' + esc(t.title) + '</div>' +
        '<div class="scsm-url">' + esc(t.scsm_url || '') + '</div>' +
        '<div class="scsm-snippet">' + esc(snippet(t)) + '</div></button>';
    }).join('');
    if (!html) html = '<div class="scsm-placeholder">No tickets in this role.</div>';
    resultsEl.innerHTML = html;
    resultsEl.querySelectorAll('[data-ticket-id]').forEach(function (btn) {
      var id = btn.getAttribute('data-ticket-id');
      var t = rows.filter(function (x) { return x.id === id; })[0];
      btn.addEventListener('click', function () { selectTicket(t); });
    });
  }

  function renderPlaceholder() {
    resultsEl.innerHTML = '<div class="scsm-placeholder">Gathering tickets…</div>';
  }
})();
</script>
{% endblock %}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q tests/test_scsm_search_page.py"`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q"`
Expected: all tests pass (existing + new).

- [ ] **Step 8: Commit**

```bash
git add templates/routes.py templates/base.html templates/scsm_search.html tests/test_scsm_search_page.py
git commit -m "feat: add SCSM Search page with split-pane workspace"
```

- [ ] **Step 9: Manual smoke (optional but recommended)**

Start dev server locally and open `/scsm-search`; verify the search bar renders, results pane + detail pane split correctly, and nav highlights "SCSM Search". Live data requires `SCSM_API_KEY` set in `.env` and the scsm-search service reachable; without it the page should show the config banner text via the status line on search failure.

---

## Self-Review

- **Spec coverage:** §6.1 engine (build_scsm_url, enrich_rows, clients, cache) → Tasks 1-3. §6.2 routes + error mapping → Task 4. §6.3 template/UI → Task 5. §4.3 dedup matrix → Task 3. §4.2 progressive-disclosure cache + polling → Tasks 3-5 (tabs count placeholder `…`, `ready:false` → 2s polling). §7 config → Task 1. §8 tests → Tasks 1-5. ✓
- **Placeholder scan:** every step has concrete code and run commands; no TBD/TODO. ✓
- **Type consistency:** `dedup_matrix` returns `{role, id, displayName}` — consumed identically in Task 4 routes and Task 4 tests; `related_cache` singleton used in routes/tests; `_spawn_warm` calls `engine.related_cache.warm(user_id, role, engine.fetch_user_tickets_page)` matching the Task 3 `warm(user_id, role, fetch_page, page_size=100)` signature. ✓

