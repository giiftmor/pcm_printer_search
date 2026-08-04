from modules.user_lookup.urls import build_grouper_group_url, GROUPER_GROUP_PRESETS

GROUP_URL = "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do"


def test_build_grouper_group_url_basic():
    url = build_grouper_group_url("nwu:groups:Azure:Azure_Include_Staff")
    assert url.startswith(GROUP_URL + "?")
    assert "typeName=group" in url
    assert "subjectType=group" in url
    assert "sourceId=g%3Agsa" in url
    assert "name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff" in url
    assert "returnTo=%2FdoSearchSubjects.do" in url


def test_build_grouper_group_url_optional_description():
    url = build_grouper_group_url(
        "nwu:groups:Adobe:Acrobat_fedID_users_include", "Acrobat Include"
    )
    assert "description=Acrobat%20Include" in url


def test_build_grouper_group_url_no_description_by_default():
    url = build_grouper_group_url("nwu:groups:Azure:Azure_Include_Staff")
    assert "description=" not in url


def test_build_grouper_group_url_rejects_invalid():
    assert build_grouper_group_url("") is None
    assert build_grouper_group_url("   ") is None
    assert build_grouper_group_url(None) is None


def test_build_grouper_group_url_trims():
    url = build_grouper_group_url("  nwu:groups:Azure:Azure_Include_Staff  ")
    assert "name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff" in url


def test_presets_have_expected_shape():
    assert len(GROUPER_GROUP_PRESETS) == 7
    names = {p["name"] for p in GROUPER_GROUP_PRESETS}
    assert "nwu:groups:Azure:Azure_Include_Staff" in names
    assert "Papercut_pcm_staff_include" in names
    for p in GROUPER_GROUP_PRESETS:
        assert {"id", "label", "name"} <= set(p)
        assert build_grouper_group_url(p["name"]) is not None


import pytest
from flask import Flask
from modules.user_lookup import bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(bp)
    return app.test_client()


def test_grouper_presets_endpoint(client):
    resp = client.get("/api/user-lookup/grouper-presets")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["presets"]) == 7
    p = data["presets"][0]
    assert {"id", "label", "name", "url"} <= set(p)
    assert p["url"].startswith("https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?")


def test_group_url_endpoint(client):
    resp = client.get(
        "/api/user-lookup/group-url?name=nwu:groups:Azure:Azure_Include_Staff"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "nwu:groups:Azure:Azure_Include_Staff"
    assert "name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff" in data["url"]


def test_group_url_endpoint_requires_name(client):
    assert client.get("/api/user-lookup/group-url").status_code == 400
    assert client.get("/api/user-lookup/group-url?name=").status_code == 400
    assert client.get("/api/user-lookup/group-url?name=%20%20").status_code == 400
