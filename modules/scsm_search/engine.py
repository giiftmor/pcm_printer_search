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
