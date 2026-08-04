# PCM Compass Extension — Installation Guide

## Quick Start (desk/tech staff — primary path)

The extension is deployed from the PCM team to a **Nextcloud shared folder**. Once that folder is synced to your PC, you load the extension straight from it — updates arrive automatically.

1. Make sure the Nextcloud folder is synced to this PC with **"Always keep on this device"** enabled:
   `%USERPROFILE%\NWUNextcloud\SFG (Tested and Deployed)\Nexus\pcm-compass`
   (The desktop client syncs new versions automatically when the team deploys.)
2. Open your browser's extensions page (see below) and enable **Developer mode**.
3. Click **Load unpacked** and select the synced `pcm-compass` folder.
4. Pin the extension to your toolbar.

## ZIP install (fallback)

1. Download `pcm-compass-v{version}.zip` from your team lead or the server
2. Extract the ZIP to a permanent folder (e.g. `C:\PCM-Compass` or `~/PCM-Compass`)
3. Load unpacked from the extracted folder instead

## Browser instructions

### Chrome / Edge / Brave

1. Open `chrome://extensions` (or `edge://extensions`)
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `pcm-compass` folder (synced) or your extracted ZIP folder
5. Pin the extension to your toolbar for quick access

### Opera

1. Open `opera://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the folder

### Firefox

1. Open `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on...**
3. Select `manifest.json` inside the folder

> **Note:** Firefox removes temporary add-ons when you close the browser.
> For permanent installation, use Firefox Developer Edition or contact IT.

## After Installation

1. Click the PCM Compass icon in your toolbar
2. Enter a Printer Hostname or NWU User ID
3. The extension opens the relevant pages directly — no login dialogs needed (your browser session handles authentication)
4. The footer of the popup shows the installed version, an **"Open app"** link, and a **"What's new"** link to the user changelog
5. Use **Settings (⚙)** in the popup header to change or reset the app address if the server moves

## Updating

New versions are deployed to the shared Nextcloud folder by the PCM team:

- **JS/HTML/CSS changes** (popup, links, changelog) arrive automatically — they apply the **next time you open the popup**. No action needed.
- **`manifest.json` changes** (new version number, permissions, host permissions, icons) require a one-time **Reload (↻)** on the extensions page, or a browser restart — Chrome only reads the manifest when the extension loads. (The browser's "Update" button does not apply to Load-unpacked extensions.)
- The popup shows a **yellow banner** when a reload is needed — open `chrome://extensions` and click **Reload (↻)**.
- If anything looks stale after a deploy, click **Reload (↻)** on the extension card — it re-reads everything from the synced folder.
