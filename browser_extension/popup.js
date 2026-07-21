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
    chrome.tabs.create({ url: `${appUrl}/printer-search?q=${encodeURIComponent(v)}` });
});

document.getElementById('printerOpenBtn').addEventListener('click', async () => {
    const appUrl = await getAppUrl();
    chrome.tabs.create({ url: `${appUrl}/printer-search` });
});

document.getElementById('idmConsolidationBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    chrome.tabs.create({ url: buildIDMConsolidationURL(v) });
});

document.getElementById('idmPasswordBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    chrome.tabs.create({ url: buildIDMPasswordURL(v) });
});

document.getElementById('grouperBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    chrome.tabs.create({ url: buildGrouperURL(v) });
});

async function loadQuickLinks() {
    try {
        const appUrl = await getAppUrl();
        const res = await fetch(`${appUrl}/api/links`);
        const links = await res.json();
        const grid = document.getElementById('quickLinks');
        grid.innerHTML = links.map(l => `<a href="${l.url}" target="_blank">${l.icon} ${l.name}</a>`).join('');
    } catch {
        document.getElementById('quickLinks').innerHTML = '<span style="color:#999;font-size:12px;">Could not load links</span>';
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
