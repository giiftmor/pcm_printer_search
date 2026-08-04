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

test('buildSvcpUrl', () => {
    assert.strictEqual(h.buildSvcpUrl('printer01'), 'https://printer01.svcp.nwu.ac.za');
    assert.strictEqual(h.buildSvcpUrl('  printer01  '), 'https://printer01.svcp.nwu.ac.za');
    assert.strictEqual(h.buildSvcpUrl('printer01.svcp.nwu.ac.za'), 'https://printer01.svcp.nwu.ac.za');
    assert.strictEqual(h.buildSvcpUrl('printer01.campus.nwu.ac.za'), 'https://printer01.svcp.nwu.ac.za');
    assert.strictEqual(h.buildSvcpUrl('bad name'), null);
    assert.strictEqual(h.buildSvcpUrl('https://evil.example'), null);
    assert.strictEqual(h.buildSvcpUrl(''), null);
    assert.strictEqual(h.buildSvcpUrl('a/b'), null);
});

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
