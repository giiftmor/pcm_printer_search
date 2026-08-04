# Grouper Group Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one-click open for 7 preset Grouper groups plus free-text manual group lookup to both the Flask web UI and the Chrome extension popup, using Grouper's `populateSubjectSummary.do` endpoint with `typeName=group` / `sourceId=g:gsa` (group stem path only, no UUID).

**Architecture:** Extend the existing `user_lookup` module (Python URL builders in `modules/user_lookup/urls.py`, blueprint in `modules/user_lookup/routes.py`) with a group URL builder, preset list, and two JSON endpoints. Mirror the builder + presets in `browser_extension/url_helpers.js` (kept in sync, same pattern as `svcp.py` ↔ `url_helpers.js`). Add a second "Grouper Groups" card to `/user-lookup` and a new popup section; reuse the existing `findOrCreateTab` Grouper tab-reuse matcher. Bump extension to 2.3.0.

**Tech Stack:** Python 3.11, Flask 2.x (pytest via Docker `pcm-test` image), vanilla JS (node v18 `node --test`), Chrome MV3.

## Global Constraints

- Host has NO usable local Python — all pytest runs via: `docker run --rm -v "$PWD":/app -w /app -v pcm-test-vol:/root/.cache/pip pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q"`. Always `-p no:cacheprovider` (prevents root-owned `.pytest_cache` on host volume).
- node v18 on host: `node --test tests/url_helpers.test.js`.
- Group URL builder rules (from spec): trim group name; reject empty/whitespace/null; URL-encode ALL param values (`:` → `%3A`, space → `%20`); `description` optional, omitted when falsy. No UUID. Existing person builders unchanged.
- The Python and JS group builders MUST produce byte-identical URLs for the same input (JS: `URLSearchParams(...).toString().replace(/\+/g, '%20')` to match Python `urllib.parse.quote`).
- Presets (7): id / label / name — the exact table in the spec:
  - `papercut-staff` / `Papercut Staff Include` / `Papercut_pcm_staff_include`
  - `azure-staff` / `Azure Staff` / `nwu:groups:Azure:Azure_Include_Staff`
  - `ms-full-staff` / `MS Full Staff License` / `nwu:groups:mslicenses:msfed_include_full_staff_license`
  - `ms-activate` / `MS Activate` / `nwu:groups:mslicenses:ms_activate`
  - `azure-students` / `Azure Students` / `nwu:groups:Azure:Azure_Include_Students`
  - `acrobat` / `Acrobat` / `nwu:groups:Adobe:Acrobat_fedID_users`
  - `acrobat-include` / `Acrobat Include` / `nwu:groups:Adobe:Acrobat_fedID_users_include`
- Vanilla JS only, no frameworks; NWU green `#006633`/`#4a8c6f`; no new secrets; no credentials stored.
- AGENTS.md: update CHANGELOG.md on every task completion; also add one-line summary to `~/projects/tailnet-changelog/CHANGELOG.md` (that path does not exist on this host — skip, note it).

---
## Task 1: Python group URL builder + preset list

**Files:**
- Modify: `modules/user_lookup/urls.py`
- Test: `tests/test_grouper_groups.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `GROUPER_GROUP_PRESETS` — list of dicts `{"id": str, "label": str, "name": str}` (exact 7 entries from Global Constraints)
  - `build_grouper_group_url(group_name: str, description: str | None = None) -> str | None` — returns URL or `None` on empty/whitespace input

- [ ] **Step 1: Write the failing test**

Create `tests/test_grouper_groups.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker run --rm -v "$PWD":/app -w /app -v pcm-test-vol:/root/.cache/pip pcm-test bash -c "pip install -q pytest && python -m pytest tests/test_grouper_groups.py -p no:cacheprovider -q"`
Expected: FAIL — `ImportError: cannot import name 'build_grouper_group_url'`

- [ ] **Step 3: Implement** in `modules/user_lookup/urls.py`

Append below the existing `build_grouper_url`:

```python
GROUPER_GROUP_BASE = 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do'

GROUPER_GROUP_PRESETS = [
    {"id": "papercut-staff", "label": "Papercut Staff Include", "name": "Papercut_pcm_staff_include"},
    {"id": "azure-staff", "label": "Azure Staff", "name": "nwu:groups:Azure:Azure_Include_Staff"},
    {"id": "ms-full-staff", "label": "MS Full Staff License", "name": "nwu:groups:mslicenses:msfed_include_full_staff_license"},
    {"id": "ms-activate", "label": "MS Activate", "name": "nwu:groups:mslicenses:ms_activate"},
    {"id": "azure-students", "label": "Azure Students", "name": "nwu:groups:Azure:Azure_Include_Students"},
    {"id": "acrobat", "label": "Acrobat", "name": "nwu:groups:Adobe:Acrobat_fedID_users"},
    {"id": "acrobat-include", "label": "Acrobat Include", "name": "nwu:groups:Adobe:Acrobat_fedID_users_include"},
]


def build_grouper_group_url(group_name: str, description: str | None = None) -> str | None:
    name = (group_name or "").strip()
    if not name:
        return None
    params = [
        ("returnToLinkKey", "subject.action.return-results"),
        ("typeName", "group"),
        ("returnTo", "/doSearchSubjects.do"),
        ("name", name),
        ("subjectType", "group"),
        ("sourceId", "g:gsa"),
    ]
    if description:
        params.append(("description", description))
    qs = "&".join(f"{k}={quote(v, safe='')}" for k, v in params)
    return f"{GROUPER_GROUP_BASE}?{qs}"
```

Note: `quote` is already imported at the top of the file (`from urllib.parse import quote`).

- [ ] **Step 4: Run test to verify it passes**

Run: same command as Step 2.
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add modules/user_lookup/urls.py tests/test_grouper_groups.py
git commit -m "feat: grouper group URL builder and preset list"
```

---
## Task 2: API endpoints

**Files:**
- Modify: `modules/user_lookup/routes.py`
- Test: `tests/test_grouper_groups.py` (append route tests)

**Interfaces:**
- Consumes: `GROUPER_GROUP_PRESETS`, `build_grouper_group_url` from `modules/user_lookup/urls.py`
- Produces:
  - `GET /api/user-lookup/grouper-presets` → `200 {"presets": [{"id","label","name","url"}]}`
  - `GET /api/user-lookup/group-url?name=<stem>` → `200 {"url","name"}` | `400 {"error":"name is required"}`

- [ ] **Step 1: Append failing route tests** to `tests/test_grouper_groups.py`

```python
import pytest
from flask import Flask
from modules.user_lookup import bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(bp)
    return app.test_client()


def test_grouper_presets_endpoint(client):
    resp = client.get("/api/user-lookup/grouper-presets")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["presets"]) == 7
    p = data["presets"][0]
    assert {"id", "label", "name", "url"} <= set(p)
    assert p["url"].startswith("https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?")


def test_group_url_endpoint(client):
    resp = client.get(
        "/api/user-lookup/group-url?name=nwu:groups:Azure:Azure_Include_Staff"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "nwu:groups:Azure:Azure_Include_Staff"
    assert "name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff" in data["url"]


def test_group_url_endpoint_requires_name(client):
    assert client.get("/api/user-lookup/group-url").status_code == 400
    assert client.get("/api/user-lookup/group-url?name=").status_code == 400
    assert client.get("/api/user-lookup/group-url?name=%20%20").status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker run --rm -v "$PWD":/app -w /app -v pcm-test-vol:/root/.cache/pip pcm-test bash -c "pip install -q pytest && python -m pytest tests/test_grouper_groups.py -p no:cacheprovider -q"`
Expected: FAIL — `404 NOT FOUND` (routes don't exist).

- [ ] **Step 3: Implement** in `modules/user_lookup/routes.py`

Update the imports and add two routes:

```python
from modules.user_lookup.urls import (
    GROUPER_GROUP_PRESETS,
    build_grouper_group_url,
    build_idm_consolidation_url,
    build_idm_password_url,
    build_grouper_url,
)
```

```python
@bp.route('/api/user-lookup/grouper-presets', methods=['GET'])
def grouper_presets():
    presets = [
        {**p, 'url': build_grouper_group_url(p['name'])}
        for p in GROUPER_GROUP_PRESETS
    ]
    return jsonify({'presets': presets})


@bp.route('/api/user-lookup/group-url', methods=['GET'])
def grouper_group_url():
    name = request.args.get('name', '').strip()
    url = build_grouper_group_url(name)
    if url is None:
        return jsonify({'error': 'name is required'}), 400
    return jsonify({'url': url, 'name': name})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: same command as Step 2.
Expected: PASS (all 9 tests in the file, 6 unit + 3 route).

- [ ] **Step 5: Commit**

```bash
git add modules/user_lookup/routes.py tests/test_grouper_groups.py
git commit -m "feat: grouper presets and group-url API endpoints"
```

---
## Task 3: Web UI — Grouper Groups card

**Files:**
- Modify: `templates/user_lookup.html`
- Modify: `static/css/compass.css`

**Interfaces:**
- Consumes: `GET /api/user-lookup/grouper-presets`, `GET /api/user-lookup/group-url?name=`
- Produces: fully functional `/user-lookup` page with presets chips + manual group open.

- [ ] **Step 1: Add chip styles** to `static/css/compass.css` (append at end)

```css
.chip-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
}
.chip {
    padding: 6px 14px;
    background: #e8f0eb;
    border: 1px solid #006633;
    border-radius: 16px;
    color: #006633;
    font-size: 13px;
    cursor: pointer;
}
.chip:hover { background: #006633; color: #fff; }
```

- [ ] **Step 2: Rename the person-Grouper button** in `templates/user_lookup.html` (line 20-22)

Change the button text from `Grouper Groups` to `Grouper User` (the `onclick="openLookup('grouper')"` stays).

- [ ] **Step 3: Add the Grouper Groups card** — insert after the existing `.card` closing `</div>` (after line 24), before the `<script>`:

```html
<div class="card">
    <h3>Grouper Groups</h3>
    <p>Open a Grouper group in a new tab, or enter a group path manually.</p>

    <div class="chip-grid" id="grouperChips"></div>

    <div class="search-group">
        <input type="text" id="groupId" placeholder="Group path or name, e.g. nwu:groups:Azure:Azure_Include_Staff">
    </div>

    <div class="search-group">
        <button class="btn btn-primary" onclick="openGrouperGroup()">Open</button>
    </div>
</div>
```

- [ ] **Step 4: Add the JS** in `templates/user_lookup.html` — insert these functions inside the existing `<script>` (after `openLookup`):

```javascript
let grouperPresets = [];

async function loadGrouperPresets() {
    try {
        const resp = await fetch('/api/user-lookup/grouper-presets');
        const data = await resp.json();
        grouperPresets = data.presets || [];
        const grid = document.getElementById('grouperChips');
        grid.innerHTML = grouperPresets.map((p, i) =>
            `<button class="chip" data-idx="${i}">${p.label}</button>`
        ).join('');
        grid.querySelectorAll('.chip').forEach(btn => {
            btn.addEventListener('click', () => openGroupUrl(grouperPresets[btn.dataset.idx].url));
        });
    } catch (err) {
        console.error('Failed to load Grouper presets:', err);
    }
}

function openGroupUrl(url) {
    window.open(url, '_blank', 'noopener,noreferrer');
}

async function openGrouperGroup() {
    const name = document.getElementById('groupId').value.trim();
    if (!name) {
        alert('Please enter a group path or name');
        return;
    }
    try {
        const resp = await fetch(`/api/user-lookup/group-url?name=${encodeURIComponent(name)}`);
        const data = await resp.json();
        if (data.error) {
            alert(data.error);
            return;
        }
        openGroupUrl(data.url);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

document.getElementById('groupId').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') openGrouperGroup();
});

loadGrouperPresets();
```

- [ ] **Step 5: Verify structure**

Run: `grep -n "grouperChips\|groupId\|openGrouperGroup\|Grouper User" templates/user_lookup.html`
Expected: all markers present; `Grouper User` appears once.

- [ ] **Step 6: Commit**

```bash
git add templates/user_lookup.html static/css/compass.css
git commit -m "feat: grouper groups card in user lookup web UI"
```

---
## Task 4: Extension JS helper + presets

**Files:**
- Modify: `browser_extension/url_helpers.js`
- Test: `tests/url_helpers.test.js`

**Interfaces:**
- Consumes: nothing new (reuses `GROUPER_BASE` constant already in the file).
- Produces:
  - `PCM_URL_HELPERS.buildGrouperGroupURL(groupName, description?) -> string | null`
  - `PCM_URL_HELPERS.GROUPER_GROUP_PRESETS` — array of `{id, label, name}` (7 entries, same names as Python)

- [ ] **Step 1: Append failing tests** to `tests/url_helpers.test.js`

```javascript
test('buildGrouperGroupURL encodes group name', () => {
    const url = h.buildGrouperGroupURL('nwu:groups:Azure:Azure_Include_Staff');
    assert.ok(url.startsWith('https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?'));
    assert.ok(url.includes('typeName=group'));
    assert.ok(url.includes('sourceId=g%3Agsa'));
    assert.ok(url.includes('name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff'));
});

test('buildGrouperGroupURL optional description', () => {
    const url = h.buildGrouperGroupURL('nwu:groups:Adobe:Acrobat_fedID_users_include', 'Acrobat Include');
    assert.ok(url.includes('description=Acrobat%20Include'));
});

test('buildGrouperGroupURL rejects invalid', () => {
    assert.strictEqual(h.buildGrouperGroupURL(''), null);
    assert.strictEqual(h.buildGrouperGroupURL('   '), null);
    assert.strictEqual(h.buildGrouperGroupURL(null), null);
});

test('GROUPER_GROUP_PRESETS shape', () => {
    assert.strictEqual(h.GROUPER_GROUP_PRESETS.length, 7);
    const names = h.GROUPER_GROUP_PRESETS.map(p => p.name);
    assert.ok(names.includes('nwu:groups:Azure:Azure_Include_Staff'));
    assert.ok(names.includes('Papercut_pcm_staff_include'));
    for (const p of h.GROUPER_GROUP_PRESETS) {
        assert.ok(p.id && p.label && p.name);
    }
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/url_helpers.test.js`
Expected: FAIL — `TypeError: h.buildGrouperGroupURL is not a function` (and `GROUPER_GROUP_PRESETS` undefined).

- [ ] **Step 3: Implement** in `browser_extension/url_helpers.js`

Add the presets constant and builder inside the factory (after `buildSvcpUrl`, before the `return`):

```javascript
    const GROUPER_GROUP_PRESETS = [
        { id: 'papercut-staff', label: 'Papercut Staff Include', name: 'Papercut_pcm_staff_include' },
        { id: 'azure-staff', label: 'Azure Staff', name: 'nwu:groups:Azure:Azure_Include_Staff' },
        { id: 'ms-full-staff', label: 'MS Full Staff License', name: 'nwu:groups:mslicenses:msfed_include_full_staff_license' },
        { id: 'ms-activate', label: 'MS Activate', name: 'nwu:groups:mslicenses:ms_activate' },
        { id: 'azure-students', label: 'Azure Students', name: 'nwu:groups:Azure:Azure_Include_Students' },
        { id: 'acrobat', label: 'Acrobat', name: 'nwu:groups:Adobe:Acrobat_fedID_users' },
        { id: 'acrobat-include', label: 'Acrobat Include', name: 'nwu:groups:Adobe:Acrobat_fedID_users_include' },
    ];

    // keep in sync with modules/user_lookup/urls.py
    function buildGrouperGroupURL(groupName, description) {
        if (typeof groupName !== 'string') return null;
        const name = groupName.trim();
        if (!name) return null;
        const params = new URLSearchParams({
            returnToLinkKey: 'subject.action.return-results',
            typeName: 'group',
            returnTo: '/doSearchSubjects.do',
            name: name,
            subjectType: 'group',
            sourceId: 'g:gsa'
        });
        if (description) params.set('description', description);
        return `${GROUPER_BASE}?${params.toString().replace(/\+/g, '%20')}`;
    }
```

Add both to the returned object:

```javascript
    return {
        buildIDMConsolidationURL: buildIDMConsolidationURL,
        buildIDMPasswordURL: buildIDMPasswordURL,
        buildGrouperURL: buildGrouperURL,
        matchesPrefix: matchesPrefix,
        buildSvcpUrl: buildSvcpUrl,
        buildGrouperGroupURL: buildGrouperGroupURL,
        GROUPER_GROUP_PRESETS: GROUPER_GROUP_PRESETS
    };
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/url_helpers.test.js`
Expected: PASS (10 tests total).

- [ ] **Step 5: Cross-check Python↔JS parity**

Run:
```bash
node -e "const h=require('./browser_extension/url_helpers.js'); console.log(h.buildGrouperGroupURL('nwu:groups:Azure:Azure_Include_Staff'))"
```
Expected output must contain `name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff` and `sourceId=g%3Agsa` (identical encoding to Python's `quote`).

- [ ] **Step 6: Commit**

```bash
git add browser_extension/url_helpers.js tests/url_helpers.test.js
git commit -m "feat: grouper group URL builder and presets in extension"
```

---
## Task 5: Extension popup UI + version bump to 2.3.0

**Files:**
- Modify: `browser_extension/popup.html`
- Modify: `browser_extension/popup.js`
- Modify: `browser_extension/popup.css`
- Modify: `browser_extension/manifest.json` (version → 2.3.0)
- Modify: `tests/test_status_version.py` (expected extension version → 2.3.0)
- Rebuild: `static/dist/pcm-compass-v2.3.0.zip` (via `bin/build-extension.sh`)

**Interfaces:**
- Consumes: `PCM_URL_HELPERS.buildGrouperGroupURL`, `PCM_URL_HELPERS.GROUPER_GROUP_PRESETS`, existing `findOrCreateTab` + `matchesPrefix` tab-reuse.
- Produces: fully functional popup Grouper Groups section; shippable extension 2.3.0.

- [ ] **Step 1: Add popup section** in `browser_extension/popup.html` — insert between the User Lookup `</section>` (line 40) and the Quick Links `<hr>` (line 42):

```html
        <section class="tool-section">
            <h2>Grouper Groups</h2>
            <div id="grouperGroupChips" class="chip-grid"></div>
            <div class="input-row">
                <input type="text" id="groupIdInput" placeholder="Group path or name">
            </div>
            <div class="button-row">
                <button id="grouperGroupOpenBtn" class="btn primary">Open</button>
            </div>
        </section>

        <hr>
```

- [ ] **Step 2: Add chip styles** to `browser_extension/popup.css` (append at end)

```css
.chip-grid { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.chip {
    padding: 4px 8px;
    background: #e8f0eb;
    border: 1px solid #006633;
    border-radius: 12px;
    color: #006633;
    font-size: 11px;
    cursor: pointer;
}
.chip:hover { background: #006633; color: #fff; }
```

- [ ] **Step 3: Wire handlers** in `browser_extension/popup.js`

Add after the `grouperBtn` handler (after line 104):

```javascript
function openGrouperGroup(name) {
    const url = PCM_URL_HELPERS.buildGrouperGroupURL(name);
    if (!url) return;
    findOrCreateTab(url, { hostPattern: '*://grp.nwu.ac.za/*', pathPrefix: '/grouper/' });
}

function renderGrouperGroupChips() {
    const grid = document.getElementById('grouperGroupChips');
    const presets = PCM_URL_HELPERS.GROUPER_GROUP_PRESETS || [];
    grid.innerHTML = presets.map((p, i) =>
        `<button class="chip" data-idx="${i}">${p.label}</button>`
    ).join('');
    grid.querySelectorAll('.chip').forEach(btn => {
        btn.addEventListener('click', () => openGrouperGroup(presets[btn.dataset.idx].name));
    });
}

document.getElementById('grouperGroupOpenBtn').addEventListener('click', () => {
    const v = document.getElementById('groupIdInput').value.trim();
    if (!v) return;
    openGrouperGroup(v);
});

document.getElementById('groupIdInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') document.getElementById('grouperGroupOpenBtn').click();
});
```

Call `renderGrouperGroupChips();` inside the `DOMContentLoaded` handler (after `loadQuickLinks();`).

- [ ] **Step 4: Bump manifest version** in `browser_extension/manifest.json` — `"version": "2.3.0"`

- [ ] **Step 5: Update the version test** in `tests/test_status_version.py` — `assert data["extension_version"] == "2.3.0"`

- [ ] **Step 6: Rebuild + verify the zip**

```bash
bin/build-extension.sh || true
ls -la static/dist/pcm-compass-v2.3.0.zip
unzip -p static/dist/pcm-compass-v2.3.0.zip popup.js | grep -c "openGrouperGroup"
unzip -l static/dist/pcm-compass-v2.3.0.zip | grep -c "test.js"   # expect 0
```
Expected: zip exists, `openGrouperGroup` present, no `*.test.js`. Nextcloud upload may fail offline — acceptable.

- [ ] **Step 7: Run all JS + Python tests**

```bash
node --test tests/url_helpers.test.js
docker run --rm -v "$PWD":/app -w /app -v pcm-test-vol:/root/.cache/pip pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q"
```
Expected: node PASS (10), pytest PASS (40).

- [ ] **Step 8: Commit**

```bash
git add browser_extension/popup.html browser_extension/popup.js browser_extension/popup.css browser_extension/manifest.json tests/test_status_version.py
git commit -m "feat: extension v2.3.0 — grouper groups section in popup"
```

---
## Task 6: Docs + full verification

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `AGENTS.md` (API Endpoints table + module diagram note)
- Modify: `major-improvements-implementation-status.md` (test inventory + progress)

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: repo docs accurate for the feature; full green suite.

- [ ] **Step 1: Update CHANGELOG.md** — add under `[Unreleased]` (Added section, top):

```
- 2026-08-04: Grouper group lookup — 7 preset groups (Papercut staff, Azure staff/students, MS licenses, Acrobat) + free-text group open; Python+JS builders, 2 new API endpoints, web card, extension popup section
```

And under `Changed`:

```
- 2026-08-04: Extension v2.3.0 — Grouper Groups section (preset chips + manual Open); person button renamed to "Grouper User" in web UI
```

- [ ] **Step 2: Update AGENTS.md API Endpoints table** — add two rows:

```
| GET | `/api/user-lookup/grouper-presets` | none | Preset Grouper groups (`{"presets":[{"id","label","name","url"}]}`) |
| GET | `/api/user-lookup/group-url?name=X` | none | Build Grouper group URL for a stem/name |
```

Also update the module diagram line for `user_lookup/` to mention group URL building, and the API docs line for `/api/user-lookup/urls` if it now seems stale (only add accuracy; do not duplicate).

- [ ] **Step 3: Update `major-improvements-implementation-status.md`** — add the new tests to the Stream test inventory (pytest `tests/test_grouper_groups.py` via Docker `pcm-test`, node `buildGrouperGroupURL`/presets cases) and a progress-log row.

- [ ] **Step 4: Full test suite**

```bash
docker run --rm -v "$PWD":/app -w /app -v pcm-test-vol:/root/.cache/pip pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q"
node --test tests/url_helpers.test.js
ls -d .pytest_cache 2>/dev/null || echo "no .pytest_cache (GOOD)"
```
Expected: pytest PASS (40), node PASS (10), no `.pytest_cache` on host.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md AGENTS.md major-improvements-implementation-status.md
git commit -m "docs: changelog and AGENTS.md for grouper group lookup"
```
