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


import requests


class FakeResp:
    def __init__(self, status_code, payload, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

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
            return {"results": [{"workItemId": "IR1", "ticketType": "incident"}] * 100, "total": 250}
        if page == 2:
            return {"results": [{"workItemId": "SR2", "ticketType": "servicerequest"}] * 100, "total": 250}
        return {"results": [{"workItemId": "IR3", "ticketType": "incident"}] * 50, "total": 250}

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


def test_cache_warm_enriches_rows_with_scsm_url():
    cache = engine.RelatedTicketsCache()

    def fetch_page(user_id, role, page, page_size):
        return {"results": [{"id": "t1", "workItemId": "IR2", "ticketType": "servicerequest"}], "total": 1}

    cache.warm("GUID", "affected", fetch_page)
    entry = cache.get("GUID", "affected")
    assert entry is not None
    assert entry["results"][0]["scsm_url"] == "https://support.nwu.ac.za/ServiceRequest/Edit/IR2/"


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
