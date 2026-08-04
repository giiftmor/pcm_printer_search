(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.PCM_URL_HELPERS = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    const IDM_BASE = 'https://idm.nwu.ac.za/profileinfo/profileinfo.jsp';
    const GROUPER_BASE = 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do';

    function buildIDMConsolidationURL(userId) {
        return `${IDM_BASE}?Menu=Consolidation&USN=${encodeURIComponent(userId)}`;
    }

    function buildIDMPasswordURL(userId) {
        return `${IDM_BASE}?Menu=Pwd&USN=${encodeURIComponent(userId)}`;
    }

    function buildGrouperURL(userId) {
        const params = new URLSearchParams({
            returnToLinkKey: 'subject.action.return-results',
            id: userId,
            typeName: 'person',
            returnTo: '/doSearchSubjects.do',
            subjectId: userId,
            name: userId,
            subjectType: 'person',
            sourceId: 'NWUSource'
        });
        return `${GROUPER_BASE}?${params.toString()}`;
    }

    function matchesPrefix(tabUrl, pathPrefix) {
        if (!tabUrl) return false;
        try {
            return new URL(tabUrl).pathname.startsWith(pathPrefix);
        } catch (e) {
            return false;
        }
    }

    // keep in sync with modules/printer_search/svcp.py
    const SVCP_DOMAIN = 'svcp.nwu.ac.za';
    const NWU_SUFFIX = '.nwu.ac.za';
    const LABEL_RE = /^(?!-)[a-z0-9-]{1,63}(?<!-)$/;

    function buildSvcpUrl(hostname) {
        if (typeof hostname !== 'string') return null;
        let name = hostname.trim().toLowerCase();
        if (!name || name.includes('://') || name.includes('/') || /\s/.test(name)) return null;
        const svcpSuffix = '.' + SVCP_DOMAIN;
        if (name.endsWith(svcpSuffix)) {
            name = name.slice(0, -svcpSuffix.length);
        } else if (name.endsWith(NWU_SUFFIX)) {
            name = name.split('.')[0];
        }
        if (!name || name.length > 253) return null;
        for (const label of name.split('.')) {
            if (!LABEL_RE.test(label)) return null;
        }
        return 'https://' + name + '.' + SVCP_DOMAIN;
    }

    const GROUPER_GROUP_PRESETS = [
        { id: 'papercut-staff', label: 'Papercut Staff Include', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=928bd04dcf244ccf8a8a6d61c78dd7b1&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Papercut_pcm_staff_include&subjectId=928bd04dcf244ccf8a8a6d61c78dd7b1&name=nwu%3Agroups%3Apapercut%3APapercut_pcm_staff_include&subjectType=group&sourceId=g%3Agsa' },
        { id: 'azure-staff', label: 'Azure Staff', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=8eed182c75ec4b648b64672d2dd8511a&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Add+extra+staff+to+office+365&subjectId=8eed182c75ec4b648b64672d2dd8511a&name=nwu%3Agroups%3AAzure%3AAzure_Include_Staff&subjectType=group&sourceId=g%3Agsa' },
        { id: 'ms-full-staff', label: 'MS Full Staff License', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=885780297fb64a3c8e568b29c50f68b8&typeName=group&returnTo=%2FdoSearchSubjects.do&description=msfed_include_full_staff_license&subjectId=885780297fb64a3c8e568b29c50f68b8&name=nwu%3Agroups%3Amslicenses%3Amsfed_include_full_staff_license&subjectType=group&sourceId=g%3Agsa' },
        { id: 'ms-activate', label: 'MS Activate', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=bc7da4ab2b0d4e97852f42a343a530c7&typeName=group&returnTo=%2FdoSearchSubjects.do&description=ms_activate&subjectId=bc7da4ab2b0d4e97852f42a343a530c7&name=nwu%3Agroups%3Amslicenses%3Ams_activate&subjectType=group&sourceId=g%3Agsa' },
        { id: 'azure-students', label: 'Azure Students', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=fefea6d36fdc4d12acde72596648d0ba&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Add+extra+students+to+office+365&subjectId=fefea6d36fdc4d12acde72596648d0ba&name=nwu%3Agroups%3AAzure%3AAzure_Include_Students&subjectType=group&sourceId=g%3Agsa' },
        { id: 'acrobat', label: 'Acrobat', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=62d5747d54314b1f96cda7cbc54afdf2&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Acrobat_fedID_users&subjectId=62d5747d54314b1f96cda7cbc54afdf2&name=nwu%3Agroups%3AAdobe%3AAcrobat_fedID_users&subjectType=group&sourceId=g%3Agsa' },
        { id: 'acrobat-include', label: 'Acrobat Include', url: 'https://grp.nwu.ac.za/grouper/populateSubjectSummary.do?returnToLinkKey=subject.action.return-results&id=95653bbe87d646f7829fab2ef82c39e5&typeName=group&returnTo=%2FdoSearchSubjects.do&description=Acrobat_fedID_users_include&subjectId=95653bbe87d646f7829fab2ef82c39e5&name=nwu%3Agroups%3AAdobe%3AAcrobat_fedID_users_include&subjectType=group&sourceId=g%3Agsa' },
    ];

    return {
        buildIDMConsolidationURL: buildIDMConsolidationURL,
        buildIDMPasswordURL: buildIDMPasswordURL,
        buildGrouperURL: buildGrouperURL,
        matchesPrefix: matchesPrefix,
        buildSvcpUrl: buildSvcpUrl,
        GROUPER_GROUP_PRESETS: GROUPER_GROUP_PRESETS
    };
}));
