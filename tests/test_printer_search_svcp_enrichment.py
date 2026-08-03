import pytest
from modules.printer_search.svcp import enrich_row_with_svcp

def test_enrich_adds_svcp_url():
    row = enrich_row_with_svcp({"Printer Hostname": "lab-01", "Serial": "X"})
    assert row["svcp_url"] == "https://lab-01.svcp.nwu.ac.za"
    assert row["Serial"] == "X"

def test_enrich_skips_invalid():
    row = enrich_row_with_svcp({"Printer Hostname": "bad name", "Serial": "X"})
    assert "svcp_url" not in row

def test_enrich_skips_missing_key():
    row = enrich_row_with_svcp({"Serial": "X"})
    assert "svcp_url" not in row

def test_enrich_does_not_mutate_input():
    src = {"Printer Hostname": "lab-01"}
    enrich_row_with_svcp(src)
    assert "svcp_url" not in src
