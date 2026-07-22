const DEFAULT_APP_URL = 'http://196.252.43.75:5000';
const STORAGE_KEYS = { printer: 'printer_history', userId: 'userId_history' };
const MAX_HISTORY = 10;

function getAppUrl() {
    return new Promise(resolve => {
        chrome.storage.local.get('app_url', data => {
            resolve(data.app_url || DEFAULT_APP_URL);
        });
    });
}

function loadHistory(key) {
    try { return JSON.parse(localStorage.getItem(key)) || []; } catch { return []; }
}

function saveHistory(key, value) {
    if (!value) return;
    let history = loadHistory(key).filter(v => v !== value);
    history.unshift(value);
    history = history.slice(0, MAX_HISTORY);
    localStorage.setItem(key, JSON.stringify(history));
}

function populateDatalist(id, key) {
    const dl = document.getElementById(id);
    dl.innerHTML = '';
    loadHistory(key).forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        dl.appendChild(opt);
    });
}

async function findOrCreateTab(urlPattern, realUrl) {
    const tabs = await chrome.tabs.query({ url: urlPattern });
    if (tabs.length > 0) {
        await chrome.tabs.update(tabs[0].id, { active: true });
        await chrome.windows.update(tabs[0].windowId, { focused: true });
        return tabs[0];
    }
    return chrome.tabs.create({ url: realUrl || urlPattern });
}

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

document.getElementById('printerSearchBtn').addEventListener('click', async () => {
    const v = document.getElementById('printerInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.printer, v);
    const appUrl = await getAppUrl();
    findOrCreateTab(`${appUrl}/printer-search?q=${encodeURIComponent(v)}`);
});

document.getElementById('printerOpenBtn').addEventListener('click', async () => {
    const appUrl = await getAppUrl();
    findOrCreateTab(`${appUrl}/printer-search`);
});

document.getElementById('idmConsolidationBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = buildIDMConsolidationURL(v);
    findOrCreateTab(`*://idm.nwu.ac.za/profileinfo/profileinfo.jsp*USN=${encodeURIComponent(v)}*`, url);
});

document.getElementById('idmPasswordBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = buildIDMPasswordURL(v);
    findOrCreateTab(`*://idm.nwu.ac.za/profileinfo/profileinfo.jsp*USN=${encodeURIComponent(v)}*`, url);
});

document.getElementById('grouperBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = buildGrouperURL(v);
    findOrCreateTab(`*://grp.nwu.ac.za/grouper/populateSubjectSummary.do*${encodeURIComponent(v)}*`, url);
});

const DEFAULT_LINKS = [
    { name: 'SVCP Portal', url: 'https://svcp.nwu.ac.za', icon: '🖨️' },
    { name: 'PaperCut Admin', url: 'https://papercut.nwu.ac.za', icon: '📊' },
    { name: 'IDM', url: 'https://idm.nwu.ac.za', icon: '👤' },
    { name: 'Grouper', url: 'https://grp.nwu.ac.za/grouper/', icon: '👥' },
];

function renderLinks(links) {
    const grid = document.getElementById('quickLinks');
    grid.innerHTML = links.map(l => `<a href="${l.url}" target="_blank">${l.icon} ${l.name}</a>`).join('');
}

async function loadQuickLinks() {
    try {
        const appUrl = await getAppUrl();
        const res = await fetch(`${appUrl}/api/links`);
        const links = await res.json();
        renderLinks(links);
    } catch {
        renderLinks(DEFAULT_LINKS);
    }
}

document.getElementById('printerInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') document.getElementById('printerSearchBtn').click();
});
document.getElementById('userIdInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') document.getElementById('idmConsolidationBtn').click();
});

document.getElementById('settingsBtn').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
});

document.addEventListener('DOMContentLoaded', () => {
    populateDatalist('printer-history', STORAGE_KEYS.printer);
    populateDatalist('user-history', STORAGE_KEYS.userId);
    loadQuickLinks();
});
