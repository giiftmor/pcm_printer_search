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
        { id: 'papercut-staff', label: 'Papercut Staff Include', name: 'Papercut_pcm_staff_include' },
        { id: 'azure-staff', label: 'Azure Staff', name: 'nwu:groups:Azure:Azure_Include_Staff' },
        { id: 'ms-full-staff', label: 'MS Full Staff License', name: 'nwu:groups:mslicenses:msfed_include_full_staff_license' },
        { id: 'ms-activate', label: 'MS Activate', name: 'nwu:groups:mslicenses:ms_activate' },
        { id: 'azure-students', label: 'Azure Students', name: 'nwu:groups:Azure:Azure_Include_Students' },
        { id: 'acrobat', label: 'Acrobat', name: 'nwu:groups:Adobe:Acrobat_fedID_users' },
        { id: 'acrobat-include', label: 'Acrobat Include', name: 'nwu:groups:Adobe:Acrobat_fedID_users_include' },
    ];

    // keep in sync with modules/user_lookup/urls.py
    function buildGrouperGroupURL(groupName, description) {
        if (typeof groupName !== 'string') return null;
        const name = groupName.trim();
        if (!name) return null;
        const params = new URLSearchParams({
            returnToLinkKey: 'subject.action.return-results',
            typeName: 'group',
            returnTo: '/doSearchSubjects.do',
            name: name,
            subjectType: 'group',
            sourceId: 'g:gsa'
        });
        if (description) params.set('description', description);
        return `${GROUPER_BASE}?${params.toString().replace(/\+/g, '%20').replace(/\*/g, '%2A').replace(/%7E/g, '~')}`;
    }

    return {
        buildIDMConsolidationURL: buildIDMConsolidationURL,
        buildIDMPasswordURL: buildIDMPasswordURL,
        buildGrouperURL: buildGrouperURL,
        matchesPrefix: matchesPrefix,
        buildSvcpUrl: buildSvcpUrl,
        buildGrouperGroupURL: buildGrouperGroupURL,
        GROUPER_GROUP_PRESETS: GROUPER_GROUP_PRESETS
    };
}));
