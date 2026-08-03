# Extension Packaging & Distribution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, package, and distribute the PCM Compass Chrome extension to colleagues via Flask download page + Nextcloud WebDAV upload.

**Architecture:** A build script zips the extension and saves it to `static/dist/`. The Flask app serves a `/download-extension` page with the ZIP download link and installation instructions. Optionally uploads to Nextcloud via WebDAV for external access. The build runs both manually and during Docker image build.

**Tech Stack:** Bash (build script), Python/Flask (download route), Nextcloud WebDAV (optional upload), Docker

## Global Constraints

- Python 3.11, Flask 2.x, Docker multi-stage build
- Extension is Chrome Manifest V3 — but installation docs cover all browsers
- Nextcloud WebDAV is optional (controlled by env vars)
- Build script must work both inside Docker and on the host

---

## Tasks

### Task 1: Create build script

**Files:**
- Create: `bin/build-extension.sh`

**Interfaces:**
- Input: `browser_extension/` directory
- Output: `static/dist/pcm-compass-v{version}.zip`
- Optional output: Upload to Nextcloud WebDAV

- [ ] **Step 1: Create `bin/build-extension.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
EXT_DIR="$ROOT_DIR/browser_extension"
DIST_DIR="$ROOT_DIR/static/dist"

# Read version from manifest
VERSION=$(python3 -c "import json; print(json.load(open('$EXT_DIR/manifest.json'))['version'])")
ZIP_NAME="pcm-compass-v${VERSION}.zip"

echo "Building PCM Compass v${VERSION}..."

# Clean previous build
rm -f "$DIST_DIR/$ZIP_NAME"

# Create ZIP (exclude README.md and __pycache__)
cd "$EXT_DIR"
zip -r "$DIST_DIR/$ZIP_NAME" . -x "README.md" "*__pycache__*" "*.pyc"
cd "$ROOT_DIR"

echo "Built: $DIST_DIR/$ZIP_NAME"

# Optional: Upload to Nextcloud WebDAV
if [ -n "${NEXTCLOUD_WEBDAV_URL:-}" ] && [ -n "${NEXTCLOUD_WEBDAV_USER:-}" ] && [ -n "${NEXTCLOUD_WEBDAV_PASS:-}" ]; then
    echo "Uploading to Nextcloud..."
    curl -s -u "$NEXTCLOUD_WEBDAV_USER:$NEXTCLOUD_WEBDAV_PASS" \
        -T "$DIST_DIR/$ZIP_NAME" \
        "$NEXTCLOUD_WEBDAV_URL/$ZIP_NAME"
    echo "Uploaded to Nextcloud: $NEXTCLOUD_WEBDAV_URL/$ZIP_NAME"
else
    echo "Nextcloud upload skipped (NEXTCLOUD_WEBDAV_URL/USER/PASS not set)"
fi

echo "Done."
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x bin/build-extension.sh
```

- [ ] **Step 3: Create `static/dist/` directory**

```bash
mkdir -p static/dist
```

- [ ] **Step 4: Test the build script**

```bash
./bin/build-extension.sh
```

Expected: ZIP created at `static/dist/pcm-compass-v2.1.0.zip`

- [ ] **Step 5: Commit**

```bash
git add bin/build-extension.sh static/dist/
git commit -m "feat: add extension build script"
```

---

### Task 2: Add Flask download route

**Files:**
- Create: `templates/download_extension.html`
- Modify: `templates/routes.py` (add route)
- Modify: `templates/base.html` (add nav item)
- Modify: `templates/dashboard.html` (add card)

**Interfaces:**
- Produces: `GET /download-extension` — page with download link + install instructions
- Produces: `GET /download-extension/zip` — serves the ZIP file

- [ ] **Step 1: Create `templates/download_extension.html`**

```html
{% extends "base.html" %}
{% block title %}PCM Compass - Download Extension{% endblock %}
{% block header %}Download Extension{% endblock %}
{% block content %}
<div class="card">
    <h2>PCM Compass Browser Extension</h2>
    <p>Download the latest version of the PCM Compass extension.</p>

    <div style="margin: 20px 0;">
        <a href="/download-extension/zip" class="btn btn-primary" style="text-decoration:none;display:inline-block;">
            Download PCM Compass v{{ version }}
        </a>
        <span style="margin-left:12px;color:#999;font-size:13px;">Updated: {{ date }}</span>
    </div>

    <h3 style="margin-top:24px;">Installation Instructions</h3>

    <div style="margin-top:12px;">
        <h4>Chrome / Edge / Brave</h4>
        <ol style="margin:8px 0 16px 20px;font-size:14px;line-height:1.8;">
            <li>Download the ZIP file above</li>
            <li>Extract the ZIP to a folder you'll keep (e.g. <code>PCM-Compass</code>)</li>
            <li>Open your browser and go to <code>chrome://extensions</code> (or <code>edge://extensions</code>)</li>
            <li>Enable <strong>Developer mode</strong> (toggle in top-right)</li>
            <li>Click <strong>Load unpacked</strong></li>
            <li>Select the extracted <code>PCM-Compass</code> folder</li>
            <li>The extension icon appears in your toolbar — pin it for easy access</li>
        </ol>

        <h4>Opera</h4>
        <ol style="margin:8px 0 16px 20px;font-size:14px;line-height:1.8;">
            <li>Download the ZIP file above</li>
            <li>Extract the ZIP to a folder you'll keep</li>
            <li>Open Opera and go to <code>opera://extensions</code></li>
            <li>Enable <strong>Developer mode</strong></li>
            <li>Click <strong>Load unpacked</strong> and select the extracted folder</li>
        </ol>

        <h4>Firefox</h4>
        <ol style="margin:8px 0 16px 20px;font-size:14px;line-height:1.8;">
            <li>Download the ZIP file above</li>
            <li>Extract the ZIP to a folder you'll keep</li>
            <li>Open Firefox and go to <code>about:debugging#/runtime/this-firefox</code></li>
            <li>Click <strong>Load Temporary Add-on...</strong></li>
            <li>Select any file inside the extracted folder (e.g. <code>manifest.json</code>)</li>
            <li><strong>Note:</strong> Firefox temporary add-ons are removed when Firefox closes. To keep it, use a Firefox Developer Edition or configure auto-loading.</li>
        </ol>
    </div>

    <div class="error-box" style="margin-top:20px;">
        <strong>Important:</strong> After installing, the extension needs to connect to the PCM Compass server.
        If the server URL is not auto-detected, click the extension icon → ⚙️ Settings → enter the server URL.
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Add routes to `templates/routes.py`**

```python
import os
import glob
from flask import send_file, render_template

@bp.route('/download-extension')
def download_extension():
    dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'dist')
    zips = sorted(glob.glob(os.path.join(dist_dir, 'pcm-compass-v*.zip')), reverse=True)
    version = '2.1.0'
    date = ''
    if zips:
        fname = os.path.basename(zips[0])
        version = fname.replace('pcm-compass-v', '').replace('.zip', '')
        date = time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(zips[0])))
    return render_template('download_extension.html', version=version, date=date)

@bp.route('/download-extension/zip')
def download_extension_zip():
    dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'dist')
    zips = sorted(glob.glob(os.path.join(dist_dir, 'pcm-compass-v*.zip')), reverse=True)
    if not zips:
        return 'No extension package found. Run bin/build-extension.sh first.', 404
    return send_file(zips[0], as_attachment=True)
```

- [ ] **Step 3: Add nav item to `templates/base.html`**

Add "Download Extension" link to the sidebar nav.

- [ ] **Step 4: Add dashboard card to `templates/dashboard.html`**

```html
<a href="/download-extension" class="dashboard-card">
    <div class="card-icon">📦</div>
    <h3>Download Extension</h3>
    <p>Get the PCM Compass browser extension for Chrome, Edge, or Firefox.</p>
</a>
```

- [ ] **Step 5: Test**

Run the app, visit `/download-extension`, verify the page renders and download works.

- [ ] **Step 6: Commit**

```bash
git add templates/download_extension.html templates/routes.py templates/base.html templates/dashboard.html
git commit -m "feat: add extension download page with install instructions"
```

---

### Task 3: Add Nextcloud WebDAV config to .env

**Files:**
- Modify: `.env`
- Modify: `.env.example`

**Interfaces:**
- Adds: `NEXTCLOUD_WEBDAV_URL`, `NEXTCLOUD_WEBDAV_USER`, `NEXTCLOUD_WEBDAV_PASS`

- [ ] **Step 1: Add env vars to `.env`**

```
NEXTCLOUD_WEBDAV_URL=
NEXTCLOUD_WEBDAV_USER=
NEXTCLOUD_WEBDAV_PASS=
```

- [ ] **Step 2: Add same to `.env.example` with comments**

```
# Nextcloud WebDAV (optional — for extension distribution)
# Example: https://nextcloud.nwu.ac.za/remote.php/dav/files/username/PCM-Compass
NEXTCLOUD_WEBDAV_URL=
NEXTCLOUD_WEBDAV_USER=
NEXTCLOUD_WEBDAV_PASS=
```

- [ ] **Step 3: Commit**

```bash
git add .env .env.example
git commit -m "feat: add Nextcloud WebDAV env vars for extension upload"
```

---

### Task 4: Docker integration

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`

**Interfaces:**
- Adds: `browser_extension/` to Docker image
- Adds: `static/dist/` volume for persistent extension packages
- Adds: Build script runs during Docker build

- [ ] **Step 1: Update Dockerfile to include extension + run build**

Add after the application files copy:

```dockerfile
# Copy browser extension and build package
COPY browser_extension/ /app/browser_extension/
COPY bin/build-extension.sh /app/bin/build-extension.sh
RUN mkdir -p /app/static/dist && /app/bin/build-extension.sh
```

- [ ] **Step 2: Update docker-compose.yml to mount dist/ volume**

Add to volumes:
```yaml
volumes:
  - ./workbook_url.txt:/app/workbook_url.txt:ro
  - ./static/dist:/app/static/dist
```

- [ ] **Step 3: Test Docker build**

```bash
docker compose build
docker compose up -d
# Visit http://localhost:5000/download-extension
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: include extension in Docker image, add build step"
```

---

### Task 5: Create INSTALL.md for extension

**Files:**
- Create: `browser_extension/INSTALL.md`

**Interfaces:**
- Produces: Standalone installation guide that ships with the ZIP

- [ ] **Step 1: Create `browser_extension/INSTALL.md`**

```markdown
# PCM Compass Extension — Installation Guide

## Quick Start

1. Download `pcm-compass-v{version}.zip` from your team lead or the server
2. Extract the ZIP to a permanent folder (e.g. `C:\PCM-Compass` or `~/PCM-Compass`)
3. Follow the instructions for your browser below

## Chrome / Edge / Brave

1. Open `chrome://extensions` (or `edge://extensions`)
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the extracted `PCM-Compass` folder
5. Pin the extension to your toolbar for quick access

## Opera

1. Open `opera://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the extracted folder

## Firefox

1. Open `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on...**
3. Select `manifest.json` inside the extracted folder

> **Note:** Firefox removes temporary add-ons when you close the browser.
> For permanent installation, use Firefox Developer Edition or contact IT.

## After Installation

1. Click the PCM Compass icon in your toolbar
2. Enter a Printer Hostname or NWU User ID
3. The extension opens the relevant pages directly — no login dialogs needed

## Updating

When a new version is released:
1. Delete the old extracted folder
2. Extract the new ZIP to the same location
3. In your browser's extensions page, click the refresh icon on PCM Compass
```

- [ ] **Step 2: Commit**

```bash
git add browser_extension/INSTALL.md
git commit -m "docs: add extension installation guide for all browsers"
```

---

## Verification

1. Run `./bin/build-extension.sh` — ZIP created at `static/dist/pcm-compass-v2.1.0.zip`
2. Visit `http://localhost:5000/download-extension` — page renders with download button
3. Click download — ZIP downloads successfully
4. Extract ZIP — contains manifest.json, popup.html, popup.js, popup.css, icons
5. Load in Chrome as unpacked extension — extension works
6. Set NEXTCLOUD_WEBDAV_* env vars — run build script again — ZIP uploads to Nextcloud
