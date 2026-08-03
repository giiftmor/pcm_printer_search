import re
from typing import Optional

SVCP_DOMAIN = "svcp.nwu.ac.za"
_NWU_SUFFIX = ".nwu.ac.za"
_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def build_svcp_url(hostname: Optional[str]) -> Optional[str]:
    if hostname is None or not isinstance(hostname, str):
        return None
    name = hostname.strip().lower()
    if not name or "://" in name or "/" in name or any(c.isspace() for c in name):
        return None
    suffix = f".{SVCP_DOMAIN}"
    if name.endswith(suffix):
        name = name[: -len(suffix)]
    elif name.endswith(_NWU_SUFFIX):
        name = name.split(".", 1)[0]
    if not name or len(name) > 253:
        return None
    for label in name.split("."):
        if not _LABEL_RE.match(label):
            return None
    return f"https://{name}.{SVCP_DOMAIN}"


def enrich_row_with_svcp(row: dict) -> dict:
    url = build_svcp_url(row.get("Printer Hostname"))
    if url:
        row = dict(row)
        row["svcp_url"] = url
    return row
