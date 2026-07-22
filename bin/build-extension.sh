#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
EXT_DIR="$ROOT_DIR/browser_extension"
DIST_DIR="$ROOT_DIR/static/dist"

NEXTCLOUD_SHARE_TOKEN="${NEXTCLOUD_SHARE_TOKEN:-kaPSTNPpgsBzQk8}"
NEXTCLOUD_WEBDAV="https://nextcloud.nwu.ac.za/public.php/webdav"

# Read version from manifest
VERSION=$(python3 -c "import json; print(json.load(open('$EXT_DIR/manifest.json'))['version'])")
ZIP_NAME="pcm-compass-v${VERSION}.zip"

mkdir -p "$DIST_DIR"

echo "Building PCM Compass v${VERSION}..."

# Clean previous build
rm -f "$DIST_DIR/$ZIP_NAME"

# Create ZIP (exclude README.md, INSTALL.md, __pycache__)
cd "$EXT_DIR"
zip -r "$DIST_DIR/$ZIP_NAME" . \
    -x "README.md" "INSTALL.md" "*__pycache__*" "*.pyc"
cd "$ROOT_DIR"

echo "Built: $DIST_DIR/$ZIP_NAME ($(du -h "$DIST_DIR/$ZIP_NAME" | cut -f1))"

# Upload to Nextcloud public share (upload-enabled)
echo "Uploading to Nextcloud..."
AUTH_HEADER="Authorization: Basic $(echo -n "${NEXTCLOUD_SHARE_TOKEN}:" | base64)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -T "$DIST_DIR/$ZIP_NAME" \
    "${NEXTCLOUD_WEBDAV}/${ZIP_NAME}" \
    -H "$AUTH_HEADER")

if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "204" ]; then
    echo "Uploaded: https://nextcloud.nwu.ac.za/index.php/s/${NEXTCLOUD_SHARE_TOKEN}"
else
    echo "Upload failed (HTTP $HTTP_CODE)"
    exit 1
fi

echo "Done."
