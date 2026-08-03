# User Lookup Module Consolidation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge IDM Lookup and Grouper into a single "User Lookup" module that simply opens the actual IDM/Grouper pages in new tabs with the user ID pre-filled in the URL. No authenticated proxy — just URL construction and redirect.

**Architecture:** The extension popup has a single user ID input. Three buttons: IDM Consolidation, IDM Password, and Grouper. Each button constructs the appropriate URL and opens it in a new tab. The Flask backend provides a simple API to generate these URLs (for the web UI), but the extension can also construct them directly.

**Tech Stack:** Python 3.11, Flask, Chrome Extension MV3, vanilla JS

## Global Constraints

- Python 3.11, Flask 2.x, Chrome Extension MV3
- NWU green branding: `#006633` primary, `#4a8c6f` secondary
- No external JS frameworks — vanilla JS only
- Extension must work offline (URL construction doesn't need network)

## URLs

- **Grouper:** `https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id={userId}&typeName=person&returnTo=%2FdoSearchSubjects.do&subjectId={userId}&name={userId}&subjectType=person&sourceId=NWUSource`
- **IDM Consolidation:** `https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Consolidation&USN={userId}`
- **IDM Password:** `https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Pwd&USN={userId}`

## File Changes

### Files to Create
- `modules/user_lookup/__init__.py` — Blueprint registration
- `modules/user_lookup/urls.py` — URL construction functions
- `modules/user_lookup/routes.py` — `/api/user-lookup/urls` API endpoint
- `templates/user_lookup.html` — Web UI with user ID input + 3 buttons

### Files to Modify
- `app.py` — Register user_lookup blueprint, remove idm_lookup and grouper blueprints
- `templates/base.html` — Update nav: replace "IDM Lookup" and "Grouper" with "User Lookup"
- `templates/dashboard.html` — Update card: replace IDM + Grouper cards with single "User Lookup" card
- `browser_extension/popup.html` — Replace IDM + Grouper sections with single User Lookup section
- `browser_extension/popup.js` — Replace proxyLookup with direct URL construction + tab open

### Files to Delete
- `modules/idm_lookup/` — entire directory (engine.py, routes.py, __init__.py, __pycache__)
- `modules/grouper/` — entire directory (engine.py, routes.py, __init__.py, __pycache__)
- `templates/idm_lookup.html` — replaced by user_lookup.html
- `templates/grouper.html` — replaced by user_lookup.html
- `core/auth.py` — no longer needed (no credential encryption)
- `core/http_client.py` — no longer needed (no HTTP proxy)
- `browser_extension/settings.html` — no longer needed (no credentials to store)

### Files to Keep (unchanged)
- `core/__init__.py`
- `modules/printer_search/` — untouched
- `modules/quick_links/` — untouched
- `static/css/compass.css` — may need minor additions
- `static/js/compass.js` — untouched

---

## Tasks

### Task 1: Create user_lookup module — URL builder

**Files:**
- Create: `modules/user_lookup/__init__.py`
- Create: `modules/user_lookup/urls.py`

**Interfaces:**
- Produces: `build_idm_consolidation_url(user_id) -> str`, `build_idm_password_url(user_id) -> str`, `build_grouper_url(user_id) -> str`

- [ ] **Step 1: Create `modules/user_lookup/__init__.py`**

```python
from flask import Blueprint

bp = Blueprint('user_lookup', __name__)

from modules.user_lookup import routes  # noqa: E402, F401
```

- [ ] **Step 2: Create `modules/user_lookup/urls.py`**

```python
from urllib.parse import quote

IDM_BASE = 'https://idm.nwu.ac.za/profileinfo/profileinfo.jsp'
GROUPER_BASE = 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do'


def build_idm_consolidation_url(user_id: str) -> str:
    return f'{IDM_BASE}?Menu=Consolidation&USN={quote(user_id, safe="")}'


def build_idm_password_url(user_id: str) -> str:
    return f'{IDM_BASE}?Menu=Pwd&USN={quote(user_id, safe="")}'


def build_grouper_url(user_id: str) -> str:
    params = (
        f'returnToLinkKey=subject.action.return-results'
        f'&id={quote(user_id, safe="")}'
        f'&typeName=person'
        f'&returnTo=%2FdoSearchSubjects.do'
        f'&subjectId={quote(user_id, safe="")}'
        f'&name={quote(user_id, safe="")}'
        f'&subjectType=person'
        f'&sourceId=NWUSource'
    )
    return f'{GROUPER_BASE}?{params}'
```

- [ ] **Step 3: Verify URL construction**

Run: `python3 -c "from modules.user_lookup.urls import *; print(build_idm_consolidation_url('31408362')); print(build_idm_password_url('31408362')); print(build_grouper_url('31408362'))"`

Expected output:
```
https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Consolidation&USN=31408362
https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Pwd&USN=31408362
https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=31408362&typeName=person&returnTo=%2FdoSearchSubjects.do&subjectId=31408362&name=31408362&subjectType=person&sourceId=NWUSource
```

- [ ] **Step 4: Commit**

```bash
git add modules/user_lookup/
git commit -m "feat: add user_lookup URL builder module"
```

---

### Task 2: Create user_lookup API route

**Files:**
- Create: `modules/user_lookup/routes.py`

**Interfaces:**
- Consumes: `build_idm_consolidation_url`, `build_idm_password_url`, `build_grouper_url` from urls.py
- Produces: `GET /api/user-lookup/urls?user_id=XXX` returning JSON with 3 URLs

- [ ] **Step 1: Create `modules/user_lookup/routes.py`**

```python
from flask import request, jsonify
from modules.user_lookup import bp
from modules.user_lookup.urls import (
    build_idm_consolidation_url,
    build_idm_password_url,
    build_grouper_url,
)


@bp.route('/api/user-lookup/urls', methods=['GET'])
def get_urls():
    user_id = request.args.get('user_id', '').strip()
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    return jsonify({
        'user_id': user_id,
        'urls': {
            'idm_consolidation': build_idm_consolidation_url(user_id),
            'idm_password': build_idm_password_url(user_id),
            'grouper': build_grouper_url(user_id),
        }
    })
```

- [ ] **Step 2: Test the API endpoint**

Run: `python3 -c "
from app import create_app
app = create_app()
with app.test_client() as c:
    r = c.get('/api/user-lookup/urls?user_id=31408362')
    import json
    print(json.dumps(r.get_json(), indent=2))
"`

Expected: JSON with 3 correctly formed URLs.

- [ ] **Step 3: Commit**

```bash
git add modules/user_lookup/routes.py
git commit -m "feat: add user_lookup API endpoint"
```

---

### Task 3: Register blueprint in app.py

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `bp` from `modules.user_lookup`
- Produces: Blueprint registered, old blueprints removed

- [ ] **Step 1: Read current app.py**

Read `app.py` to see the current blueprint registrations.

- [ ] **Step 2: Update blueprint imports and registrations**

Replace the idm_lookup and grouper imports/registrations with user_lookup:

```python
from modules.user_lookup import bp as user_lookup_bp
app.register_blueprint(user_lookup_bp)
```

Remove:
```python
from modules.idm_lookup import bp as idm_lookup_bp
from modules.grouper import bp as grouper_bp
app.register_blueprint(idm_lookup_bp)
app.register_blueprint(grouper_bp)
```

- [ ] **Step 3: Verify app starts**

Run: `python3 -c "from app import create_app; app = create_app(); print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: register user_lookup blueprint, remove idm_lookup and grouper"
```

---

### Task 4: Create user_lookup web template

**Files:**
- Create: `templates/user_lookup.html`

**Interfaces:**
- Consumes: `GET /api/user-lookup/urls?user_id=XXX` returns JSON with URLs
- Produces: HTML page with user ID input and 3 redirect buttons

- [ ] **Step 1: Create `templates/user_lookup.html`**

```html
{% extends "base.html" %}
{% block title %}PCM Compass - User Lookup{% endblock %}
{% block header %}User Lookup{% endblock %}
{% block content %}
<div class="card">
    <h2>User Lookup</h2>
    <p>Enter a user ID to open their IDM or Grouper profile in a new tab.</p>

    <div class="form-group">
        <label for="userId">NWU User ID</label>
        <input type="text" id="userId" placeholder="e.g. 31408362" autofocus>
    </div>

    <div class="button-group">
        <button class="btn btn-primary" onclick="openLookup('idm_consolidation')">
            IDM Consolidation
        </button>
        <button class="btn btn-primary" onclick="openLookup('idm_password')">
            IDM Password
        </button>
        <button class="btn btn-primary" onclick="openLookup('grouper')">
            Grouper Groups
        </button>
    </div>
</div>

<script>
async function openLookup(type) {
    const userId = document.getElementById('userId').value.trim();
    if (!userId) {
        alert('Please enter a user ID');
        return;
    }

    try {
        const resp = await fetch(`/api/user-lookup/urls?user_id=${encodeURIComponent(userId)}`);
        const data = await resp.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        const url = data.urls[type];
        if (url) {
            window.open(url, '_blank');
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

document.getElementById('userId').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') openLookup('idm_consolidation');
});
</script>
{% endblock %}
```

- [ ] **Step 2: Add page route**

Add to `templates/routes.py` (or wherever page routes are defined):

```python
@bp.route('/user-lookup')
def user_lookup():
    return render_template('user_lookup.html')
```

- [ ] **Step 3: Commit**

```bash
git add templates/user_lookup.html templates/routes.py
git commit -m "feat: add user_lookup web template and route"
```

---

### Task 5: Update dashboard and nav

**Files:**
- Modify: `templates/base.html`
- Modify: `templates/dashboard.html`

**Interfaces:**
- Consumes: None
- Produces: Updated nav and dashboard with single "User Lookup" entry

- [ ] **Step 1: Update `templates/base.html` nav**

Replace the separate "IDM Lookup" and "Grouper" nav items with a single "User Lookup" entry.

- [ ] **Step 2: Update `templates/dashboard.html`**

Replace the two cards (IDM Lookup + Grouper Groups) with a single "User Lookup" card:

```html
<a href="/user-lookup" class="dashboard-card">
    <div class="card-icon">👤</div>
    <h3>User Lookup</h3>
    <p>Open IDM or Grouper profiles for any user.</p>
</a>
```

- [ ] **Step 3: Commit**

```bash
git add templates/base.html templates/dashboard.html
git commit -m "feat: update dashboard and nav with single User Lookup entry"
```

---

### Task 6: Update extension popup — single User Lookup section

**Files:**
- Modify: `browser_extension/popup.html`
- Modify: `browser_extension/popup.js`

**Interfaces:**
- Consumes: None (extension constructs URLs directly)
- Produces: Popup with single user ID input + 3 buttons that open tabs

- [ ] **Step 1: Update `browser_extension/popup.html`**

Replace the separate IDM and Grouper sections with a single User Lookup section:

```html
<div class="section">
    <div class="section-header">
        <span>👤 User Lookup</span>
    </div>
    <div class="input-row">
        <input type="text" id="userIdInput" placeholder="NWU User ID" list="user-history">
        <datalist id="user-history"></datalist>
    </div>
    <div class="button-row">
        <button id="idmConsolidationBtn" class="btn-idm">IDM Consolidation</button>
        <button id="idmPasswordBtn" class="btn-idm">IDM Password</button>
        <button id="grouperBtn" class="btn-grouper">Grouper</button>
    </div>
</div>
```

- [ ] **Step 2: Update `browser_extension/popup.js`**

Replace the proxyLookup logic with direct URL construction:

```javascript
const IDM_BASE = 'https://idm.nwu.ac.za/profileinfo/profileinfo.jsp';
const GROUPER_BASE = 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do';

function buildIDMConsolidationURL(userId) {
    return `${IDM_BASE}?Menu=Consolidation&USN=${encodeURIComponent(userId)}`;
}

function buildIDMPasswordURL(userId) {
    return `${IDM_BASE}?Menu=Pwd&USN=${encodeURIComponent(userId)}`;
}

function buildGrouperURL(userId) {
    const params = new URLSearchParams({
        returnToLinkKey: 'subject.action.return-results',
        id: userId,
        typeName: 'person',
        returnTo: '/doSearchSubjects.do',
        subjectId: userId,
        name: userId,
        subjectType: 'person',
        sourceId: 'NWUSource'
    });
    return `${GROUPER_BASE}?${params.toString()}`;
}

// Button handlers
document.getElementById('idmConsolidationBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    chrome.tabs.create({ url: buildIDMConsolidationURL(v) });
});

document.getElementById('idmPasswordBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    chrome.tabs.create({ url: buildIDMPasswordURL(v) });
});

document.getElementById('grouperBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    chrome.tabs.create({ url: buildGrouperURL(v) });
});
```

Remove all proxy-related functions: `getCreds`, `decryptPassword`, `askForPin`, `proxyLookup`, `renderResultTab`, `waitForTabLoad`, `sendMessageToTab`.

- [ ] **Step 3: Commit**

```bash
git add browser_extension/popup.html browser_extension/popup.js
git commit -m "feat: update extension popup with direct URL construction"
```

---

### Task 7: Delete old modules and auth files

**Files:**
- Delete: `modules/idm_lookup/` (entire directory)
- Delete: `modules/grouper/` (entire directory)
- Delete: `templates/idm_lookup.html`
- Delete: `templates/grouper.html`
- Delete: `core/auth.py`
- Delete: `core/http_client.py`
- Delete: `browser_extension/settings.html`

**Interfaces:**
- None — these are removals

- [ ] **Step 1: Delete old modules**

```bash
rm -rf modules/idm_lookup/
rm -rf modules/grouper/
rm templates/idm_lookup.html
rm templates/grouper.html
rm core/auth.py
rm core/http_client.py
rm browser_extension/settings.html
```

- [ ] **Step 2: Update requirements.txt**

Remove `cryptography>=41.0,<42.0` (was only needed for AES-GCM credential encryption).

- [ ] **Step 3: Update manifest.json**

Remove `options_page` line (no settings page needed).

- [ ] **Step 4: Verify app starts**

Run: `python3 -c "from app import create_app; app = create_app(); print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: remove old idm_lookup, grouper, auth modules"
```

---

### Task 8: Update CHANGELOG and cleanup

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `tailnet-changelog/CHANGELOG.md`

- [ ] **Step 1: Update CHANGELOG.md**

Add entry under `[Unreleased]`:
```
- 2026-07-20: Consolidated IDM Lookup and Grouper into single User Lookup module — opens actual IDM/Grouper pages in new tabs with user ID pre-filled
- 2026-07-20: Removed authenticated proxy approach — no longer need Flask to authenticate to IDM/Grouper
- 2026-07-20: Removed AES-GCM credential encryption (core/auth.py) — no credentials to store
```

- [ ] **Step 2: Update tailnet-changelog**

Add one-line summary to `~/projects/tailnet-changelog/CHANGELOG.md`.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update changelog for user_lookup consolidation"
```

---

## Verification

After all tasks:

1. Run: `python3 -c "from app import create_app; app = create_app(); print('OK')"`
2. Open browser to `http://localhost:5000/user-lookup`
3. Enter `31408362` and click each button — verify correct URLs open
4. Load extension in Chrome — verify 3 buttons open correct tabs
5. Verify printer search and quick links still work
