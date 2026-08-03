# SVCP as a Function + Tab Reuse Fix + Versioning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Promote the ad-hoc SVCP hostname link into a first-class shared function (audited Python + JS URL builders, `svcp_url` on search API rows, web UI consumes the field, extension **Open SVCP** button). (2) Fix broken "use same tab" reuse for IDM/Grouper/printer in the extension. (3) Establish independent semver versioning for the app and extension (scheme **B2**).

**Architecture:** Mirror `modules/user_lookup/urls.py`. Add `modules/printer_search/svcp.py` with `build_svcp_url(hostname) -> str | None`. Enrich search rows with `svcp_url`. Web template renders `row.svcp_url` with full HTML escaping. Extension gets a testable `url_helpers.js` (CommonJS-guarded so node can unit-test it): URL builders moved there, a `matchesPrefix` tab-reuse matcher, and `buildSvcpUrl` mirroring the Python rules. `findOrCreateTab` rewritten to query a broad host pattern and reuse-by-path-prefix (query strings are invisible to Chrome match patterns — the current `*USN=...*` patterns can never match, causing duplicate tabs). App version read from a new `VERSION` file into `Config.APP_VERSION`, shown in the footer and a new `/api/status`; extension version stays `manifest.json` (source of truth, already read by `bin/build-extension.sh`).

**Tech Stack:** Python 3.11, Flask 2.x, pytest, node:test (v18 present on host), vanilla JS, Chrome MV3

## Parked (out of scope)

- Nextcloud share-token hardening (hardcoded `NEXTCLOUD_SHARE_TOKEN` fallback in `bin/build-extension.sh`), Docker build skipping upload (no curl in slim image), stale `browser_extension/README.md`, extension feature-branch release process. Track later; do not implement in this plan.
- `popup.js` `settingsBtn` calls `chrome.runtime.openOptionsPage()` but manifest has no `options_page` — pre-existing, unrelated to this work. Parked.

## Prerequisite

- DONE: `quick-links-categorization` merged to master (`c1eb6d6`); `tests/`, `requirements-dev.txt`, Docker pytest workflow now on master. 19 tests green.
- Host has no usable Python venv (no ensurepip, externally-managed) — run pytest via Docker image `pcm-test` (`python:3.11-slim` + requirements). Always append `-p no:cacheprovider` to avoid leaving root-owned `.pytest_cache` on the host volume.

## Global Constraints

- Python 3.11, Flask 2.x, no external JS frameworks
- NWU green `#006633` / `#4a8c6f`
- Pattern remains: `https://{short-hostname}.svcp.nwu.ac.za` (not `svpc`)
- Portal home `https://svcp.nwu.ac.za` stays a quick-link only — not this feature
- Do not change printer Excel schema or search matching logic beyond enrichment
- Commit per task; update `CHANGELOG.md` on meaningful changes
- Sanitize hostnames — never put raw Excel text into `href` without validation
- Chrome match patterns never match query strings → tab reuse must query broad host patterns and filter in JS
- Keep Python and JS URL rules in sync (comment `keep in sync with modules/printer_search/svcp.py`)
- Extension test files must not ship inside the built zip

---

## Audit findings (baseline)

| Finding | Severity | Disposition in this plan |
|---------|----------|---------------------------|
| URL built only in `templates/printer_search.html` inline JS | Maintainability | T1–T3: centralize |
| No sanitization — hostile/malformed hostname can break `href` or inject attributes | Important | T1: reject invalid → `None`; web shows plain text |
| FQDN / already-suffixed values (e.g. `foo.svcp.nwu.ac.za`) would become `foo.svcp.nwu.ac.za.svcp.nwu.ac.za` | Bug risk | T1: strip known suffixes; take left-most label if needed |
| Extension CHANGELOG claims “SVCP links” but popup has no per-printer SVCP | Docs drift | T5: real Open SVCP + honest CHANGELOG |
| Column name hard-coded `"Printer Hostname"` | Fragile | Keep (matches Excel); document; only enrich that key |
| No tests for SVCP URL rules | Gap | T1 tests |
| Tab reuse broken: `chrome.tabs.query({ url: "*://idm.nwu.ac.za/...jsp*USN=...*" })` — match patterns match **path only**, query `?Menu=...&USN=...` is never matched → `tabs.query` returns `[]` → always creates a new tab | Critical | T4: broad host pattern + JS `pathPrefix` reuse |
| IDM Consolidation & Password share one match pattern | Bug | T4: reuse-by-path reuses the single IDM tab and navigates it (Consolidation ↔ Pwd on same tab) |
| Printer "Open App"/Search passed full URL as pattern | Fragile | T4: `*://{host}/*` + pathname `/printer-search` |
| App version meaningless: `package.json` 0.1.0 unused; hardcoded `"2.1.0"` fallback in `templates/routes.py:33` | Maintainability | T6: `VERSION` file + `Config.APP_VERSION` + footer + `/api/status` + manifest-driven fallback |
| Extension version bump policy absent (stuck at 2.1.0 across feature releases) | Process | T6: bump to 2.2.0, document policy in AGENTS.md |

---

### Task 1: Python `build_svcp_url` + unit tests

**Files:**
- Create: `modules/printer_search/svcp.py`
- Create: `tests/test_printer_svcp.py`

**Interfaces:**
- `build_svcp_url(hostname: str | None) -> str | None`
- `SVCP_DOMAIN = "svcp.nwu.ac.za"` (module constant)

**Rules (implement exactly; tests lock them):**

1. `None` / non-string / empty after strip → `None`
2. Strip whitespace; lowercase for DNS label consistency
3. If value contains `://` or `/` or any whitespace → `None` (not a bare hostname)
4. If value ends with `.svcp.nwu.ac.za` (case-insensitive), strip that suffix and continue with remainder
5. If value ends with `.nwu.ac.za` but not SVCP suffix, take the **first label only** (e.g. `printer01.campus.nwu.ac.za` → `printer01`)
6. Allow only DNS label chars: `a-zA-Z0-9` and hyphens; labels separated by dots; no leading/trailing hyphen per label; max length 63 per label, 253 overall
7. Final short name must be non-empty → return `https://{name}.svcp.nwu.ac.za`
8. Never return a URL with unescaped quotes or spaces

- [ ] **Step 1: Write failing tests** in `tests/test_printer_svcp.py`

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c \
  "pip install -q pytest && python -m pytest tests/test_printer_svcp.py -v -p no:cacheprovider"
```

- [ ] **Step 3: Implement `modules/printer_search/svcp.py`**

```python
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
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add modules/printer_search/svcp.py tests/test_printer_svcp.py
git commit -m "feat: add build_svcp_url helper with hostname sanitization"
```

---

### Task 2: Enrich search API with `svcp_url`

**Files:**
- Modify: `modules/printer_search/engine.py` (single place — after `to_dict`)
- Modify: `modules/printer_search/routes.py` (no change required if engine does it; only if engine path is not feasible)
- Create: `tests/test_printer_search_svcp_enrichment.py`

**Interfaces:**
- Each successful search **row dict** gains optional key `svcp_url` (string) when `"Printer Hostname"` validates
- Error payloads unchanged: `{"error": "..."}` — no `svcp_url`
- Rows without hostname or invalid hostname **omit** the `svcp_url` key entirely
- `enrich_row_with_svcp(row: dict) -> dict` lives in `modules/printer_search/svcp.py` (testable pure function)

- [ ] **Step 1: Add `enrich_row_with_svcp` to `modules/printer_search/svcp.py`**

```python
def enrich_row_with_svcp(row: dict) -> dict:
    url = build_svcp_url(row.get("Printer Hostname"))
    if url:
        row = dict(row)
        row["svcp_url"] = url
    return row
```

- [ ] **Step 2: Wire into `search_all_sheets`** in `engine.py` — replace the return:

```python
        records = results_df.to_dict(orient="records")
        return [enrich_row_with_svcp(r) for r in records]
```

Add import at top of `engine.py`: `from modules.printer_search.svcp import enrich_row_with_svcp`

- [ ] **Step 3: Tests** in `tests/test_printer_search_svcp_enrichment.py`

```python
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c \
  "pip install -q pytest && python -m pytest tests/test_printer_svcp.py tests/test_printer_search_svcp_enrichment.py -q -p no:cacheprovider"
```

- [ ] **Step 5: Commit**

```bash
git add modules/printer_search/engine.py modules/printer_search/svcp.py tests/test_printer_search_svcp_enrichment.py
git commit -m "feat: attach svcp_url to printer search result rows"
```

---

### Task 3: Web UI consumes `svcp_url`

**Files:**
- Modify: `templates/printer_search.html`

**Interfaces:**
- Prefer `row.svcp_url` for `href`
- Fallback: if missing, render hostname as plain text (no client-side URL build — API is source of truth)
- Escape text content when rendering any cell (basic HTML escape)

- [ ] **Step 1: Add `escapeHtml` and replace the column renderer**

Add a top-level helper before `performSearch`:

```javascript
function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
```

Replace the inner column loop body (currently `templates/printer_search.html:82-87`):

```javascript
            columnOrder.forEach(c => {
                const value = row[c] || '';
                if (c === 'Printer Hostname' && row.svcp_url) {
                    html += `<td><a href="${escapeHtml(row.svcp_url)}" target="_blank" rel="noopener noreferrer" class="svcp-link">${escapeHtml(value)}</a></td>`;
                } else {
                    html += `<td>${escapeHtml(value)}</td>`;
                }
            });
```

- [ ] **Step 2: Structural verify**

```bash
grep -n "escapeHtml\|row.svcp_url\|noopener" templates/printer_search.html
```

- [ ] **Step 3: Smoke** — with app running, search a known printer; hostname link target is `https://….svcp.nwu.ac.za`; invalid host shows plain text.

- [ ] **Step 4: Commit**

```bash
git add templates/printer_search.html
git commit -m "feat: printer search uses API svcp_url; escape result cells"
```

---

### Task 4: Extension — fix "use same tab" reuse (IDM / Grouper / printer)

**Files:**
- Create: `browser_extension/url_helpers.js` (URL builders + `matchesPrefix`, CommonJS-guarded)
- Create: `tests/url_helpers.test.js` (node:test)
- Modify: `browser_extension/popup.js` (use helpers; rewrite `findOrCreateTab`)
- Modify: `browser_extension/popup.html` (load `url_helpers.js` before `popup.js`)
- Modify: `bin/build-extension.sh` (exclude `*.test.js` from zip)

**Interfaces:**
- `PCM_URL_HELPERS` global exposes: `buildIDMConsolidationURL(userId)`, `buildIDMPasswordURL(userId)`, `buildGrouperURL(userId)`, `matchesPrefix(tabUrl, pathPrefix)`
- `findOrCreateTab(realUrl, opts)` where `opts = { hostPattern, pathPrefix }` — returns focused existing tab or a new tab
- Later tasks rely on `PCM_URL_HELPERS.buildSvcpUrl` being added in T5

**Why this fixes the bug:** Chrome match patterns match `<scheme>://<host>/<path>` only. The query string (everything after `?`) is never matched. The current patterns `*://idm.nwu.ac.za/profileinfo/profileinfo.jsp*USN=abc*` demand the literal text `USN=abc` inside the **path**, but the real URL has it in the **query**, so `tabs.query` returns `[]` and a new tab is created every click. Fix: query `*://idm.nwu.ac.za/*` (matches any path on the host), then reuse the first tab whose `pathname` starts with `/profileinfo` (for IDM), `/grouper/` (for Grouper), or `/printer-search` (for the app). Reusing by path gives "one tab per tool" and lets IDM Consolidation ↔ Password navigate the same tab.

- [ ] **Step 1: Write failing JS tests** in `tests/url_helpers.test.js`

```js
const test = require('node:test');
const assert = require('node:assert');
const h = require('../browser_extension/url_helpers.js');

test('buildIDMConsolidationURL', () => {
    assert.strictEqual(h.buildIDMConsolidationURL('abc123'),
        'https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Consolidation&USN=abc123');
});

test('buildIDMPasswordURL', () => {
    assert.strictEqual(h.buildIDMPasswordURL('abc123'),
        'https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Pwd&USN=abc123');
});

test('buildGrouperURL includes user id', () => {
    const url = h.buildGrouperURL('abc123');
    assert.ok(url.startsWith('https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?'));
    assert.ok(url.includes('id=abc123'));
    assert.ok(url.includes('subjectId=abc123'));
});

test('matchesPrefix matches pathname ignoring query', () => {
    assert.ok(h.matchesPrefix('https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Consolidation&USN=abc', '/profileinfo'));
    assert.ok(h.matchesPrefix('https://idm.nwu.ac.za/profileinfo/', '/profileinfo'));
    assert.ok(!h.matchesPrefix('https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?x=1', '/profileinfo'));
    assert.ok(!h.matchesPrefix('not-a-url', '/profileinfo'));
    assert.ok(!h.matchesPrefix(null, '/profileinfo'));
});

test('matchesPrefix requires prefix at start of pathname', () => {
    assert.ok(!h.matchesPrefix('https://idm.nwu.ac.za/xprofileinfo/', '/profileinfo'));
});
```

- [ ] **Step 2: Run JS tests — expect FAIL** (module not found)

```bash
node --test tests/url_helpers.test.js
```

- [ ] **Step 3: Implement `browser_extension/url_helpers.js`** (CommonJS guard so node can require it; browser gets a global)

```js
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.PCM_URL_HELPERS = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
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

    function matchesPrefix(tabUrl, pathPrefix) {
        if (!tabUrl) return false;
        try {
            return new URL(tabUrl).pathname.startsWith(pathPrefix);
        } catch (e) {
            return false;
        }
    }

    return {
        buildIDMConsolidationURL: buildIDMConsolidationURL,
        buildIDMPasswordURL: buildIDMPasswordURL,
        buildGrouperURL: buildGrouperURL,
        matchesPrefix: matchesPrefix
    };
}));
```

- [ ] **Step 4: Run JS tests — expect PASS**

- [ ] **Step 5: Rewrite `findOrCreateTab` in `popup.js`** and use helpers

Replace the existing `findOrCreateTab` (currently `popup.js:35-43`):

```javascript
async function findOrCreateTab(realUrl, opts) {
    const tabs = await chrome.tabs.query({ url: opts.hostPattern });
    const target = tabs.find(t => PCM_URL_HELPERS.matchesPrefix(t.url, opts.pathPrefix));
    if (target) {
        await chrome.tabs.update(target.id, { url: realUrl, active: true });
        await chrome.windows.update(target.windowId, { focused: true });
        return target;
    }
    return chrome.tabs.create({ url: realUrl });
}
```

Remove the duplicated URL builders from `popup.js` (`buildIDMConsolidationURL`, `buildIDMPasswordURL`, `buildGrouperURL`, and the `IDM_BASE`/`GROUPER_BASE` consts) — they now live in `url_helpers.js`.

- [ ] **Step 6: Update the click handlers in `popup.js`**

```javascript
document.getElementById('idmConsolidationBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = PCM_URL_HELPERS.buildIDMConsolidationURL(v);
    findOrCreateTab(url, { hostPattern: '*://idm.nwu.ac.za/*', pathPrefix: '/profileinfo' });
});

document.getElementById('idmPasswordBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = PCM_URL_HELPERS.buildIDMPasswordURL(v);
    findOrCreateTab(url, { hostPattern: '*://idm.nwu.ac.za/*', pathPrefix: '/profileinfo' });
});

document.getElementById('grouperBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = PCM_URL_HELPERS.buildGrouperURL(v);
    findOrCreateTab(url, { hostPattern: '*://grp.nwu.ac.za/*', pathPrefix: '/grouper/' });
});
```

Update the printer handlers to reuse the `/printer-search` tab:

```javascript
async function printerHostPattern() {
    const appUrl = await getAppUrl();
    try {
        return { hostPattern: `*://${new URL(appUrl).host}/*`, pathPrefix: '/printer-search' };
    } catch (e) {
        return { hostPattern: '*://*/*', pathPrefix: '/printer-search' };
    }
}

document.getElementById('printerSearchBtn').addEventListener('click', async () => {
    const v = document.getElementById('printerInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.printer, v);
    const appUrl = await getAppUrl();
    const p = await printerHostPattern();
    findOrCreateTab(`${appUrl}/printer-search?q=${encodeURIComponent(v)}`, p);
});

document.getElementById('printerOpenBtn').addEventListener('click', async () => {
    const appUrl = await getAppUrl();
    const p = await printerHostPattern();
    findOrCreateTab(`${appUrl}/printer-search`, p);
});
```

- [ ] **Step 7: Load the helper in `popup.html`** — add before the `popup.js` script tag

```html
    <script src="url_helpers.js"></script>
    <script src="popup.js"></script>
```

- [ ] **Step 8: Exclude JS test files from the extension zip** in `bin/build-extension.sh`

Change the zip line to also exclude `*.test.js`:

```bash
zip -r "$DIST_DIR/$ZIP_NAME" . \
    -x "README.md" "INSTALL.md" "*__pycache__*" "*.pyc" "*.test.js"
```

- [ ] **Step 9: Verify JS tests still pass + popup.js has no leftover builders**

```bash
node --test tests/url_helpers.test.js
grep -n "buildIDM\|buildGrouper\|GROUPER_BASE\|IDM_BASE" browser_extension/popup.js || echo "OK: builders only in url_helpers.js"
```

- [ ] **Step 10: Commit**

```bash
git add browser_extension/url_helpers.js browser_extension/popup.js browser_extension/popup.html bin/build-extension.sh tests/url_helpers.test.js
git commit -m "fix: reuse same tab for IDM, Grouper, and printer search"
```

---

### Task 5: Extension — Open SVCP button + bump manifest to 2.2.0

**Files:**
- Modify: `browser_extension/url_helpers.js` (add `buildSvcpUrl`)
- Modify: `tests/url_helpers.test.js` (SVCP cases)
- Modify: `browser_extension/popup.html` (add button)
- Modify: `browser_extension/popup.js` (wire button; Enter key unchanged → Search)
- Modify: `browser_extension/manifest.json` (`version` → `2.2.0`)
- Rebuild: `static/dist/pcm-compass-v2.2.0.zip`

**Interfaces:**
- `PCM_URL_HELPERS.buildSvcpUrl(hostname) -> string | null` — mirrors `modules/printer_search/svcp.py::build_svcp_url` exactly
- New button `#printerSvcpBtn` label **Open SVCP** in the Printer Search button row
- On click: validate → `findOrCreateTab(url, { hostPattern: '*://*.svcp.nwu.ac.za/*', pathPrefix: '/' })` with real URL `https://{name}.svcp.nwu.ac.za`
- Invalid hostname: `alert('Invalid printer hostname')`, no tab created
- Saves printer history on success (same as Search)

- [ ] **Step 1: Add failing SVCP JS tests** to `tests/url_helpers.test.js`

```js
test('buildSvcpUrl valid hostname', () => {
    assert.strictEqual(h.buildSvcpUrl('printer01'), 'https://printer01.svcp.nwu.ac.za');
});

test('buildSvcpUrl strips svcp suffix', () => {
    assert.strictEqual(h.buildSvcpUrl('printer01.svcp.nwu.ac.za'), 'https://printer01.svcp.nwu.ac.za');
});

test('buildSvcpUrl takes first label of fqdn', () => {
    assert.strictEqual(h.buildSvcpUrl('printer01.campus.nwu.ac.za'), 'https://printer01.svcp.nwu.ac.za');
});

test('buildSvcpUrl rejects invalid', () => {
    assert.strictEqual(h.buildSvcpUrl('bad name'), null);
    assert.strictEqual(h.buildSvcpUrl('https://evil.example'), null);
    assert.strictEqual(h.buildSvcpUrl(''), null);
    assert.strictEqual(h.buildSvcpUrl('a/b'), null);
});
```

- [ ] **Step 2: Run JS tests — expect FAIL**

- [ ] **Step 3: Implement `buildSvcpUrl` in `url_helpers.js`** (inside the factory, before the return; comment `// keep in sync with modules/printer_search/svcp.py`)

```javascript
    const SVCP_DOMAIN = 'svcp.nwu.ac.za';
    const NWU_SUFFIX = '.nwu.ac.za';
    const LABEL_RE = /^(?!-)[a-z0-9-]{1,63}(?<!-)$/;

    function buildSvcpUrl(hostname) {
        if (typeof hostname !== 'string') return null;
        let name = hostname.trim().toLowerCase();
        if (!name || name.includes('://') || name.includes('/') || /\s/.test(name)) return null;
        const svcpSuffix = '.' + SVCP_DOMAIN;
        if (name.endsWith(svcpSuffix)) {
            name = name.slice(0, -svcpSuffix.length);
        } else if (name.endsWith(NWU_SUFFIX)) {
            name = name.split('.')[0];
        }
        if (!name || name.length > 253) return null;
        for (const label of name.split('.')) {
            if (!LABEL_RE.test(label)) return null;
        }
        return 'https://' + name + '.' + SVCP_DOMAIN;
    }
```

Add `buildSvcpUrl: buildSvcpUrl` to the returned object.

- [ ] **Step 4: Run JS tests — expect PASS**

- [ ] **Step 5: HTML** — add the button in `popup.html` (Printer Search button row, after Open App):

```html
                <button id="printerSvcpBtn" class="btn secondary">Open SVCP</button>
```

- [ ] **Step 6: Wire the handler in `popup.js`**

```javascript
document.getElementById('printerSvcpBtn').addEventListener('click', () => {
    const v = document.getElementById('printerInput').value.trim();
    if (!v) return;
    const url = PCM_URL_HELPERS.buildSvcpUrl(v);
    if (!url) {
        alert('Invalid printer hostname');
        return;
    }
    saveHistory(STORAGE_KEYS.printer, v);
    findOrCreateTab(url, { hostPattern: '*://*.svcp.nwu.ac.za/*', pathPrefix: '/' });
});
```

- [ ] **Step 7: Bump manifest version** to `2.2.0` in `browser_extension/manifest.json` (`"version": "2.2.0"`)

- [ ] **Step 8: Rebuild zip** (host has `zip`; Nextcloud upload may fail offline — that's fine)

```bash
bin/build-extension.sh || true   # reads manifest 2.2.0 → static/dist/pcm-compass-v2.2.0.zip
ls -la static/dist/pcm-compass-v2.2.0.zip
```

- [ ] **Step 9: Structural verify**

```bash
grep -n "buildSvcpUrl\|printerSvcpBtn\|svcp.nwu.ac.za" browser_extension/popup.js browser_extension/popup.html browser_extension/url_helpers.js
grep -n '"version"' browser_extension/manifest.json
unzip -l static/dist/pcm-compass-v2.2.0.zip | grep -c "url_helpers.js"   # expect 1 (test file excluded)
```

- [ ] **Step 10: Commit**

```bash
git add browser_extension/ static/dist/
git commit -m "feat: extension Open SVCP from printer hostname; bump to 2.2.0"
```

---

### Task 6: Versioning (B2) — app `VERSION` file + `/api/status` + manifest-driven download fallback

**Files:**
- Create: `VERSION` (repo root, content `0.2.0`)
- Modify: `config.py` (read `VERSION` → `Config.APP_VERSION`)
- Modify: `templates/base.html` (footer shows app version)
- Modify: `templates/routes.py` (add `/api/status`; fix hardcoded `"2.1.0"` fallback → read manifest)
- Modify: `package.json` (sync `version` to `0.2.0`)
- Modify: `AGENTS.md` (versioning policy)
- Create: `tests/test_status_version.py`

**Interfaces:**
- `Config.APP_VERSION: str` — read from `VERSION` file at import
- `GET /api/status` → `{"name": "PCM Compass", "app_version": "0.2.0", "extension_version": "2.2.0"}`
- Footer renders `PCM Compass v{{ config.APP_VERSION }}`
- `download_extension` fallback version derives from `browser_extension/manifest.json` instead of hardcoded `"2.1.0"`

**Versioning policy (document in AGENTS.md):**
- **App version** (`VERSION` file, source of truth): `MAJOR.MINOR.PATCH`; MAJOR for breaking API, MINOR for features, PATCH for fixes. Bump on every release. `package.json` mirrors it manually.
- **Extension version** (`manifest.json`, source of truth): `MAJOR.MINOR.PATCH`; bump on every shippable extension change. Build script already reads it for the zip name.

- [ ] **Step 1: Create `VERSION`** at repo root

```
0.2.0
```

- [ ] **Step 2: Read it in `config.py`** — add before the `Config` class:

```python
def _read_app_version():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")) as f:
            return f.read().strip() or "0.0.0"
    except FileNotFoundError:
        return "0.0.0"
```

Add to `Config`:

```python
    APP_VERSION = _read_app_version()
```

- [ ] **Step 3: Footer in `templates/base.html`** — inside `<main class="main">`, after `</main>`:

```html
    <footer class="footer">
        PCM Compass v{{ config.APP_VERSION }}
    </footer>
```

- [ ] **Step 4: `/api/status` + manifest fallback in `templates/routes.py`**

Add imports at top: `import json` and `from config import Config`. Add a helper:

```python
def _extension_manifest_version():
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "browser_extension", "manifest.json"
    )
    try:
        with open(manifest_path) as f:
            return json.load(f).get("version", "0.0.0")
    except (IOError, ValueError):
        return "0.0.0"
```

Add endpoint:

```python
@pages_bp.route("/api/status")
def api_status():
    return {
        "name": "PCM Compass",
        "app_version": Config.APP_VERSION,
        "extension_version": _extension_manifest_version(),
    }
```

In `download_extension`, replace `version = "2.1.0"` with:

```python
    version = _extension_manifest_version()
```

- [ ] **Step 5: Sync `package.json`** — `"version": "0.2.0"`

- [ ] **Step 6: Tests** in `tests/test_status_version.py`

```python
import pytest
from flask import Flask
from config import Config
from templates.routes import pages_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(pages_bp)
    return app.test_client()


def test_status_returns_versions(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "PCM Compass"
    assert data["app_version"] == Config.APP_VERSION
    assert data["extension_version"] == "2.2.0"


def test_status_app_version_matches_version_file():
    with open("VERSION") as f:
        assert Config.APP_VERSION == f.read().strip()
```

- [ ] **Step 7: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c \
  "pip install -q pytest && python -m pytest tests/test_status_version.py -q -p no:cacheprovider"
```

- [ ] **Step 8: Document policy in `AGENTS.md`** — add a "## Versioning" section (see Task 7 for the exact text; may be done together, but commit here if trivial).

- [ ] **Step 9: Commit**

```bash
git add VERSION config.py templates/base.html templates/routes.py package.json AGENTS.md tests/test_status_version.py
git commit -m "feat: add app VERSION source, /api/status, manifest-driven download fallback"
```

---

### Task 7: Docs + CHANGELOG + full test run

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `AGENTS.md` (API table: `svcp_url` field + `/api/status` + Versioning section if not committed in T6)
- Modify: `major-improvements-implementation-status.md` (progress note)

- [ ] **Step 1: CHANGELOG Added**

```markdown
- 2026-08-03: SVCP as shared function — build_svcp_url, search svcp_url field, escaped web links, extension Open SVCP button
- 2026-08-03: Fix extension tab reuse for IDM/Grouper/printer (query strings invisible to Chrome match patterns)
- 2026-08-03: Independent semver — app VERSION file (0.2.0) + /api/status + footer; extension manifest 2.2.0
```

- [ ] **Step 2: AGENTS.md** — add to the API table:

```
| GET | `/api/status` | none | App + extension versions (`{"app_version","extension_version"}`) |
```

and a note under printer search API: search rows may include `svcp_url` (built from `Printer Hostname`). Add the Versioning section:

```markdown
## Versioning

- App: `VERSION` file (repo root) is the source of truth, exposed as `Config.APP_VERSION`, footer, and `/api/status`. `package.json` mirrors it. Semver; bump on release.
- Extension: `browser_extension/manifest.json` is the source of truth. `bin/build-extension.sh` reads it for the zip name. Bump on every shippable extension change.
```

- [ ] **Step 3: Full test run (pytest + JS)**

```bash
docker run --rm -v "$PWD:/app" -w /app -e ADMIN_PASSWORD=test-password -e FLASK_SECRET_KEY=test-secret \
  pcm-test bash -c "pip install -q pytest pytest-cov && python -m pytest tests/ -v -p no:cacheprovider"
node --test tests/url_helpers.test.js
```

- [ ] **Step 4: Verify no root-owned cache left on host**

```bash
ls -la .pytest_cache 2>/dev/null || echo "OK: no .pytest_cache on host"
```

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md AGENTS.md major-improvements-implementation-status.md
git commit -m "docs: document SVCP enrichment, tab reuse fix, and versioning"
```

---

## Self-review checklist

- [ ] Python and JS URL rules match (same fixtures: `printer01`, FQDN strip, reject spaces)
- [ ] API error objects unchanged
- [ ] Web never concatenates hostname into href without `svcp_url`
- [ ] Extension works offline (no Flask required for Open SVCP)
- [ ] IDM Consolidation and Password each reuse the same IDM tab (navigate in place), no duplicates
- [ ] Grouper reuses the Grouper tab; printer reuses `/printer-search` tab
- [ ] No Nextcloud/token work in this branch
- [ ] CHANGELOG no longer implies extension had per-printer SVCP before this work
- [ ] `VERSION` file = `0.2.0`, manifest = `2.2.0`, `package.json` synced
- [ ] `/api/status` returns both versions; download page fallback no longer hardcoded `2.1.0`

## Verification (manual)

1. `POST /api/printer/search` with known host → JSON row includes `"svcp_url": "https://….svcp.nwu.ac.za"`
2. `/printer-search` results: link uses that URL; `rel="noopener noreferrer"`; bad host shows plain text
3. Extension: type hostname → Open SVCP → tab to device web UI; second click focuses same tab
4. Extension: IDM Consolidation, then IDM Password for same user → same tab navigates; no duplicates; same for Grouper
5. Extension: Search, then Open App → same `/printer-search` tab reused
6. `GET /api/status` → `{"name":"PCM Compass","app_version":"0.2.0","extension_version":"2.2.0"}`
7. Footer shows `PCM Compass v0.2.0`; `/download-extension` shows v2.2.0
8. `pytest` + `node --test` green
