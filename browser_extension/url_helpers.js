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

    return {
        buildIDMConsolidationURL: buildIDMConsolidationURL,
        buildIDMPasswordURL: buildIDMPasswordURL,
        buildGrouperURL: buildGrouperURL,
        matchesPrefix: matchesPrefix,
        buildSvcpUrl: buildSvcpUrl
    };
}));
