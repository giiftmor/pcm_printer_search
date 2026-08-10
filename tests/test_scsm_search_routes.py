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
