# Quick Links Categorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two-level category grouping to the Quick Links module (category → links) across the Flask engine, API, web UI, and Chrome extension, with a new 13-link seed inventory and tests.

**Architecture:** `quick_links.json` changes from `{"links": [...]}` to `{"categories": [{id, name, links: [...]}]}`. `engine.py` gains migration + grouped CRUD (links by category, add/remove category). `routes.py` returns the grouped shape and adds category endpoints. Web UI and extension popup both render one section per category. Legacy flat data auto-migrates to a single "General" category on read.

**Tech Stack:** Python 3.11, Flask 2.x, pytest (new), vanilla JS, Chrome Extension MV3

## Global Constraints

- Python 3.11, Flask 2.x, no external JS frameworks
- NWU green branding: `#006633` primary, `#4a8c6f` secondary
- JSON endpoints prefixed `/api/`; admin mutations guarded by `core.auth.admin_required`
- Category `id` and link `id` are `uuid4` strings
- No changes to `modules/user_lookup/`, `modules/printer_search/`, or their endpoints
- Extension keeps offline fallback (`DEFAULT_LINKS` → restructured to categories)
- Only 13 seeded links; categories exactly: Portals, Printing, Identity, SIS (Omnia), NAC
- Commit per task; update `CHANGELOG.md` and `~/projects/tailnet-changelog/CHANGELOG.md` on every meaningful change

---

### Task 1: Engine — grouped model, migration, CRUD, seed

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_quick_links_engine.py`
- Rewrite: `modules/quick_links/engine.py`

**Interfaces:**
- Consumes: `Config.QUICK_LINKS_FILE` (unchanged)
- Produces:
  - `get_categories() -> list[dict]` — list of `{"id", "name", "links": [...]}`
  - `add_category(name: str) -> dict` — creates empty category
  - `remove_category(category_id: str) -> bool` — raises `ValueError` if non-empty
  - `add_link(category_id: str, name: str, url: str, icon: str = "🔗") -> dict` — raises `KeyError` if category unknown
  - `remove_link(link_id: str) -> bool`

- [ ] **Step 1: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest>=7.0,<9.0
pytest-cov>=4.0,<7.0
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")
```

- [ ] **Step 3: Write the failing engine tests in `tests/test_quick_links_engine.py`**

```python
import pytest
from modules.quick_links import engine


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    links_file = tmp_path / "quick_links.json"
    monkeypatch.setattr(engine.Config, "QUICK_LINKS_FILE", str(links_file))
    if links_file.exists():
        links_file.unlink()
    return links_file


def test_seed_defaults_are_grouped(isolated):
    categories = engine.get_categories()
    names = [c["name"] for c in categories]
    assert names == ["Portals", "Printing", "Identity", "SIS (Omnia)", "NAC"]
    total_links = sum(len(c["links"]) for c in categories)
    assert total_links == 13
    for cat in categories:
        assert cat["id"]
        for link in cat["links"]:
            assert link["id"]
            assert link["name"]
            assert link["url"]
            assert link["icon"]


def test_legacy_flat_data_migrates_to_general(isolated):
    isolated.write_text(
        '{"links": [{"id": "a", "name": "Old", "url": "https://x", "icon": "🔗"}]}'
    )
    categories = engine.get_categories()
    assert len(categories) == 1
    assert categories[0]["name"] == "General"
    assert categories[0]["links"][0]["name"] == "Old"


def test_add_and_remove_link_by_category(isolated):
    cat_id = engine.get_categories()[0]["id"]
    link = engine.add_link(cat_id, "New Link", "https://example.com", "🖥️")
    cats = engine.get_categories()
    assert any(l["id"] == link["id"] for l in cats[0]["links"])
    assert engine.remove_link(link["id"]) is True
    cats = engine.get_categories()
    assert all(l["id"] != link["id"] for c in cats for l in c["links"])


def test_add_link_unknown_category_raises(isolated):
    with pytest.raises(KeyError):
        engine.add_link("missing", "X", "https://example.com")


def test_add_and_remove_category(isolated):
    cat = engine.add_category("Temp")
    assert cat["name"] == "Temp"
    assert cat["links"] == []
    assert engine.remove_category(cat["id"]) is True


def test_remove_non_empty_category_raises(isolated):
    cat = engine.add_category("Busy")
    engine.add_link(cat["id"], "X", "https://example.com")
    with pytest.raises(ValueError):
        engine.remove_category(cat["id"])
    assert len(engine.get_categories()) == 6


def test_mutation_persists_grouped_shape(isolated):
    cat = engine.add_category("Persist")
    assert "categories" in isolated.read_text()
    engine.add_link(cat["id"], "L", "https://example.com")
    assert '"categories"' in isolated.read_text()
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `pip install -r requirements-dev.txt && python -m pytest tests/test_quick_links_engine.py -v`
Expected: FAIL/ERROR — engine still returns the legacy shape (`KeyError: 'categories'` / attribute errors).

- [ ] **Step 5: Rewrite `modules/quick_links/engine.py`**

```python
import json
import os
import uuid
from config import Config


def _load():
    path = Config.QUICK_LINKS_FILE
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        if "categories" in data:
            return data
        if "links" in data:
            return {
                "categories": [
                    {"id": str(uuid.uuid4()), "name": "General", "links": data["links"]}
                ]
            }
    return {"categories": _default_categories()}


def _save(data):
    with open(Config.QUICK_LINKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


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
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_quick_links_engine.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements-dev.txt tests/conftest.py tests/test_quick_links_engine.py modules/quick_links/engine.py
git commit -m "feat: grouped quick links engine with migration, category CRUD, 13-link seed"
```

---

### Task 2: Routes — grouped API + category endpoints

**Files:**
- Rewrite: `modules/quick_links/routes.py`
- Create: `tests/test_quick_links_routes.py`

**Interfaces:**
- Consumes: `get_categories`, `add_category`, `remove_category`, `add_link`, `remove_link` from Task 1
- Produces:
  - `GET /api/links` → `{"categories": [...]}`
  - `POST /api/links` → 201 link / 400 (requires `category_id`, `name`, `url`)
  - `DELETE /api/links/<link_id>` → `{"success": True}`
  - `POST /api/links/categories` → 201 category / 400 (requires `name`)
  - `DELETE /api/links/categories/<category_id>` → 200 / 409 non-empty / 404 unknown
  - All POST/DELETE → 403 when not admin

- [ ] **Step 1: Write the failing route tests in `tests/test_quick_links_routes.py`**

```python
import os
import pytest
from flask import Flask
from core.auth import init_admin_password
from modules.quick_links import engine
from modules.quick_links.routes import links_bp

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "test-password")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(engine.Config, "QUICK_LINKS_FILE", str(tmp_path / "quick_links.json"))
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    init_admin_password(app)
    app.register_blueprint(links_bp)
    return app.test_client()


def login(client):
    client.post("/api/admin/login", data={"password": ADMIN_PASSWORD})


def test_get_links_returns_grouped(client):
    resp = client.get("/api/links")
    data = resp.get_json()
    assert resp.status_code == 200
    assert set(data.keys()) == {"categories"}
    assert [c["name"] for c in data["categories"]] == [
        "Portals", "Printing", "Identity", "SIS (Omnia)", "NAC",
    ]


def test_post_link_requires_category(client):
    resp = client.post("/api/links", json={"name": "X", "url": "https://x", "icon": "🔗"})
    assert resp.status_code == 403


def test_post_link_requires_auth(client):
    login(client)
    resp = client.post("/api/links", json={"name": "X", "url": "https://x"})
    assert resp.status_code == 400
    assert "Category" in resp.get_json()["error"]


def test_post_link_unknown_category(client):
    login(client)
    resp = client.post("/api/links", json={"category_id": "nope", "name": "X", "url": "https://x"})
    assert resp.status_code == 400


def test_post_link_success(client):
    login(client)
    cat_id = client.get("/api/links").get_json()["categories"][0]["id"]
    resp = client.post("/api/links", json={"category_id": cat_id, "name": "New", "url": "https://new"})
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "New"


def test_delete_link_requires_auth(client):
    login(client)
    cat = client.get("/api/links").get_json()["categories"][0]
    link_id = cat["links"][0]["id"]
    resp = client.delete(f"/api/links/{link_id}")
    assert resp.status_code == 200


def test_post_category(client):
    login(client)
    resp = client.post("/api/links/categories", json={"name": "Extra"})
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "Extra"


def test_delete_empty_category(client):
    login(client)
    cat_id = client.post("/api/links/categories", json={"name": "Empty"}).get_json()["id"]
    resp = client.delete(f"/api/links/categories/{cat_id}")
    assert resp.status_code == 200


def test_delete_non_empty_category_409(client):
    login(client)
    cat = client.get("/api/links").get_json()["categories"][0]
    resp = client.delete(f"/api/links/categories/{cat['id']}")
    assert resp.status_code == 409
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_quick_links_routes.py -v`
Expected: FAIL — current routes return the legacy flat list and lack category endpoints.

- [ ] **Step 3: Rewrite `modules/quick_links/routes.py`**

```python
from flask import Blueprint, request, jsonify
from modules.quick_links.engine import (
    get_categories,
    add_category,
    remove_category,
    add_link,
    remove_link,
)
from core.auth import admin_required

links_bp = Blueprint("links", __name__)


@links_bp.route("/api/links")
def list_links():
    return jsonify({"categories": get_categories()})


@links_bp.route("/api/links", methods=["POST"])
@admin_required
def create_link():
    data = request.get_json(silent=True) or {}
    category_id = (data.get("category_id") or "").strip()
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    icon = (data.get("icon") or "🔗").strip()
    if not category_id or not name or not url:
        return jsonify({"error": "Category, name, and URL required"}), 400
    try:
        return jsonify(add_link(category_id, name, url, icon)), 201
    except KeyError:
        return jsonify({"error": "Unknown category"}), 400


@links_bp.route("/api/links/<link_id>", methods=["DELETE"])
@admin_required
def delete_link(link_id):
    remove_link(link_id)
    return jsonify({"success": True})


@links_bp.route("/api/links/categories", methods=["POST"])
@admin_required
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    return jsonify(add_category(name)), 201


@links_bp.route("/api/links/categories/<category_id>", methods=["DELETE"])
@admin_required
def delete_category(category_id):
    try:
        removed = remove_category(category_id)
    except ValueError:
        return jsonify({"error": "Category is not empty"}), 409
    if not removed:
        return jsonify({"error": "Category not found"}), 404
    return jsonify({"success": True})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_quick_links_routes.py -v`
Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add modules/quick_links/routes.py tests/test_quick_links_routes.py
git commit -m "feat: grouped quick links API with category endpoints"
```

---

### Task 3: Web UI — grouped render + admin category management

**Files:**
- Rewrite: `templates/quick_links.html`

**Interfaces:**
- Consumes: `GET /api/links` (`{"categories": [...]}`), `POST /api/links`, `DELETE /api/links/<id>`, `POST /api/links/categories`, `DELETE /api/links/categories/<id>` from Task 2, `GET /api/admin/status`
- Produces: page rendering one section per category; admin form with category select, add-category, per-category delete

- [ ] **Step 1: Rewrite `templates/quick_links.html`**

```html
{% extends "base.html" %}
{% block title %}PCM Compass - Quick Links{% endblock %}
{% block header %}Quick Links{% endblock %}
{% block content %}
<div class="card">
    <h3>Quick Links</h3>
    <div id="linksGrid"></div>
</div>

<div class="card" id="adminSection" style="display:none;">
    <h3>Add New Link</h3>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <select id="linkCategory" style="padding:8px;border:1px solid #ddd;border-radius:4px;"></select>
        <input type="text" id="linkName" placeholder="Name" style="flex:1;min-width:120px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <input type="text" id="linkUrl" placeholder="URL" style="flex:2;min-width:200px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <input type="text" id="linkIcon" placeholder="Icon (emoji)" style="width:80px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <button class="btn btn-primary" onclick="addLink()">Add</button>
    </div>

    <h3 style="margin-top:20px;">Categories</h3>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
        <input type="text" id="categoryName" placeholder="New category name" style="flex:1;min-width:160px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <button class="btn btn-primary" onclick="addCategory()">Add Category</button>
    </div>
    <div id="categoryList"></div>
</div>

<script>
let isAdmin = false;
let categoriesData = [];

document.addEventListener('DOMContentLoaded', () => {
    loadLinks();
    checkAdmin();
});

function checkAdmin() {
    fetch('/api/admin/status').then(r => r.json()).then(d => {
        isAdmin = d.is_admin;
        document.getElementById('adminSection').style.display = isAdmin ? 'block' : 'none';
        if (isAdmin) loadLinks();
    });
}

function loadLinks() {
    fetch('/api/links').then(r => r.json()).then(data => {
        categoriesData = data.categories || [];
        renderGrid();
        if (isAdmin) { renderCategorySelect(); renderCategoryList(); }
    });
}

function renderGrid() {
    const grid = document.getElementById('linksGrid');
    grid.innerHTML = categoriesData.map(cat => `
        <div class="links-category" style="margin-bottom:24px;">
            <h3 style="margin-bottom:12px;">${cat.name}</h3>
            <div class="dashboard-grid">
                ${cat.links.map(l => `
                    <a href="${l.url}" target="_blank" class="dashboard-card" style="text-align:center;">
                        <div class="card-icon">${l.icon}</div>
                        <h3>${l.name}</h3>
                        ${isAdmin ? `<button onclick="event.preventDefault();deleteLink('${l.id}')" style="margin-top:8px;padding:4px 8px;font-size:11px;background:#dc3545;color:white;border:none;border-radius:4px;cursor:pointer;">Remove</button>` : ''}
                    </a>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function renderCategorySelect() {
    const sel = document.getElementById('linkCategory');
    sel.innerHTML = categoriesData.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
}

function renderCategoryList() {
    const list = document.getElementById('categoryList');
    list.innerHTML = categoriesData.map(c => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;border:1px solid #eee;border-radius:4px;margin-bottom:6px;">
            <span>${c.name} (${c.links.length})</span>
            <button onclick="deleteCategory('${c.id}')" style="padding:4px 8px;font-size:11px;background:#dc3545;color:white;border:none;border-radius:4px;cursor:pointer;">Delete</button>
        </div>
    `).join('');
}

function addLink() {
    const category_id = document.getElementById('linkCategory').value;
    const name = document.getElementById('linkName').value.trim();
    const url = document.getElementById('linkUrl').value.trim();
    const icon = document.getElementById('linkIcon').value.trim() || '🔗';
    if (!category_id || !name || !url) return;
    fetch('/api/links', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_id, name, url, icon })
    }).then(resp => {
        if (!resp.ok) return resp.json().then(d => { throw new Error(d.error); });
        document.getElementById('linkName').value = '';
        document.getElementById('linkUrl').value = '';
        document.getElementById('linkIcon').value = '';
        loadLinks();
    }).catch(err => alert(err.message));
}

function addCategory() {
    const name = document.getElementById('categoryName').value.trim();
    if (!name) return;
    fetch('/api/links/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    }).then(resp => {
        if (!resp.ok) return resp.json().then(d => { throw new Error(d.error); });
        document.getElementById('categoryName').value = '';
        loadLinks();
    }).catch(err => alert(err.message));
}

function deleteLink(id) {
    fetch(`/api/links/${id}`, { method: 'DELETE' }).then(() => loadLinks());
}

function deleteCategory(id) {
    fetch(`/api/links/categories/${id}`, { method: 'DELETE' }).then(resp => {
        if (!resp.ok) return resp.json().then(d => { throw new Error(d.error); });
        loadLinks();
    }).catch(err => alert(err.message));
}
</script>
{% endblock %}
```

- [ ] **Step 2: Verify in browser**

Run: `python app.py` → open `http://localhost:5000/quick-links`
Expected: 5 category sections (Portals, Printing, Identity, SIS (Omnia), NAC) each with their links. As admin (login via session cookie set through `/api/admin/login`), the Add Link form shows a category dropdown, and the Categories list shows delete buttons; deleting a non-empty category shows an alert.

- [ ] **Step 3: Commit**

```bash
git add templates/quick_links.html
git commit -m "feat: grouped quick links web UI with admin category management"
```

---

### Task 4: Extension — grouped fallback + sectioned popup

**Files:**
- Modify: `browser_extension/popup.js`
- Modify: `browser_extension/popup.css`

**Interfaces:**
- Consumes: `GET /api/links` → `{"categories": [...]}` (optional; fallback offline)
- Produces: `DEFAULT_CATEGORIES` constant + `renderLinks(categories)` rendering grouped sections; scrollable Quick Links area

- [ ] **Step 1: Update `browser_extension/popup.js`**

Replace `const DEFAULT_LINKS = [...]` (lines 107-112) and the `renderLinks` + `loadQuickLinks` functions (lines 114-128) with:

```javascript
const DEFAULT_CATEGORIES = [
    { name: 'Portals', links: [
        { name: 'SCSM Support Portal', url: 'https://support.nwu.ac.za/View/HomePage#/', icon: '🎫' },
        { name: 'Scopserve', url: 'http://143.160.36.111:5555/reports/telephony.php', icon: '📞' },
    ] },
    { name: 'Printing', links: [
        { name: 'SVCP Portal', url: 'https://svcp.nwu.ac.za', icon: '🖨️' },
        { name: 'PaperCut Admin Portal', url: 'http://v-pcut-win1.nwu.ac.za:9191/app', icon: '🖨️' },
    ] },
    { name: 'Identity', links: [
        { name: 'IDM', url: 'https://idm.nwu.ac.za', icon: '👤' },
        { name: 'Grouper', url: 'https://grp.nwu.ac.za/grouper/', icon: '👥' },
        { name: 'Microsoft Entra', url: 'https://entra.microsoft.com/#home', icon: '🪪' },
    ] },
    { name: 'SIS (Omnia)', links: [
        { name: 'Omnia Pwd Reset', url: 'https://omnia.nwu.ac.za/omnia/send_sis_password_info', icon: '🔑' },
        { name: 'Omnia Profile', url: 'https://omnia.nwu.ac.za/omnia/get_sis_provisioning_info_page', icon: '📋' },
    ] },
    { name: 'NAC', links: [
        { name: 'MAN NAC', url: 'https://196.252.138.240:8443/gui/hosts/view', icon: '🌐' },
        { name: 'NAC 1 B LAN', url: 'https://196.252.138.242:8443/gui/hosts/adapters', icon: '🏛️' },
        { name: 'NAC 1 B WIFI', url: 'https://196.252.138.241:8443/gui/hosts/view', icon: '📶' },
        { name: 'NAC 2 A LAN', url: 'https://196.252.138.243:8443/gui/hosts/adapters', icon: '🏛️' },
        { name: 'NAC 2 A WIFI', url: 'https://196.252.138.244:8443/gui/hosts/view', icon: '📶' },
    ] },
];

function renderLinks(categories) {
    const grid = document.getElementById('quickLinks');
    grid.innerHTML = categories.map(cat => `
        <div class="link-group">
            <div class="link-group-title">${cat.name}</div>
            <div class="links-grid">${cat.links.map(l => `<a href="${l.url}" target="_blank">${l.icon} ${l.name}</a>`).join('')}</div>
        </div>
    `).join('');
}

async function loadQuickLinks() {
    try {
        const appUrl = await getAppUrl();
        const res = await fetch(`${appUrl}/api/links`);
        const data = await res.json();
        renderLinks(data.categories || DEFAULT_CATEGORIES);
    } catch {
        renderLinks(DEFAULT_CATEGORIES);
    }
}
```

- [ ] **Step 2: Update `browser_extension/popup.css`**

Add after the `.links-grid` rules:

```css
.link-group { margin-bottom: 10px; }
.link-group-title { font-size: 12px; font-weight: 600; color: #006633; margin-bottom: 6px; }
#quickLinks { max-height: 300px; overflow-y: auto; }
```

- [ ] **Step 3: Verify in browser**

Load `browser_extension/` as unpacked in Chrome. Click the popup icon.
Expected: Quick Links section shows 5 group headers (Portals, Printing, Identity, SIS (Omnia), NAC) with their links; area scrolls if it overflows; links open in new tabs; IDM/Grouper/Printer Search sections unchanged.

- [ ] **Step 4: Rebuild the extension package**

Run: `./bin/build-extension.sh`
Expected: `static/dist/pcm-compass-v2.1.0.zip` regenerated and (if `curl` present) uploaded to Nextcloud.

- [ ] **Step 5: Commit**

```bash
git add browser_extension/popup.js browser_extension/popup.css static/dist/pcm-compass-v2.1.0.zip
git commit -m "feat: grouped quick links in extension popup with scrollable fallback"
```

---

### Task 5: Reseed data file + docs + status tracking

**Files:**
- Rewrite: `quick_links.json`
- Modify: `major-improvements-implementation-status.md`
- Modify: `CHANGELOG.md`
- Modify: `~/projects/tailnet-changelog/CHANGELOG.md`

**Interfaces:**
- Consumes: grouped seed shape from Task 1
- Produces: committed grouped seed; Stream 0 tracked in the improvements status doc

- [ ] **Step 1: Rewrite `quick_links.json`**

```json
{
  "categories": [
    {
      "id": "seed-portals",
      "name": "Portals",
      "links": [
        { "id": "seed-portal-scsm", "name": "SCSM Support Portal", "url": "https://support.nwu.ac.za/View/HomePage#/", "icon": "🎫" },
        { "id": "seed-portal-scopserve", "name": "Scopserve", "url": "http://143.160.36.111:5555/reports/telephony.php", "icon": "📞" }
      ]
    },
    {
      "id": "seed-printing",
      "name": "Printing",
      "links": [
        { "id": "seed-print-svcp", "name": "SVCP Portal", "url": "https://svcp.nwu.ac.za", "icon": "🖨️" },
        { "id": "seed-print-papercut", "name": "PaperCut Admin Portal", "url": "http://v-pcut-win1.nwu.ac.za:9191/app", "icon": "🖨️" }
      ]
    },
    {
      "id": "seed-identity",
      "name": "Identity",
      "links": [
        { "id": "seed-identity-idm", "name": "IDM", "url": "https://idm.nwu.ac.za", "icon": "👤" },
        { "id": "seed-identity-grouper", "name": "Grouper", "url": "https://grp.nwu.ac.za/grouper/", "icon": "👥" },
        { "id": "seed-identity-entra", "name": "Microsoft Entra", "url": "https://entra.microsoft.com/#home", "icon": "🪪" }
      ]
    },
    {
      "id": "seed-omnia",
      "name": "SIS (Omnia)",
      "links": [
        { "id": "seed-omnia-reset", "name": "Omnia (SIS Password Reset)", "url": "https://omnia.nwu.ac.za/omnia/send_sis_password_info", "icon": "🔑" },
        { "id": "seed-omnia-profile", "name": "Omnia (SIS Profile Overview)", "url": "https://omnia.nwu.ac.za/omnia/get_sis_provisioning_info_page", "icon": "📋" }
      ]
    },
    {
      "id": "seed-nac",
      "name": "NAC",
      "links": [
        { "id": "seed-nac-man", "name": "MAN NAC", "url": "https://196.252.138.240:8443/gui/hosts/view", "icon": "🌐" },
        { "id": "seed-nac-1b-lan", "name": "NAC 1 (Campus B) LAN", "url": "https://196.252.138.242:8443/gui/hosts/adapters", "icon": "🏛️" },
        { "id": "seed-nac-1b-wifi", "name": "NAC 1 (Campus B) WIFI", "url": "https://196.252.138.241:8443/gui/hosts/view", "icon": "📶" },
        { "id": "seed-nac-2a-lan", "name": "NAC 2 (Campus A) LAN", "url": "https://196.252.138.243:8443/gui/hosts/adapters", "icon": "🏛️" },
        { "id": "seed-nac-2a-wifi", "name": "NAC 2 (Campus A) WIFI", "url": "https://196.252.138.244:8443/gui/hosts/view", "icon": "📶" }
      ]
    }
  ]
}
```

> Note: static `seed-*` ids keep the committed file stable; the engine's own `_default_categories()` generates `uuid4` ids only when no file exists.

- [ ] **Step 2: Add Stream 0 to `major-improvements-implementation-status.md`**

Insert a new **"Stream 0 — Feature: Quick Links Categorization ✅"** section after the **Program Structure** intro (before Stream 1). Content:

```markdown
### Stream 0 — Feature: Quick Links Categorization ✅

**Goal:** Group quick links into categories across engine, API, web UI, and extension.

- Link inventory expanded from 4 to 13 links across 5 categories: Portals (SCSM, Scopserve), Printing (SVCP, PaperCut), Identity (IDM, Grouper, Entra), SIS Omnia (Password Reset, Profile Overview), NAC (MAN, Campus A/B LAN + WIFI).
- Two-level data model `{"categories": [{id, name, links}]}` with legacy flat-data auto-migration to a "General" category.
- New admin endpoints: `POST /api/links/categories`, `DELETE /api/links/categories/<id>` (409 if non-empty); `POST /api/links` now requires `category_id`.
- Extension popup renders grouped, scrollable Quick Links with matching offline fallback.
- Spec: `docs/superpowers/specs/2026-08-03-quick-links-categorization-design.md`
- Plan: `.opencode/plans/2026-08-03-quick-links-categorization.md`
```

Also update the **Progress Log** table with:

```markdown
| 2026-08-03 | Stream 0 | Quick Links categorization | ✅ |
```

- [ ] **Step 3: Update `CHANGELOG.md`**

Under `[Unreleased]` → `### Added`:

```markdown
- 2026-08-03: Quick Links categorized into 5 groups (Portals, Printing, Identity, SIS Omnia, NAC) — grouped data model with legacy migration, category admin endpoints, sectioned web UI + extension popup
```

- [ ] **Step 4: Update tailnet changelog**

Append one line to `~/projects/tailnet-changelog/CHANGELOG.md`:

```markdown
- 2026-08-03: PCM Compass — quick links grouped into categories with 13-link inventory + category admin
```

- [ ] **Step 5: Full verification**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS (engine 7 + routes 10).

Run: `python app.py` → check `http://localhost:5000/quick-links` and the extension popup.
Expected: 5 grouped sections everywhere; extension fallback matches server seed.

- [ ] **Step 6: Commit**

```bash
git add quick_links.json major-improvements-implementation-status.md CHANGELOG.md
git commit -m "feat: reseed grouped quick links, track Stream 0 in improvements status"
```

---

## Self-Review Notes

- Spec coverage: data model ✅ (T1), migration ✅ (T1), seed ✅ (T1/T5), API grouped GET + POST link + category endpoints ✅ (T2), 403/400/409 semantics ✅ (T2 tests), web UI grouped render + admin select + category manager ✅ (T3), extension grouped fallback + scroll ✅ (T4), tests ✅ (T1/T2), status doc ✅ (T5).
- Type consistency: `get_categories/add_category/remove_category/add_link/remove_link` signatures are identical across engine (T1), routes (T2), and web UI JS calls. `POST /api/links` body key is `category_id` everywhere.
- Backward-compat note: existing `quick_links.json` is rewritten to the grouped seed in T5; before that task the running app reads the old flat file and migrates it to a "General" category automatically, so no broken intermediate state.
