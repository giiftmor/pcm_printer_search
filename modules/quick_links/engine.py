import json
import os
import uuid
from config import Config


def _save(data):
    with open(Config.QUICK_LINKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _load():
    path = Config.QUICK_LINKS_FILE
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        if "categories" in data:
            return data
        if "links" in data:
            data = {
                "categories": [
                    {"id": str(uuid.uuid4()), "name": "General", "links": data["links"]}
                ]
            }
            _save(data)
            return data
    data = {"categories": _default_categories()}
    _save(data)
    return data


def _default_categories():
    return [
        {
            "id": str(uuid.uuid4()),
            "name": "Portals",
            "links": [
                {"id": str(uuid.uuid4()), "name": "SCSM Support Portal", "url": "https://support.nwu.ac.za/View/HomePage#/", "icon": "🎫"},
                {"id": str(uuid.uuid4()), "name": "Scopserve", "url": "http://143.160.36.111:5555/reports/telephony.php", "icon": "📞"},
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Printing",
            "links": [
                {"id": str(uuid.uuid4()), "name": "SVCP Portal", "url": "https://svcp.nwu.ac.za", "icon": "🖨️"},
                {"id": str(uuid.uuid4()), "name": "PaperCut Admin Portal", "url": "http://v-pcut-win1.nwu.ac.za:9191/app", "icon": "🖨️"},
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Identity",
            "links": [
                {"id": str(uuid.uuid4()), "name": "IDM", "url": "https://idm.nwu.ac.za", "icon": "👤"},
                {"id": str(uuid.uuid4()), "name": "Grouper", "url": "https://grp.nwu.ac.za/grouper/", "icon": "👥"},
                {"id": str(uuid.uuid4()), "name": "Microsoft Entra", "url": "https://entra.microsoft.com/#home", "icon": "🪪"},
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "name": "SIS (Omnia)",
            "links": [
                {"id": str(uuid.uuid4()), "name": "Omnia (SIS Password Reset)", "url": "https://omnia.nwu.ac.za/omnia/send_sis_password_info", "icon": "🔑"},
                {"id": str(uuid.uuid4()), "name": "Omnia (SIS Profile Overview)", "url": "https://omnia.nwu.ac.za/omnia/get_sis_provisioning_info_page", "icon": "📋"},
            ],
        },
        {
            "id": str(uuid.uuid4()),
            "name": "NAC",
            "links": [
                {"id": str(uuid.uuid4()), "name": "MAN NAC", "url": "https://196.252.138.240:8443/gui/hosts/view", "icon": "🌐"},
                {"id": str(uuid.uuid4()), "name": "NAC 1 (Campus B) LAN", "url": "https://196.252.138.242:8443/gui/hosts/adapters", "icon": "🏛️"},
                {"id": str(uuid.uuid4()), "name": "NAC 1 (Campus B) WIFI", "url": "https://196.252.138.241:8443/gui/hosts/view", "icon": "📶"},
                {"id": str(uuid.uuid4()), "name": "NAC 2 (Campus A) LAN", "url": "https://196.252.138.243:8443/gui/hosts/adapters", "icon": "🏛️"},
                {"id": str(uuid.uuid4()), "name": "NAC 2 (Campus A) WIFI", "url": "https://196.252.138.244:8443/gui/hosts/view", "icon": "📶"},
            ],
        },
    ]


def get_categories():
    return _load()["categories"]


def add_category(name):
    data = _load()
    category = {"id": str(uuid.uuid4()), "name": name, "links": []}
    data["categories"].append(category)
    _save(data)
    return category


def remove_category(category_id):
    data = _load()
    for cat in data["categories"]:
        if cat["id"] == category_id:
            if cat["links"]:
                raise ValueError("Category is not empty")
            data["categories"] = [c for c in data["categories"] if c["id"] != category_id]
            _save(data)
            return True
    return False


def add_link(category_id, name, url, icon="🔗"):
    data = _load()
    for cat in data["categories"]:
        if cat["id"] == category_id:
            link = {"id": str(uuid.uuid4()), "name": name, "url": url, "icon": icon}
            cat["links"].append(link)
            _save(data)
            return link
    raise KeyError(f"Category not found: {category_id}")


def remove_link(link_id):
    data = _load()
    for cat in data["categories"]:
        before = len(cat["links"])
        cat["links"] = [l for l in cat["links"] if l["id"] != link_id]
        if len(cat["links"]) != before:
            _save(data)
            return True
    return False
