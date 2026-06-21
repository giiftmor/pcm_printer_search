# NWU Quick Links Browser Extension

A safe, local browser extension for quick access to NWU SVPC and IDM Profile pages.

## Features

- **Print ID Quick Access**: Enter a Print ID and redirect to `[printID].svpc.nwu.ac.za` in a new tab
- **PID User Profile**: Enter a PID User and redirect to the IDM profile page. If the page is already open, it updates the URL instead of opening a new tab
- **Autocomplete**: Both textboxes remember your previous entries for quick access
- **Enter Key Support**: Press Enter in either textbox to submit
- **Compatible**: Works with Chrome, Edge, and Brave browsers

## Installation Instructions

### For Chrome:
1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" using the toggle in the top-right corner
3. Click "Load unpacked"
4. Select the `nwu-redirect-extension` folder
5. The extension icon should appear in your toolbar

### For Edge:
1. Open Edge and navigate to `edge://extensions/`
2. Enable "Developer mode" using the toggle in the bottom-left corner
3. Click "Load unpacked"
4. Select the `nwu-redirect-extension` folder
5. The extension icon should appear in your toolbar

### For Brave:
1. Open Brave and navigate to `brave://extensions/`
2. Enable "Developer mode" using the toggle in the top-right corner
3. Click "Load unpacked"
4. Select the `nwu-redirect-extension` folder
5. The extension icon should appear in your toolbar

## Usage

1. Click the extension icon in your browser toolbar
2. Enter a Print ID or PID User in the respective textbox
3. Click the button or press Enter to redirect
4. Previously used values will appear as autocomplete suggestions

## Privacy & Safety

- **100% Local**: All data is stored locally in your browser
- **No External Connections**: The extension only redirects to specified NWU URLs
- **No Data Collection**: Your entries are stored only on your device
- **Open Source**: You can review all the code in this folder

## Files Included

- `manifest.json` - Extension configuration
- `popup.html` - User interface
- `popup.css` - Styling
- `popup.js` - Functionality and logic
- `icon16.png`, `icon48.png`, `icon128.png` - Extension icons
- `README.md` - This file

## Troubleshooting

If the extension doesn't work:
1. Make sure Developer mode is enabled
2. Try reloading the extension
3. Check that all files are in the same folder
4. Ensure you have the latest browser version

## Support

This is a local extension for personal use. If you encounter issues, check that:
- The URLs are accessible from your network
- You have the correct permissions to access the NWU services
- Your browser allows extensions to open new tabs
