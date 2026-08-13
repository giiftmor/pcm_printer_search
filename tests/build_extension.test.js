const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const popupHtml = fs.readFileSync(path.join(ROOT, 'browser_extension/popup.html'), 'utf8');
const buildScript = fs.readFileSync(path.join(ROOT, 'bin/build-extension.sh'), 'utf8');

const SCRIPT_SRCS = [...popupHtml.matchAll(/<script\s+src="([^"]+)">/g)].map(m => m[1]);
const EXT_FILES_LINE = buildScript.match(/^EXT_FILES="([^"]+)"/m);
assert.ok(EXT_FILES_LINE, 'build-extension.sh must define EXT_FILES');

const EXT_FILES = EXT_FILES_LINE[1].split(' ');

const EXTENSION_ROOT = path.join(ROOT, 'browser_extension');
const REQUIRED_FILES = [
    'manifest.json',
    'version.json',
    ...SCRIPT_SRCS,
    'changelog.html',
];

test('every popup script src is uploaded individually to Nextcloud', () => {
    assert.ok(SCRIPT_SRCS.length >= 2, 'popup.html should reference its script files');
    for (const src of SCRIPT_SRCS) {
        assert.ok(EXT_FILES.includes(src), `EXT_FILES must include ${src}`);
    }
});

test('all runtime-required extension files are uploaded individually to Nextcloud', () => {
    assert.ok(EXT_FILES.includes('popup.css'), 'EXT_FILES must include popup.css');
    assert.ok(EXT_FILES.includes('version.json'), 'EXT_FILES must include version.json');
    for (const icon of ['icon16.png', 'icon48.png', 'icon128.png']) {
        assert.ok(EXT_FILES.includes(icon), `EXT_FILES must include ${icon}`);
    }
});

test('every runtime-required file exists in browser_extension/ and is in EXT_FILES', () => {
    for (const file of REQUIRED_FILES) {
        assert.ok(fs.existsSync(path.join(EXTENSION_ROOT, file)), `${file} must exist in browser_extension/`);
        assert.ok(EXT_FILES.includes(file), `EXT_FILES must include ${file}`);
    }
});

test('popup includes a Ticket Search section', () => {
    assert.ok(popupHtml.includes('id="ticketInput"'), 'popup.html must include #ticketInput');
    assert.ok(popupHtml.includes('id="ticketSearchBtn"'), 'popup.html must include #ticketSearchBtn');
    assert.ok(popupHtml.includes('id="ticket-history"'), 'popup.html must include the ticket history datalist');
    assert.ok(popupHtml.includes('Ticket Search'), 'popup.html must label the section Ticket Search');
});
