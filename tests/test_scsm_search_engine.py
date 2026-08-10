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
