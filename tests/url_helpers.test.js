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

test('GROUPER_GROUP_PRESETS exact list', () => {
    assert.deepStrictEqual(h.GROUPER_GROUP_PRESETS, [
        { id: 'papercut-staff', label: 'Papercut Staff Include', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=928bd04dcf244ccf8a8a6d61c78dd7b1&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Papercut_pcm_staff_include&subjectId=928bd04dcf244ccf8a8a6d61c78dd7b1&name=nwu%3Agroups%3Apapercut%3APapercut_pcm_staff_include&subjectType=group&sourceId=g%3Agsa' },
        { id: 'azure-staff', label: 'Azure Staff', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=8eed182c75ec4b648b64672d2dd8511a&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Add+extra+staff+to+office+365&subjectId=8eed182c75ec4b648b64672d2dd8511a&name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff&subjectType=group&sourceId=g%3Agsa' },
        { id: 'ms-full-staff', label: 'MS Full Staff License', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=885780297fb64a3c8e568b29c50f68b8&typeName=group&returnTo=%2FdoSearchSubjects.do&description=msfed_include_full_staff_license&subjectId=885780297fb64a3c8e568b29c50f68b8&name=nwu%3Agroups%3Amslicenses%3Amsfed_include_full_staff_license&subjectType=group&sourceId=g%3Agsa' },
        { id: 'ms-activate', label: 'MS Activate', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=bc7da4ab2b0d4e97852f42a343a530c7&typeName=group&returnTo=%2FdoSearchSubjects.do&description=ms_activate&subjectId=bc7da4ab2b0d4e97852f42a343a530c7&name=nwu%3Agroups%3Amslicenses%3Ams_activate&subjectType=group&sourceId=g%3Agsa' },
        { id: 'azure-students', label: 'Azure Students', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=fefea6d36fdc4d12acde72596648d0ba&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Add+extra+students+to+office+365&subjectId=fefea6d36fdc4d12acde72596648d0ba&name=nwu%3Agroups%3AAzure%3AAzure_Include_Students&subjectType=group&sourceId=g%3Agsa' },
        { id: 'acrobat', label: 'Acrobat', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=62d5747d54314b1f96cda7cbc54afdf2&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Acrobat_fedID_users&subjectId=62d5747d54314b1f96cda7cbc54afdf2&name=nwu%3Agroups%3AAdobe%3AAcrobat_fedID_users&subjectType=group&sourceId=g%3Agsa' },
        { id: 'acrobat-include', label: 'Acrobat Include', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=95653bbe87d646f7829fab2ef82c39e5&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Acrobat_fedID_users_include&subjectId=95653bbe87d646f7829fab2ef82c39e5&name=nwu%3Agroups%3AAdobe%3AAcrobat_fedID_users_include&subjectType=group&sourceId=g%3Agsa' },
    ]);
});

test('GROUPER_GROUP_PRESETS all URLs well-formed', () => {
    assert.strictEqual(h.GROUPER_GROUP_PRESETS.length, 7);
    const ids = new Set();
    for (const p of h.GROUPER_GROUP_PRESETS) {
        assert.ok(p.url.startsWith('https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?'), `${p.id} base`);
        assert.ok(p.url.includes('typeName=group'), `${p.id} typeName`);
        assert.ok(p.url.includes('sourceId=g%3Agsa'), `${p.id} sourceId`);
        assert.ok(p.url.includes('subjectType=group'), `${p.id} subjectType`);
        const uuid = new URL(p.url).searchParams.get('id');
        assert.ok(uuid, `${p.id} uuid`);
        assert.ok(!ids.has(uuid), `${p.id} unique uuid`);
        ids.add(uuid);
    }
});
