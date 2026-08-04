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
