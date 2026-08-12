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


def test_scsm_search_page_has_filter_bar():
    app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"))
    app.config["TESTING"] = True
    app.register_blueprint(pages_bp)
    resp = app.test_client().get("/scsm-search")
    assert resp.status_code == 200
    assert b"scsm-filters" in resp.data
    assert b"scsm-tier" in resp.data
    assert b"scsm-status" in resp.data
    assert b"scsm-location" in resp.data
    assert b"scsm-status-msg" in resp.data
