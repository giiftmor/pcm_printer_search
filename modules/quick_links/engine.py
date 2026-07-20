import json
import os
import uuid
from config import Config


def _load():
    path = Config.QUICK_LINKS_FILE
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"links": _default_links()}


def _save(data):
    with open(Config.QUICK_LINKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _default_links():
    return [
        {"id": str(uuid.uuid4()), "name": "SVCP Portal", "url": "https://svcp.nwu.ac.za", "icon": "🖨️"},
        {"id": str(uuid.uuid4()), "name": "PaperCut Admin", "url": "https://papercut.nwu.ac.za", "icon": "📊"},
        {"id": str(uuid.uuid4()), "name": "IDM", "url": "https://idm.nwu.ac.za", "icon": "👤"},
        {"id": str(uuid.uuid4()), "name": "Grouper", "url": "https://grp.nwu.ac.za/grouper/", "icon": "👥"},
    ]


def get_links():
    return _load()["links"]


def add_link(name, url, icon="🔗"):
    data = _load()
    link = {"id": str(uuid.uuid4()), "name": name, "url": url, "icon": icon}
    data["links"].append(link)
    _save(data)
    return link


def remove_link(link_id):
    data = _load()
    data["links"] = [l for l in data["links"] if l["id"] != link_id]
    _save(data)
