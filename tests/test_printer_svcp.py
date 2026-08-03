import pytest
from modules.printer_search.svcp import build_svcp_url

@pytest.mark.parametrize("raw,expected", [
    ("printer01", "https://printer01.svcp.nwu.ac.za"),
    ("  PRINTER01  ", "https://printer01.svcp.nwu.ac.za"),
    ("printer01.svcp.nwu.ac.za", "https://printer01.svcp.nwu.ac.za"),
    ("printer01.campus.nwu.ac.za", "https://printer01.svcp.nwu.ac.za"),
    ("", None),
    (None, None),
    ("https://evil.example", None),
    ("printer 01", None),
    ('printer"onclick', None),
    ("a/b", None),
    ("-bad", None),
    ("bad-", None),
])
def test_build_svcp_url(raw, expected):
    assert build_svcp_url(raw) == expected
