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


@bp.get("/meta/filters")
@_scsm_route
def meta_filters():
    return engine.fetch_filters()


def _spawn_warm(user_id, role):
    threading.Thread(
        target=engine.related_cache.warm,
        args=(user_id, role, engine.fetch_user_tickets_page),
        daemon=True,
    ).start()


_BIG = 10 ** 9


def _relevance(row):
    rel = row.get("relevance")
    return rel if isinstance(rel, (int, float)) else _BIG


def _apply_sort(merged, sort):
    merged.sort(key=lambda r: r.get("createdDate") or "", reverse=True)
    if sort == "az":
        merged.sort(key=lambda r: (r.get("title") or "").lower())
    elif sort in (None, "relevance"):
        merged.sort(key=_relevance)


@bp.post("/tickets")
@_scsm_route
def tickets():
    body = request.get_json(silent=True) or {}
    q = (body.get("q") or "").strip()
    if not q:
        return {"error": {"code": "BAD_REQUEST", "message": "q is required"}}, 400
    filters = {}
    for key in ("status", "priority", "from", "to", "tier", "location", "sort"):
        if body.get(key) is not None:
            filters[key] = body[key]
    merged = []
    total = 0
    for ticket_type in ("incident", "servicerequest"):
        data = engine.search_tickets(q, ticket_type=ticket_type, page_size=25, **filters)
        merged.extend(engine.enrich_rows(data.get("results") or [], ticket_type=ticket_type))
        total += data.get("total") or 0
    _apply_sort(merged, filters.get("sort"))
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
            "id": r["id"],
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
