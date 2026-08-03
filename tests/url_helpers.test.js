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
