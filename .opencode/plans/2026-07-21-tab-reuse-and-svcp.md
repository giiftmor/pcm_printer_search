# Grouper Tab Reuse + SVCP Link Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Make IDM and Grouper reuse existing tabs instead of opening duplicates. (2) Add SVCP links to the printer hostname column in search results.

**Architecture:** The extension popup searches for existing tabs matching URL patterns before creating new ones. If a match is found, it switches to that tab. For SVCP, the printer search template wraps hostname values in `<a>` tags pointing to `https://{hostname}.svcp.nwu.ac.za`.

**Tech Stack:** Chrome Extension MV3, vanilla JS, Flask/Jinja2 templates

## Global Constraints

- Python 3.11, Flask 2.x, Chrome Extension MV3
- NWU green branding: `#006633` primary, `#4a8c6f` secondary
- No external JS frameworks — vanilla JS only

---

## Tasks

### Task 1: Tab reuse for IDM and Grouper in extension popup

**Files:**
- Modify: `browser_extension/popup.js`

**Interfaces:**
- Produces: `findOrCreateTab(urlPattern) -> Promise<tab>` function that finds an existing tab matching a URL pattern or creates a new one

- [ ] **Step 1: Add `findOrCreateTab` function to popup.js**

```javascript
async function findOrCreateTab(urlPattern) {
    const tabs = await chrome.tabs.query({ url: urlPattern });
    if (tabs.length > 0) {
        await chrome.tabs.update(tabs[0].id, { active: true });
        await chrome.windows.update(tabs[0].windowId, { focused: true });
        return tabs[0];
    }
    return chrome.tabs.create({ url: urlPattern });
}
```

- [ ] **Step 2: Update IDM button handlers to use `findOrCreateTab`**

Replace:
```javascript
chrome.tabs.create({ url: buildIDMConsolidationURL(v) });
```
With:
```javascript
findOrCreateTab(`*://idm.nwu.ac.za/profileinfo/profileinfo.jsp*USN=${encodeURIComponent(v)}*`);
```

Same for IDM Password button.

- [ ] **Step 3: Update Grouper button handler to use `findOrCreateTab`**

Replace:
```javascript
chrome.tabs.create({ url: buildGrouperURL(v) });
```
With:
```javascript
findOrCreateTab(`*://grp.nwu.ac.za/grouper/populateSubjectSummary.do*${encodeURIComponent(v)}*`);
```

- [ ] **Step 4: Update manifest.json permissions**

Add `tabs` permission (may already be present) — needed for `chrome.tabs.query` with URL patterns:
```json
"permissions": ["tabs", "storage"]
```

- [ ] **Step 5: Test manually**

Load extension in Chrome. Open IDM for a user. Click IDM again — should switch to existing tab, not open a new one. Same for Grouper.

- [ ] **Step 6: Commit**

```bash
git add browser_extension/popup.js browser_extension/manifest.json
git commit -m "feat: reuse existing IDM/Grouper tabs instead of opening duplicates"
```

---

### Task 2: SVCP link in printer hostname column

**Files:**
- Modify: `templates/printer_search.html`
- Modify: `static/css/compass.css` (optional, for link styling)

**Interfaces:**
- Consumes: `row["Printer Hostname"]` from search results
- Produces: Hostname column rendered as `<a href="https://{hostname}.svcp.nwu.ac.za" target="_blank">{hostname}</a>`

- [ ] **Step 1: Update the table-building JS in `printer_search.html`**

Find the line:
```javascript
columnOrder.forEach(c => html += `<td>${row[c] || ''}</td>`);
```

Replace with:
```javascript
columnOrder.forEach(c => {
    if (c === 'Printer Hostname' && row[c]) {
        const hostname = row[c];
        html += `<td><a href="https://${hostname}.svcp.nwu.ac.za" target="_blank" class="svcp-link">${hostname}</a></td>`;
    } else {
        html += `<td>${row[c] || ''}</td>`;
    }
});
```

- [ ] **Step 2: Add SVCP link styles to `compass.css`**

```css
.svcp-link {
    color: #006633;
    text-decoration: none;
}
.svcp-link:hover {
    text-decoration: underline;
    color: #4a8c6f;
}
```

- [ ] **Step 3: Test**

Run the app, search for a printer. Verify the hostname is a clickable link pointing to `https://{hostname}.svcp.nwu.ac.za`.

- [ ] **Step 4: Commit**

```bash
git add templates/printer_search.html static/css/compass.css
git commit -m "feat: add SVCP link to printer hostname column"
```

---

## Verification

1. Load extension in Chrome
2. Open IDM for a user → tab opens
3. Open IDM for same user again → switches to existing tab (no duplicate)
4. Open Grouper for a user → tab opens
5. Open Grouper for same user again → switches to existing tab
6. Open app → search for a printer → hostname is a clickable link → opens SVCP page
