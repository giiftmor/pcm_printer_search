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

test('buildGrouperGroupURL matches Python quote for ~ and *', () => {
    const url = h.buildGrouperGroupURL('a~b*c');
    assert.ok(url.includes('name=a~b%2Ac'));
    assert.ok(!url.includes('%7E'));
    const url2 = h.buildGrouperGroupURL('a~b*c d');
    assert.ok(url2.includes('name=a~b%2Ac%20d'));
});

test('GROUPER_GROUP_PRESETS exact list', () => {
    assert.deepStrictEqual(h.GROUPER_GROUP_PRESETS, [
        { id: 'papercut-staff', label: 'Papercut Staff Include', name: 'Papercut_pcm_staff_include' },
        { id: 'azure-staff', label: 'Azure Staff', name: 'nwu:groups:Azure:Azure_Include_Staff' },
        { id: 'ms-full-staff', label: 'MS Full Staff License', name: 'nwu:groups:mslicenses:msfed_include_full_staff_license' },
        { id: 'ms-activate', label: 'MS Activate', name: 'nwu:groups:mslicenses:ms_activate' },
        { id: 'azure-students', label: 'Azure Students', name: 'nwu:groups:Azure:Azure_Include_Students' },
        { id: 'acrobat', label: 'Acrobat', name: 'nwu:groups:Adobe:Acrobat_fedID_users' },
        { id: 'acrobat-include', label: 'Acrobat Include', name: 'nwu:groups:Adobe:Acrobat_fedID_users_include' },
    ]);
});

test('buildGrouperGroupURL Python parity for all 7 preset names', () => {
    const expected = [
        ['papercut-staff', 'name=Papercut_pcm_staff_include'],
        ['azure-staff', 'name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff'],
        ['ms-full-staff', 'name=nwu%3Agroups%3Amslicenses%3Amsfed_include_full_staff_license'],
        ['ms-activate', 'name=nwu%3Agroups%3Amslicenses%3Ams_activate'],
        ['azure-students', 'name=nwu%3Agroups%3AAzure%3AAzure_Include_Students'],
        ['acrobat', 'name=nwu%3Agroups%3AAdobe%3AAcrobat_fedID_users'],
        ['acrobat-include', 'name=nwu%3Agroups%3AAdobe%3AAcrobat_fedID_users_include'],
    ];
    for (const [presetId, nameSegment] of expected) {
        const preset = h.GROUPER_GROUP_PRESETS.find(p => p.id === presetId);
        assert.ok(preset, `preset ${presetId} exists`);
        const url = h.buildGrouperGroupURL(preset.name);
        assert.ok(url.includes('sourceId=g%3Agsa'), `${presetId} sourceId segment`);
        assert.ok(url.includes(nameSegment), `${presetId} name segment ${nameSegment}`);
    }
});
