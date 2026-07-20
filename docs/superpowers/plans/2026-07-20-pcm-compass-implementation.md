# PCM Compass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform PCM Printer Search into PCM Compass — a modular IT helpdesk toolkit with Flask dashboard + Chrome extension.

**Architecture:** Flask app with module-based structure (one folder per tool), dashboard-style UI with sidebar nav, Chrome extension as quick-access launcher. Each module has its own routes/engine.

**Tech Stack:** Python 3.11, Flask, Pandas, openpyxl, Gunicorn, Docker, Jinja2, vanilla JS, Chrome Extension MV3

## Global Constraints

- Python 3.11, Flask 2.x, Pandas 1.3+, openpyxl 3.x
- Docker multi-stage build (existing pattern)
- No JS frameworks — vanilla JS only
- Chrome Extension Manifest V3
- NWU green branding (#006633 primary, #4a8c6f secondary)
- All routes prefixed `/api/` for JSON endpoints
- Admin auth: bcrypt for password hashing, Flask session-based
- No NWU credentials stored anywhere in our code

---

## File Structure

```
pcm-compass/
├── app.py                          # App factory, register blueprints
├── config.py                       # Config from env vars
├── requirements.txt                # Updated deps
├── Dockerfile                      # Updated for new structure
├── docker-compose.yml              # Unchanged
├── docker-compose.dev.yml          # Unchanged
├── .env.example                    # Updated
├── CHANGELOG.md
├── AGENTS.md
│
├── core/
│   ├── __init__.py
│   ├── auth.py                     # Admin auth (bcrypt + session)
│   └── http_client.py              # Shared requests wrapper
│
├── modules/
│   ├── __init__.py                 # Module registry
│   ├── printer_search/
│   │   ├── __init__.py
│   │   ├── routes.py               # Blueprint: printer_bp
│   │   └── engine.py               # Excel load, search, CRUD
│   ├── idm_lookup/
│   │   ├── __init__.py
│   │   ├── routes.py               # Blueprint: idm_bp
│   │   └── engine.py               # IDM URL construction
│   ├── grouper/
│   │   ├── __init__.py
│   │   ├── routes.py               # Blueprint: grouper_bp
│   │   └── engine.py               # Grouper URL construction
│   └── quick_links/
│       ├── __init__.py
│       ├── routes.py               # Blueprint: links_bp
│       └── engine.py               # Link CRUD (JSON storage)
│
├── templates/
│   ├── base.html                   # Dashboard shell
│   ├── dashboard.html              # Home page
│   ├── printer_search.html         # Printer search page
│   ├── idm_lookup.html             # IDM lookup page
│   ├── grouper.html                # Grouper lookup page
│   └── quick_links.html            # Quick links page
│
├── static/
│   ├── css/
│   │   └── compass.css             # Dashboard + branding CSS
│   ├── js/
│   │   └── compass.js              # Shared JS
│   └── img/
│       └── nwu-logo.png            # NWU logo
│
└── browser_extension/
    ├── manifest.json               # Updated MV3
    ├── popup.html                  # Redesigned popup
    ├── popup.css                   # New styling
    ├── popup.js                    # New logic
    ├── settings.html               # Settings page
    ├── settings.js                 # Settings logic
    └── icons/                      # Existing icons
```

---

### Task 1: Project Restructure & Config

**Files:**
- Create: `config.py`, `core/__init__.py`, `core/auth.py`, `modules/__init__.py`
- Modify: `app.py`, `requirements.txt`, `.env.example`, `Dockerfile`, `AGENTS.md`

**Interfaces:**
- Consumes: existing `app.py` with all routes inline
- Produces: `create_app()` factory, `config` module, `core` package

- [ ] **Step 1: Create config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-do-not-use-in-production")
    ADMIN_PASSWORD_HASH = None  # Set at startup from env
    WORKBOOK_URL = os.getenv("WORKBOOK_URL", "https://nextcloud.nwu.ac.za/index.php/s/4RdDP4qX3mMoXc7")
    DATA_REFRESH_INTERVAL = int(os.getenv("DATA_REFRESH_INTERVAL", "60"))
    QUICK_LINKS_FILE = os.getenv("QUICK_LINKS_FILE", "quick_links.json")
```

- [ ] **Step 2: Create core/__init__.py**

```python
# Core package
```

- [ ] **Step 3: Create core/auth.py**

```python
import bcrypt
from functools import wraps
from flask import session, jsonify


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def check_password(password: str, password_hash: bytes) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash)


def init_admin_password(app):
    from config import Config
    raw = os.getenv("ADMIN_PASSWORD", "print@NWU")
    Config.ADMIN_PASSWORD_HASH = hash_password(raw)


import os


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return decorated
```

- [ ] **Step 4: Create modules/__init__.py**

```python
# Module registry
```

- [ ] **Step 5: Update requirements.txt**

```
flask>=2.0,<3.0
pandas>=1.3
openpyxl>=3.0,<4.0
requests>=2.25,<3.0
gunicorn>=20.1,<22.0
python-dotenv>=0.19,<2.0
bcrypt>=4.0,<5.0
```

- [ ] **Step 6: Rewrite app.py as app factory**

```python
from flask import Flask
from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from core.auth import init_admin_password
    init_admin_password(app)

    from modules.printer_search.routes import printer_bp
    from modules.idm_lookup.routes import idm_bp
    from modules.grouper.routes import grouper_bp
    from modules.quick_links.routes import links_bp

    app.register_blueprint(printer_bp)
    app.register_blueprint(idm_bp)
    app.register_blueprint(grouper_bp)
    app.register_blueprint(links_bp)

    from templates.routes import pages_bp
    app.register_blueprint(pages_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
```

- [ ] **Step 7: Update .env.example**

```
FLASK_SECRET_KEY=your-random-secret-key-here
ADMIN_PASSWORD=print@NWU
WORKBOOK_URL=https://nextcloud.nwu.ac.za/index.php/s/4RdDP4qX3mMoXc7
DATA_REFRESH_INTERVAL=60
```

- [ ] **Step 8: Create template routes placeholder**

Create `templates/__init__.py`:
```python
# Templates package
```

Create `templates/routes.py`:
```python
from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@pages_bp.route("/printer-search")
def printer_search():
    return render_template("printer_search.html")


@pages_bp.route("/idm-lookup")
def idm_lookup():
    return render_template("idm_lookup.html")


@pages_bp.route("/grouper")
def grouper():
    return render_template("grouper.html")


@pages_bp.route("/quick-links")
def quick_links():
    return render_template("quick_links.html")
```

- [ ] **Step 9: Verify app starts**

Run: `python app.py`
Expected: Flask starts on port 5000 without errors

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: restructure into app factory with module architecture"
```

---

### Task 2: Dashboard Base Template & CSS

**Files:**
- Create: `templates/base.html`, `templates/dashboard.html`, `static/css/compass.css`, `static/js/compass.js`
- Modify: none (standalone)

**Interfaces:**
- Consumes: page routes from Task 1
- Produces: base template with sidebar nav, NWU branding, responsive layout

- [ ] **Step 1: Create static/css/compass.css**

```css
:root {
    --nwu-green: #006633;
    --nwu-green-light: #4a8c6f;
    --nwu-green-bg: #e8f5e9;
    --sidebar-width: 260px;
    --header-height: 60px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f2f5;
    color: #333;
    min-height: 100vh;
}

/* Sidebar */
.sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: var(--sidebar-width);
    height: 100vh;
    background: var(--nwu-green);
    color: white;
    display: flex;
    flex-direction: column;
    z-index: 100;
}

.sidebar-brand {
    padding: 20px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    display: flex;
    align-items: center;
    gap: 12px;
}

.sidebar-brand img {
    height: 36px;
}

.sidebar-brand h1 {
    font-size: 18px;
    font-weight: 600;
}

.sidebar-nav {
    flex: 1;
    padding: 12px 0;
    overflow-y: auto;
}

.sidebar-nav a {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    color: rgba(255,255,255,0.8);
    text-decoration: none;
    transition: all 0.2s;
    font-size: 14px;
}

.sidebar-nav a:hover,
.sidebar-nav a.active {
    background: rgba(255,255,255,0.1);
    color: white;
}

.sidebar-nav a .icon {
    font-size: 18px;
    width: 24px;
    text-align: center;
}

/* Main content */
.main {
    margin-left: var(--sidebar-width);
    min-height: 100vh;
}

.header {
    height: var(--header-height);
    background: white;
    border-bottom: 1px solid #e0e0e0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 30px;
    position: sticky;
    top: 0;
    z-index: 50;
}

.header h2 {
    font-size: 16px;
    color: #555;
}

.content {
    padding: 30px;
}

/* Cards */
.card {
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    padding: 24px;
    margin-bottom: 20px;
}

.card h3 {
    color: var(--nwu-green);
    margin-bottom: 16px;
    font-size: 18px;
}

/* Search input */
.search-group {
    display: flex;
    gap: 8px;
    margin: 16px 0;
}

.search-group input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
}

.search-group input:focus {
    outline: none;
    border-color: var(--nwu-green);
    box-shadow: 0 0 0 2px rgba(0,102,51,0.15);
}

/* Buttons */
.btn {
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary {
    background: var(--nwu-green);
    color: white;
}

.btn-primary:hover {
    background: var(--nwu-green-light);
}

.btn-secondary {
    background: #e9ecef;
    color: #333;
}

.btn-secondary:hover {
    background: #dee2e6;
}

/* Dashboard grid */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
}

.dashboard-card {
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    padding: 24px;
    text-decoration: none;
    color: inherit;
    transition: all 0.2s;
    border-left: 4px solid var(--nwu-green);
}

.dashboard-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    transform: translateY(-2px);
}

.dashboard-card .card-icon {
    font-size: 32px;
    margin-bottom: 12px;
}

.dashboard-card h3 {
    color: var(--nwu-green);
    margin-bottom: 8px;
}

.dashboard-card p {
    color: #666;
    font-size: 14px;
}

/* Responsive */
@media (max-width: 768px) {
    .sidebar { width: 60px; }
    .sidebar-brand h1 { display: none; }
    .sidebar-nav a span { display: none; }
    .main { margin-left: 60px; }
}
```

- [ ] **Step 2: Create static/js/compass.js**

```javascript
// PCM Compass - Shared JS

// Admin auth
async function checkAdminStatus() {
    try {
        const res = await fetch('/api/admin/status');
        const data = await res.json();
        return data.is_admin;
    } catch { return false; }
}

async function adminLogin(password) {
    const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `password=${encodeURIComponent(password)}`
    });
    return res.json();
}

async function adminLogout() {
    await fetch('/api/admin/logout', { method: 'POST' });
}

// Message display
function showMessage(container, message, type) {
    container.innerHTML = `<div class="message ${type}">${message}</div>`;
    setTimeout(() => container.innerHTML = '', 5000);
}
```

- [ ] **Step 3: Create templates/base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PCM Compass{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/compass.css">
    <link rel="icon" href="/favicon.ico">
</head>
<body>
    <nav class="sidebar">
        <div class="sidebar-brand">
            <img src="/static/img/nwu-logo.png" alt="NWU">
            <h1>PCM Compass</h1>
        </div>
        <div class="sidebar-nav">
            <a href="/" class="{% if request.path == '/' %}active{% endif %}">
                <span class="icon">🏠</span>
                <span>Dashboard</span>
            </a>
            <a href="/printer-search" class="{% if request.path == '/printer-search' %}active{% endif %}">
                <span class="icon">🖨️</span>
                <span>Printer Search</span>
            </a>
            <a href="/idm-lookup" class="{% if request.path == '/idm-lookup' %}active{% endif %}">
                <span class="icon">👤</span>
                <span>IDM Lookup</span>
            </a>
            <a href="/grouper" class="{% if request.path == '/grouper' %}active{% endif %}">
                <span class="icon">👥</span>
                <span>Grouper Groups</span>
            </a>
            <a href="/quick-links" class="{% if request.path == '/quick-links' %}active{% endif %}">
                <span class="icon">🔗</span>
                <span>Quick Links</span>
            </a>
        </div>
    </nav>

    <main class="main">
        <header class="header">
            <h2>{% block header %}Dashboard{% endblock %}</h2>
            <div id="admin-controls"></div>
        </header>
        <div class="content">
            {% block content %}{% endblock %}
        </div>
    </main>

    <script src="/static/js/compass.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Create templates/dashboard.html**

```html
{% extends "base.html" %}
{% block title %}PCM Compass - Dashboard{% endblock %}
{% block header %}Dashboard{% endblock %}
{% block content %}
<div class="dashboard-grid">
    <a href="/printer-search" class="dashboard-card">
        <div class="card-icon">🖨️</div>
        <h3>Printer Search</h3>
        <p>Search printer data by hostname, serial, MAC, or location.</p>
    </a>
    <a href="/idm-lookup" class="dashboard-card">
        <div class="card-icon">👤</div>
        <h3>IDM Lookup</h3>
        <p>Look up a user's IDM profile information.</p>
    </a>
    <a href="/grouper" class="dashboard-card">
        <div class="card-icon">👥</div>
        <h3>Grouper Groups</h3>
        <p>View a user's group memberships in Grouper.</p>
    </a>
    <a href="/quick-links" class="dashboard-card">
        <div class="card-icon">🔗</div>
        <h3>Quick Links</h3>
        <p>Quick access to NWU IT service desk tools.</p>
    </a>
</div>
{% endblock %}
```

- [ ] **Step 5: Verify app renders dashboard**

Run: `python app.py` then open http://localhost:5000/
Expected: Dashboard with 4 cards, sidebar nav, NWU green branding

- [ ] **Step 6: Commit**

```bash
git add templates/ static/
git commit -m "feat: add dashboard base template with sidebar nav and NWU branding"
```

---

### Task 3: Printer Search Module

**Files:**
- Create: `modules/printer_search/__init__.py`, `modules/printer_search/routes.py`, `modules/printer_search/engine.py`, `templates/printer_search.html`
- Move: existing logic from `app.py` into module files
- Delete: old inline routes from `app.py` (already done in Task 1)

**Interfaces:**
- Consumes: `create_app()` registers `printer_bp`
- Produces: `POST /api/printer/search`, `GET /api/printer/last-update`, admin CRUD endpoints

- [ ] **Step 1: Create modules/printer_search/__init__.py**

```python
# Printer Search module
```

- [ ] **Step 2: Create modules/printer_search/engine.py**

Move the Excel loading/search logic from old `app.py`:

```python
import pandas as pd
import requests
from io import BytesIO
import os
import threading
import time
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

URL_STORAGE_FILE = "workbook_url.txt"

df_all_sheets = None
last_update_time = None
data_load_lock = threading.Lock()


def get_saved_url():
    try:
        if os.path.exists(URL_STORAGE_FILE):
            with open(URL_STORAGE_FILE, "r") as f:
                return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading saved URL: {e}")
    return Config.WORKBOOK_URL


def save_url(url):
    try:
        with open(URL_STORAGE_FILE, "w") as f:
            f.write(url.strip())
        return True
    except Exception as e:
        logger.error(f"Error saving URL: {e}")
        return False


def load_excel_from_url():
    global last_update_time
    try:
        base_url = get_saved_url()
        if not base_url.endswith("/download"):
            url = base_url + "/download"
        else:
            url = base_url

        logger.info(f"Downloading Excel from: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        excel_file = BytesIO(response.content)
        new_data = pd.read_excel(excel_file, sheet_name=None)
        last_update_time = datetime.now()
        logger.info(f"Excel loaded. Sheets: {list(new_data.keys())}")
        return new_data
    except Exception as e:
        logger.error(f"Error loading Excel: {e}")
        return None


def search_all_sheets(search_term):
    with data_load_lock:
        if df_all_sheets is None or not df_all_sheets:
            return {"error": "Data not loaded."}

        all_results = []
        for sheet_name, df in df_all_sheets.items():
            results = df[df.apply(
                lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(),
                axis=1
            )]
            if not results.empty:
                results_cleaned = results.fillna("")
                results_cleaned["Sheet Name"] = sheet_name
                all_results.append(results_cleaned)

        if not all_results:
            return {"error": "No results found."}

        results_df = pd.concat(all_results, ignore_index=True)
        results_df = results_df.map(str).replace("nan", "")
        return results_df.to_dict(orient="records")


def auto_reload_data():
    while True:
        time.sleep(Config.DATA_REFRESH_INTERVAL)
        try:
            with data_load_lock:
                global df_all_sheets
                new_data = load_excel_from_url()
                if new_data is not None:
                    df_all_sheets = new_data
        except Exception as e:
            logger.error(f"Auto-reload error: {e}")


def init():
    global df_all_sheets
    df_all_sheets = load_excel_from_url()
    thread = threading.Thread(target=auto_reload_data, daemon=True)
    thread.start()
```

- [ ] **Step 3: Create modules/printer_search/routes.py**

```python
from flask import Blueprint, request, jsonify, session
from modules.printer_search.engine import (
    search_all_sheets, get_saved_url, save_url,
    load_excel_from_url, data_load_lock, df_all_sheets,
    last_update_time, init
)
from core.auth import admin_required
import logging

logger = logging.getLogger(__name__)
printer_bp = Blueprint("printer", __name__)

# Initialize module on import
init()


@printer_bp.route("/api/printer/search", methods=["POST"])
def search():
    search_term = request.form.get("search_term", "").strip()
    if not search_term:
        return jsonify({"error": "Please enter a search term."})
    logger.info(f"Search: '{search_term}'")
    return jsonify(search_all_sheets(search_term))


@printer_bp.route("/api/printer/last-update")
def last_update():
    from modules.printer_search.engine import last_update_time
    return jsonify({
        "last_update": last_update_time.isoformat() if last_update_time else None,
        "timestamp": last_update_time.strftime("%Y-%m-%d %H:%M:%S") if last_update_time else "Never"
    })


@printer_bp.route("/api/admin/status")
def admin_status():
    return jsonify({"is_admin": session.get("is_admin", False)})


@printer_bp.route("/api/admin/login", methods=["POST"])
def admin_login():
    from config import Config
    from core.auth import check_password
    password = request.form.get("password", "").strip()
    if Config.ADMIN_PASSWORD_HASH and check_password(password, Config.ADMIN_PASSWORD_HASH):
        session["is_admin"] = True
        return jsonify({"success": True, "message": "Login successful"})
    return jsonify({"success": False, "message": "Invalid password"})


@printer_bp.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return jsonify({"success": True, "message": "Logout successful"})


@printer_bp.route("/api/admin/get_url")
@admin_required
def admin_get_url():
    return jsonify({"url": get_saved_url()})


@printer_bp.route("/api/admin/update_url", methods=["POST"])
@admin_required
def admin_update_url():
    new_url = request.form.get("url", "").strip()
    if not new_url:
        return jsonify({"success": False, "message": "URL cannot be empty"})
    if save_url(new_url):
        with data_load_lock:
            import modules.printer_search.engine as eng
            eng.df_all_sheets = load_excel_from_url()
        return jsonify({"success": True, "message": "URL updated and data reloaded"})
    return jsonify({"success": False, "message": "Failed to save URL"})


@printer_bp.route("/api/admin/reload_data")
@admin_required
def admin_reload_data():
    with data_load_lock:
        import modules.printer_search.engine as eng
        eng.df_all_sheets = load_excel_from_url()
    if eng.df_all_sheets is not None:
        return jsonify({"success": True, "message": "Data reloaded"})
    return jsonify({"success": False, "message": "Failed to reload"})
```

- [ ] **Step 4: Create templates/printer_search.html**

```html
{% extends "base.html" %}
{% block title %}PCM Compass - Printer Search{% endblock %}
{% block header %}Printer Search{% endblock %}
{% block content %}
<div class="card">
    <h3>Search Printer Data</h3>
    <div class="last-update" id="lastUpdate">
        Data last updated: <span id="lastUpdateTime">Loading...</span>
    </div>
    <div class="search-group">
        <input type="text" id="search-term" placeholder="Hostname, Serial, MAC, or Location" autofocus>
        <button class="btn btn-primary" onclick="performSearch()">Search</button>
    </div>
    <p style="font-size:12px;color:#999;">Data auto-refreshes every 60 seconds</p>
</div>

<div class="card" id="resultsCard" style="display:none;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Results</h3>
        <span id="resultsCount"></span>
    </div>
    <div id="resultsContent" style="overflow-x:auto;"></div>
</div>

<script>
const columnOrder = [
    "Printer Hostname", "Make and Model", "Serial", "MAC", "Location", "Contact Person",
    "ITHELP/SR Ref No.", "PaperCut ready", "Card Reader needed", "Card Reader Fix",
    "Android Fix", "PaperCut sticker", "Status", "Date Completed", "Notes"
];

document.addEventListener('DOMContentLoaded', () => {
    updateLastUpdateTime();
    setInterval(updateLastUpdateTime, 30000);
    const urlQ = new URLSearchParams(window.location.search).get('q');
    if (urlQ) {
        document.getElementById('search-term').value = urlQ;
        performSearch();
    }
    document.getElementById('search-term').addEventListener('keypress', e => {
        if (e.key === 'Enter') performSearch();
    });
});

function updateLastUpdateTime() {
    fetch('/api/printer/last-update')
        .then(r => r.json())
        .then(d => {
            document.getElementById('lastUpdateTime').textContent = d.timestamp || 'Never';
        });
}

function performSearch() {
    const term = document.getElementById('search-term').value.trim();
    if (!term) return;
    const rc = document.getElementById('resultsCard');
    const content = document.getElementById('resultsContent');
    const count = document.getElementById('resultsCount');
    rc.style.display = 'block';
    content.innerHTML = '<p style="text-align:center;">Searching...</p>';
    count.textContent = '';

    fetch('/api/printer/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `search_term=${encodeURIComponent(term)}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            content.innerHTML = `<p class="error">${data.error}</p>`;
            count.textContent = '';
            return;
        }
        count.textContent = `${data.length} result${data.length !== 1 ? 's' : ''}`;
        let html = '<table><thead><tr>';
        columnOrder.forEach(c => html += `<th>${c}</th>`);
        html += '</tr></thead><tbody>';
        data.forEach(row => {
            html += '<tr>';
            columnOrder.forEach(c => html += `<td>${row[c] || ''}</td>`);
            html += '</tr>';
        });
        html += '</tbody></table>';
        content.innerHTML = html;
    })
    .catch(err => {
        content.innerHTML = `<p class="error">Error: ${err.message}</p>`;
    });
}
</script>
{% endblock %}
```

- [ ] **Step 5: Verify printer search works**

Run: `python app.py` then open http://localhost:5000/printer-search
Expected: Search form loads, data timestamp shows, search returns results

- [ ] **Step 6: Commit**

```bash
git add modules/printer_search/ templates/printer_search.html
git commit -m "feat: add printer search module with routes and template"
```

---

### Task 4: IDM Lookup Module

**Files:**
- Create: `modules/idm_lookup/__init__.py`, `modules/idm_lookup/routes.py`, `modules/idm_lookup/engine.py`, `templates/idm_lookup.html`

**Interfaces:**
- Consumes: `create_app()` registers `idm_bp`
- Produces: `POST /api/idm/lookup` returns redirect URL

- [ ] **Step 1: Create modules/idm_lookup/engine.py**

```python
IDM_BASE_URL = "https://idm.nwu.ac.za/profileinfo/profileinfo.jsp"


def build_idm_url(user_id: str) -> str:
    user_id = user_id.strip()
    if not user_id:
        return None
    return f"{IDM_BASE_URL}?Menu=Consolidation&USN={user_id}"


def validate_user_id(user_id: str) -> bool:
    return bool(user_id and user_id.strip())
```

- [ ] **Step 2: Create modules/idm_lookup/routes.py**

```python
from flask import Blueprint, request, jsonify
from modules.idm_lookup.engine import build_idm_url, validate_user_id

idm_bp = Blueprint("idm", __name__)


@idm_bp.route("/api/idm/lookup", methods=["POST"])
def lookup():
    user_id = request.form.get("user_id", "").strip()
    if not validate_user_id(user_id):
        return jsonify({"error": "Please enter a user ID."})
    url = build_idm_url(user_id)
    return jsonify({"url": url})
```

- [ ] **Step 3: Create modules/idm_lookup/__init__.py**

```python
# IDM Lookup module
```

- [ ] **Step 4: Create templates/idm_lookup.html**

```html
{% extends "base.html" %}
{% block title %}PCM Compass - IDM Lookup{% endblock %}
{% block header %}IDM User Lookup{% endblock %}
{% block content %}
<div class="card">
    <h3>Look up IDM Profile</h3>
    <p>Enter a user ID to open their IDM profile page.</p>
    <div class="search-group">
        <input type="text" id="userId" placeholder="e.g. 31408362" autofocus>
        <button class="btn btn-primary" onclick="openIDM()">Open Profile</button>
    </div>
    <div id="history" style="margin-top:16px;"></div>
</div>

<script>
document.getElementById('userId').addEventListener('keypress', e => {
    if (e.key === 'Enter') openIDM();
});

function openIDM() {
    const userId = document.getElementById('userId').value.trim();
    if (!userId) return;
    fetch('/api/idm/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `user_id=${encodeURIComponent(userId)}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.url) window.open(data.url, '_blank');
        else alert(data.error);
    });
}
</script>
{% endblock %}
```

- [ ] **Step 5: Verify IDM lookup**

Run: `python app.py` then open http://localhost:5000/idm-lookup
Expected: Enter user ID, click button, opens IDM in new tab

- [ ] **Step 6: Commit**

```bash
git add modules/idm_lookup/ templates/idm_lookup.html
git commit -m "feat: add IDM lookup module with URL construction"
```

---

### Task 5: Grouper Lookup Module

**Files:**
- Create: `modules/grouper/__init__.py`, `modules/grouper/routes.py`, `modules/grouper/engine.py`, `templates/grouper.html`

**Interfaces:**
- Consumes: `create_app()` registers `grouper_bp`
- Produces: `POST /api/grouper/lookup` returns redirect URL

- [ ] **Step 1: Create modules/grouper/engine.py**

```python
GROUPER_BASE_URL = "https://grp.nwu.ac.za/grouper/populateSubjectSummary.do"


def build_grouper_url(user_id: str) -> str:
    user_id = user_id.strip()
    if not user_id:
        return None
    return (
        f"{GROUPER_BASE_URL}"
        f"?id={user_id}"
        f"&typeName=person"
        f"&subjectId={user_id}"
        f"&name={user_id}"
        f"&subjectType=person"
        f"&sourceId=NWUSource0"
    )


def validate_user_id(user_id: str) -> bool:
    return bool(user_id and user_id.strip())
```

- [ ] **Step 2: Create modules/grouper/routes.py**

```python
from flask import Blueprint, request, jsonify
from modules.grouper.engine import build_grouper_url, validate_user_id

grouper_bp = Blueprint("grouper", __name__)


@grouper_bp.route("/api/grouper/lookup", methods=["POST"])
def lookup():
    user_id = request.form.get("user_id", "").strip()
    if not validate_user_id(user_id):
        return jsonify({"error": "Please enter a user ID."})
    url = build_grouper_url(user_id)
    return jsonify({"url": url})
```

- [ ] **Step 3: Create modules/grouper/__init__.py**

```python
# Grouper module
```

- [ ] **Step 4: Create templates/grouper.html**

```html
{% extends "base.html" %}
{% block title %}PCM Compass - Grouper Groups{% endblock %}
{% block header %}Grouper Group Lookup{% endblock %}
{% block content %}
<div class="card">
    <h3>Look up User Groups</h3>
    <p>Enter a user ID to open their Grouper group memberships.</p>
    <div class="search-group">
        <input type="text" id="userId" placeholder="e.g. 31408362" autofocus>
        <button class="btn btn-primary" onclick="openGrouper()">Open Groups</button>
    </div>
</div>

<script>
document.getElementById('userId').addEventListener('keypress', e => {
    if (e.key === 'Enter') openGrouper();
});

function openGrouper() {
    const userId = document.getElementById('userId').value.trim();
    if (!userId) return;
    fetch('/api/grouper/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `user_id=${encodeURIComponent(userId)}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.url) window.open(data.url, '_blank');
        else alert(data.error);
    });
}
</script>
{% endblock %}
```

- [ ] **Step 5: Verify Grouper lookup**

Run: `python app.py` then open http://localhost:5000/grouper
Expected: Enter user ID, click button, opens Grouper in new tab

- [ ] **Step 6: Commit**

```bash
git add modules/grouper/ templates/grouper.html
git commit -m "feat: add Grouper lookup module with URL construction"
```

---

### Task 6: Quick Links Module

**Files:**
- Create: `modules/quick_links/__init__.py`, `modules/quick_links/routes.py`, `modules/quick_links/engine.py`, `templates/quick_links.html`

**Interfaces:**
- Consumes: `create_app()` registers `links_bp`
- Produces: `GET /api/links`, `POST /api/links`, `DELETE /api/links/<id>`

- [ ] **Step 1: Create modules/quick_links/engine.py**

```python
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
```

- [ ] **Step 2: Create modules/quick_links/routes.py**

```python
from flask import Blueprint, request, jsonify
from modules.quick_links.engine import get_links, add_link, remove_link
from core.auth import admin_required

links_bp = Blueprint("links", __name__)


@links_bp.route("/api/links")
def list_links():
    return jsonify(get_links())


@links_bp.route("/api/links", methods=["POST"])
@admin_required
def create_link():
    data = request.get_json()
    name = data.get("name", "").strip()
    url = data.get("url", "").strip()
    icon = data.get("icon", "🔗").strip()
    if not name or not url:
        return jsonify({"error": "Name and URL required"}), 400
    return jsonify(add_link(name, url, icon)), 201


@links_bp.route("/api/links/<link_id>", methods=["DELETE"])
@admin_required
def delete_link(link_id):
    remove_link(link_id)
    return jsonify({"success": True})
```

- [ ] **Step 3: Create modules/quick_links/__init__.py**

```python
# Quick Links module
```

- [ ] **Step 4: Create templates/quick_links.html**

```html
{% extends "base.html" %}
{% block title %}PCM Compass - Quick Links{% endblock %}
{% block header %}Quick Links{% endblock %}
{% block content %}
<div class="card">
    <h3>Quick Links</h3>
    <div id="linksGrid" class="dashboard-grid"></div>
</div>

<div class="card" id="adminSection" style="display:none;">
    <h3>Add New Link</h3>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <input type="text" id="linkName" placeholder="Name" style="flex:1;min-width:120px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <input type="text" id="linkUrl" placeholder="URL" style="flex:2;min-width:200px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <input type="text" id="linkIcon" placeholder="Icon (emoji)" style="width:80px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <button class="btn btn-primary" onclick="addLink()">Add</button>
    </div>
</div>

<script>
let isAdmin = false;

document.addEventListener('DOMContentLoaded', () => {
    loadLinks();
    checkAdmin();
});

function checkAdmin() {
    fetch('/api/admin/status').then(r => r.json()).then(d => {
        isAdmin = d.is_admin;
        document.getElementById('adminSection').style.display = isAdmin ? 'block' : 'none';
    });
}

function loadLinks() {
    fetch('/api/links').then(r => r.json()).then(links => {
        const grid = document.getElementById('linksGrid');
        grid.innerHTML = links.map(l => `
            <a href="${l.url}" target="_blank" class="dashboard-card" style="text-align:center;">
                <div class="card-icon">${l.icon}</div>
                <h3>${l.name}</h3>
                ${isAdmin ? `<button onclick="event.preventDefault();deleteLink('${l.id}')" style="margin-top:8px;padding:4px 8px;font-size:11px;background:#dc3545;color:white;border:none;border-radius:4px;cursor:pointer;">Remove</button>` : ''}
            </a>
        `).join('');
    });
}

function addLink() {
    const name = document.getElementById('linkName').value.trim();
    const url = document.getElementById('linkUrl').value.trim();
    const icon = document.getElementById('linkIcon').value.trim() || '🔗';
    if (!name || !url) return;
    fetch('/api/links', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, url, icon })
    }).then(() => {
        document.getElementById('linkName').value = '';
        document.getElementById('linkUrl').value = '';
        document.getElementById('linkIcon').value = '';
        loadLinks();
    });
}

function deleteLink(id) {
    fetch(`/api/links/${id}`, { method: 'DELETE' }).then(() => loadLinks());
}
</script>
{% endblock %}
```

- [ ] **Step 5: Verify quick links**

Run: `python app.py` then open http://localhost:5000/quick-links
Expected: Default links displayed, admin can add/remove

- [ ] **Step 6: Commit**

```bash
git add modules/quick_links/ templates/quick_links.html
git commit -m "feat: add quick links module with JSON storage"
```

---

### Task 7: Chrome Extension Redesign

**Files:**
- Modify: `browser_extension/manifest.json`, `browser_extension/popup.html`, `browser_extension/popup.css`, `browser_extension/popup.js`
- Create: `browser_extension/settings.html`, `browser_extension/settings.js`

**Interfaces:**
- Consumes: Flask API endpoints from Tasks 1-6
- Produces: Popup with Printer Search, User Lookup (IDM + Grouper), Quick Links

- [ ] **Step 1: Rewrite manifest.json**

```json
{
  "manifest_version": 3,
  "name": "PCM Compass",
  "version": "2.0.0",
  "description": "Quick access to NWU PCM IT Service Desk tools",
  "author": "PCM IT Service Desk",
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icon16.png",
      "48": "icon48.png",
      "128": "icon128.png"
    }
  },
  "permissions": ["tabs", "activeTab", "storage"],
  "host_permissions": [
    "*://*.nwu.ac.za/*",
    "http://localhost:5000/*",
    "http://196.252.43.75:5000/*"
  ],
  "options_page": "settings.html",
  "icons": {
    "16": "icon16.png",
    "48": "icon48.png",
    "128": "icon128.png"
  }
}
```

- [ ] **Step 2: Rewrite popup.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="popup.css">
</head>
<body>
    <div class="popup">
        <div class="header">
            <h1>PCM Compass</h1>
            <button id="settingsBtn" class="icon-btn" title="Settings">⚙️</button>
        </div>

        <!-- Printer Search -->
        <section class="tool-section">
            <h2>🖨️ Printer Search</h2>
            <div class="input-row">
                <input type="text" id="printerInput" placeholder="Hostname, serial, or MAC" list="printer-history">
                <datalist id="printer-history"></datalist>
            </div>
            <div class="button-row">
                <button id="printerSearchBtn" class="btn primary">Search</button>
                <button id="printerOpenBtn" class="btn secondary">Open App</button>
            </div>
        </section>

        <hr>

        <!-- User Lookup -->
        <section class="tool-section">
            <h2>👤 User Lookup</h2>
            <div class="input-row">
                <input type="text" id="userIdInput" placeholder="User ID (e.g. 31408362)" list="user-history">
                <datalist id="user-history"></datalist>
            </div>
            <div class="button-row">
                <button id="idmBtn" class="btn primary">IDM Profile</button>
                <button id="grouperBtn" class="btn primary">Grouper Groups</button>
            </div>
        </section>

        <hr>

        <!-- Quick Links -->
        <section class="tool-section">
            <h2>🔗 Quick Links</h2>
            <div id="quickLinks" class="links-grid"></div>
        </section>
    </div>
    <script src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 3: Rewrite popup.css**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { width: 360px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

.popup { padding: 16px; }

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 2px solid #006633;
}
.header h1 { font-size: 16px; color: #006633; }
.icon-btn { background: none; border: none; cursor: pointer; font-size: 18px; }

.tool-section { margin-bottom: 12px; }
.tool-section h2 { font-size: 13px; color: #555; margin-bottom: 8px; }

.input-row { margin-bottom: 8px; }
.input-row input {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 13px;
}
.input-row input:focus { outline: none; border-color: #006633; }

.button-row { display: flex; gap: 6px; }

.btn {
    padding: 7px 14px;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    flex: 1;
}
.btn.primary { background: #006633; color: white; }
.btn.primary:hover { background: #4a8c6f; }
.btn.secondary { background: #e9ecef; color: #333; }
.btn.secondary:hover { background: #dee2e6; }

hr { border: none; border-top: 1px solid #eee; margin: 8px 0; }

.links-grid { display: flex; gap: 6px; flex-wrap: wrap; }
.links-grid a {
    padding: 6px 10px;
    background: #f0f2f5;
    border-radius: 4px;
    text-decoration: none;
    color: #333;
    font-size: 12px;
}
.links-grid a:hover { background: #e0e0e0; }
```

- [ ] **Step 4: Rewrite popup.js**

```javascript
const DEFAULT_APP_URL = 'http://196.252.43.75:5000';
const STORAGE_KEYS = { printer: 'printer_history', userId: 'userId_history' };
const MAX_HISTORY = 10;

function getAppUrl() { return localStorage.getItem('app_url') || DEFAULT_APP_URL; }

function loadHistory(key) {
    try { return JSON.parse(localStorage.getItem(key)) || []; } catch { return []; }
}

function saveHistory(key, value) {
    if (!value) return;
    let history = loadHistory(key).filter(v => v !== value);
    history.unshift(value);
    history = history.slice(0, MAX_HISTORY);
    localStorage.setItem(key, JSON.stringify(history));
}

function populateDatalist(id, key) {
    const dl = document.getElementById(id);
    dl.innerHTML = '';
    loadHistory(key).forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        dl.appendChild(opt);
    });
}

// Printer Search
document.getElementById('printerSearchBtn').addEventListener('click', () => {
    const v = document.getElementById('printerInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.printer, v);
    chrome.tabs.create({ url: `${getAppUrl()}/printer-search?q=${encodeURIComponent(v)}` });
});

document.getElementById('printerOpenBtn').addEventListener('click', () => {
    chrome.tabs.create({ url: `${getAppUrl()}/printer-search` });
});

// User Lookup - IDM
document.getElementById('idmBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    chrome.tabs.create({ url: `https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Consolidation&USN=${encodeURIComponent(v)}` });
});

// User Lookup - Grouper
document.getElementById('grouperBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    chrome.tabs.create({
        url: `https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?id=${encodeURIComponent(v)}&typeName=person&subjectId=${encodeURIComponent(v)}&name=${encodeURIComponent(v)}&subjectType=person&sourceId=NWUSource0`
    });
});

// Quick Links
async function loadQuickLinks() {
    try {
        const res = await fetch(`${getAppUrl()}/api/links`);
        const links = await res.json();
        const grid = document.getElementById('quickLinks');
        grid.innerHTML = links.map(l => `<a href="${l.url}" target="_blank">${l.icon} ${l.name}</a>`).join('');
    } catch {
        document.getElementById('quickLinks').innerHTML = '<span style="color:#999;font-size:12px;">Could not load links</span>';
    }
}

// Enter key handlers
document.getElementById('printerInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') document.getElementById('printerSearchBtn').click();
});
document.getElementById('userIdInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') document.getElementById('idmBtn').click();
});

// Settings
document.getElementById('settingsBtn').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
});

// Init
document.addEventListener('DOMContentLoaded', () => {
    populateDatalist('printer-history', STORAGE_KEYS.printer);
    populateDatalist('user-history', STORAGE_KEYS.userId);
    loadQuickLinks();
});
```

- [ ] **Step 5: Create settings.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PCM Compass Settings</title>
    <style>
        body { font-family: sans-serif; max-width: 500px; margin: 40px auto; padding: 20px; }
        h1 { color: #006633; margin-bottom: 20px; }
        label { display: block; margin-top: 16px; font-weight: 600; }
        input { width: 100%; padding: 8px; margin-top: 4px; border: 1px solid #ddd; border-radius: 4px; }
        button { margin-top: 16px; padding: 8px 16px; background: #006633; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .status { margin-top: 12px; padding: 8px; border-radius: 4px; }
        .success { background: #d4edda; color: #155724; }
    </style>
</head>
<body>
    <h1>PCM Compass Settings</h1>
    <label>Flask App URL</label>
    <input type="text" id="appUrl" placeholder="http://localhost:5000">
    <button id="saveBtn">Save</button>
    <div id="status"></div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            chrome.storage.local.get('app_url', data => {
                document.getElementById('appUrl').value = data.app_url || 'http://196.252.43.75:5000';
            });
        });
        document.getElementById('saveBtn').addEventListener('click', () => {
            const url = document.getElementById('appUrl').value.trim().replace(/\/$/, '');
            chrome.storage.local.set({ app_url: url }, () => {
                const s = document.getElementById('status');
                s.textContent = 'Saved!';
                s.className = 'status success';
            });
        });
    </script>
</body>
</html>
```

- [ ] **Step 6: Update popup.js to use chrome.storage for app URL**

Replace the `getAppUrl` function in popup.js:

```javascript
function getAppUrl() {
    return new Promise(resolve => {
        chrome.storage.local.get('app_url', data => {
            resolve(data.app_url || DEFAULT_APP_URL);
        });
    });
}
```

Update the click handlers to use async/await with `getAppUrl()`.

- [ ] **Step 7: Commit extension changes**

```bash
git add browser_extension/
git commit -m "feat: redesign Chrome extension with tool sections and settings"
```

---

### Task 8: Polish, Docker, & Final Cleanup

**Files:**
- Modify: `Dockerfile`, `AGENTS.md`, `CHANGELOG.md`
- Verify: all modules, extension, Docker build

**Interfaces:**
- Consumes: all previous tasks
- Produces: working Docker build, updated docs

- [ ] **Step 1: Update Dockerfile**

```dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/usr/local -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
RUN pip install --no-cache-dir --upgrade --force-reinstall numpy pandas

COPY app.py config.py ./
COPY core/ ./core/
COPY modules/ ./modules/
COPY templates/ ./templates/
COPY static/ ./static/
COPY .env.example .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
```

- [ ] **Step 2: Update AGENTS.md**

Update the project name, run commands, and structure docs.

- [ ] **Step 3: Update CHANGELOG.md**

Add entries for all new modules and the rename.

- [ ] **Step 4: Build and test Docker**

Run: `docker compose build && docker compose up -d`
Expected: App starts on port 5000, all pages load, search works

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: update Dockerfile, docs, and changelog for PCM Compass"
```
