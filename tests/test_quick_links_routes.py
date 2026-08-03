import os
import pytest
from flask import Flask
from core.auth import init_admin_password
from modules.quick_links import engine
from modules.quick_links.routes import links_bp

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "test-password")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(engine.Config, "QUICK_LINKS_FILE", str(tmp_path / "quick_links.json"))
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    init_admin_password(app)
    app.register_blueprint(links_bp)
    return app.test_client()


def login(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True


def test_get_links_returns_grouped(client):
    resp = client.get("/api/links")
    data = resp.get_json()
    assert resp.status_code == 200
    assert set(data.keys()) == {"categories"}
    assert [c["name"] for c in data["categories"]] == [
        "Portals", "Printing", "Identity", "SIS (Omnia)", "NAC",
    ]


def test_post_link_requires_category(client):
    resp = client.post("/api/links", json={"name": "X", "url": "https://x", "icon": "🔗"})
    assert resp.status_code == 403


def test_post_link_requires_auth(client):
    login(client)
    resp = client.post("/api/links", json={"name": "X", "url": "https://x"})
    assert resp.status_code == 400
    assert "Category" in resp.get_json()["error"]


def test_post_link_unknown_category(client):
    login(client)
    resp = client.post("/api/links", json={"category_id": "nope", "name": "X", "url": "https://x"})
    assert resp.status_code == 400


def test_post_link_success(client):
    login(client)
    cat_id = client.get("/api/links").get_json()["categories"][0]["id"]
    resp = client.post("/api/links", json={"category_id": cat_id, "name": "New", "url": "https://new"})
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "New"


def test_delete_link_requires_auth(client):
    login(client)
    cat = client.get("/api/links").get_json()["categories"][0]
    link_id = cat["links"][0]["id"]
    resp = client.delete(f"/api/links/{link_id}")
    assert resp.status_code == 200


def test_post_category(client):
    login(client)
    resp = client.post("/api/links/categories", json={"name": "Extra"})
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "Extra"


def test_delete_empty_category(client):
    login(client)
    cat_id = client.post("/api/links/categories", json={"name": "Empty"}).get_json()["id"]
    resp = client.delete(f"/api/links/categories/{cat_id}")
    assert resp.status_code == 200


def test_delete_non_empty_category_409(client):
    login(client)
    cat = client.get("/api/links").get_json()["categories"][0]
    resp = client.delete(f"/api/links/categories/{cat['id']}")
    assert resp.status_code == 409
