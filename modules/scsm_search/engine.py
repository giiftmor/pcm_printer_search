import logging

import requests

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
