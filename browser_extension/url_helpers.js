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

    return {
        buildIDMConsolidationURL: buildIDMConsolidationURL,
        buildIDMPasswordURL: buildIDMPasswordURL,
        buildGrouperURL: buildGrouperURL,
        matchesPrefix: matchesPrefix
    };
}));
