#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
EXT_DIR="$ROOT_DIR/browser_extension"
DIST_DIR="$ROOT_DIR/static/dist"

NEXTCLOUD_SHARE_TOKEN="${NEXTCLOUD_SHARE_TOKEN:-kaPSTNPpgsBzQk8}"
NEXTCLOUD_WEBDAV="https://nextcloud.nwu.ac.za/public.php/webdav"
NEXTCLOUD_LINK="https://nextcloud.nwu.ac.za/index.php/s/${NEXTCLOUD_SHARE_TOKEN}"

# Extension files to upload to pcm-compass/ subfolder
EXT_FILES="manifest.json popup.html popup.js popup.css icon16.png icon48.png icon128.png"

# Docs to upload to root
DOC_FILES="INSTALL.md README.md"

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

# Upload to Nextcloud — skip if curl not available
if command -v curl &> /dev/null; then
    AUTH_HEADER="Authorization: Basic $(echo -n "${NEXTCLOUD_SHARE_TOKEN}:" | base64)"

    # Create pcm-compass/ subfolder (405 = already exists, treat as success)
    echo "Creating pcm-compass/ folder..."
    MKCOL_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X MKCOL "${NEXTCLOUD_WEBDAV}/pcm-compass/" \
        -H "$AUTH_HEADER")
    if [ "$MKCOL_CODE" = "201" ] || [ "$MKCOL_CODE" = "405" ]; then
        echo "Folder ready: pcm-compass/"
    else
        echo "Failed to create folder (HTTP $MKCOL_CODE)"
        exit 1
    fi

    # Upload extension files to pcm-compass/
    echo "Uploading extension files..."
    for FILE in $EXT_FILES; do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -T "$EXT_DIR/$FILE" \
            "${NEXTCLOUD_WEBDAV}/pcm-compass/${FILE}" \
            -H "$AUTH_HEADER")
        if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "204" ]; then
            echo "  ✓ ${FILE}"
        else
            echo "  ✗ ${FILE} (HTTP $HTTP_CODE)"
            exit 1
        fi
    done

    # Upload ZIP to root
    echo "Uploading ZIP..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -T "$DIST_DIR/$ZIP_NAME" \
        "${NEXTCLOUD_WEBDAV}/${ZIP_NAME}" \
        -H "$AUTH_HEADER")
    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "204" ]; then
        echo "  ✓ ${ZIP_NAME}"
    else
        echo "  ✗ ${ZIP_NAME} (HTTP $HTTP_CODE)"
        exit 1
    fi

    # Upload docs to root
    echo "Uploading documentation..."
    for FILE in $DOC_FILES; do
        if [ -f "$EXT_DIR/$FILE" ]; then
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
                -T "$EXT_DIR/$FILE" \
                "${NEXTCLOUD_WEBDAV}/${FILE}" \
                -H "$AUTH_HEADER")
            if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "204" ]; then
                echo "  ✓ ${FILE}"
            else
                echo "  ✗ ${FILE} (HTTP $HTTP_CODE)"
                exit 1
            fi
        fi
    done

    echo ""
    echo "Uploaded to Nextcloud: ${NEXTCLOUD_LINK}"
else
    echo "curl not found — skipping Nextcloud upload (run bin/build-extension.sh on host to upload)"
fi

echo "Done."
