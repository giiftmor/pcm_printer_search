import json
import os

import pytest
from flask import Flask
from config import Config
from templates.routes import pages_bp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _extension_version():
    with open(os.path.join(ROOT, "browser_extension", "manifest.json")) as f:
        return json.load(f)["version"]


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(pages_bp)
    return app.test_client()


def test_status_returns_versions(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "PCM Compass"
    assert data["app_version"] == Config.APP_VERSION
    assert data["extension_version"] == _extension_version()


def test_status_app_version_matches_version_file():
    with open("VERSION") as f:
        assert Config.APP_VERSION == f.read().strip()
