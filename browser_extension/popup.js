const DEFAULT_APP_URL = 'http://196.252.15.214:5000';
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

async function findOrCreateTab(realUrl, opts) {
    let tabs;
    try {
        tabs = await chrome.tabs.query({ url: opts.hostPattern });
    } catch (e) {
        tabs = [];
    }
    const target = tabs.find(t => PCM_URL_HELPERS.matchesPrefix(t.url, opts.pathPrefix));
    if (target) {
        await chrome.tabs.update(target.id, { url: realUrl, active: true });
        await chrome.windows.update(target.windowId, { focused: true });
        return target;
    }
    return chrome.tabs.create({ url: realUrl });
}

async function printerHostPattern() {
    const appUrl = await getAppUrl();
    try {
        return { hostPattern: `*://${new URL(appUrl).hostname}/*`, pathPrefix: '/printer-search' };
    } catch (e) {
        return { hostPattern: '*://*/*', pathPrefix: '/printer-search' };
    }
}

document.getElementById('printerSearchBtn').addEventListener('click', async () => {
    const raw = document.getElementById('printerInput').value.trim();
    if (!raw) return;
    const v = PCM_URL_HELPERS.normalizePrinterHostname(raw) || raw;
    saveHistory(STORAGE_KEYS.printer, v);
    const appUrl = await getAppUrl();
    const p = await printerHostPattern();
    findOrCreateTab(`${appUrl}/printer-search?q=${encodeURIComponent(v)}`, p);
});

document.getElementById('openAppLink').addEventListener('click', async e => {
    e.preventDefault();
    const appUrl = await getAppUrl();
    const p = await printerHostPattern();
    findOrCreateTab(`${appUrl}/printer-search`, p);
});

document.getElementById('printerSvcpBtn').addEventListener('click', () => {
    const v = PCM_URL_HELPERS.normalizePrinterHostname(
        document.getElementById('printerInput').value
    );
    if (!v) {
        alert('Enter a valid printer hostname');
        return;
    }
    const url = PCM_URL_HELPERS.buildSvcpUrl(v);
    if (!url) {
        alert('Invalid printer hostname');
        return;
    }
    saveHistory(STORAGE_KEYS.printer, v);
    findOrCreateTab(url, { hostPattern: '*://*.svcp.nwu.ac.za/*', pathPrefix: '/' });
});

document.getElementById('idmConsolidationBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = PCM_URL_HELPERS.buildIDMConsolidationURL(v);
    findOrCreateTab(url, { hostPattern: '*://idm.nwu.ac.za/*', pathPrefix: '/profileinfo' });
});

document.getElementById('idmPasswordBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = PCM_URL_HELPERS.buildIDMPasswordURL(v);
    findOrCreateTab(url, { hostPattern: '*://idm.nwu.ac.za/*', pathPrefix: '/profileinfo' });
});

document.getElementById('grouperBtn').addEventListener('click', () => {
    const v = document.getElementById('userIdInput').value.trim();
    if (!v) return;
    saveHistory(STORAGE_KEYS.userId, v);
    const url = PCM_URL_HELPERS.buildGrouperURL(v);
    findOrCreateTab(url, { hostPattern: '*://grp.nwu.ac.za/*', pathPrefix: '/grouper/' });
});

function openGrouperGroup(url) {
    if (!url) return;
    findOrCreateTab(url, { hostPattern: '*://grp.nwu.ac.za/*', pathPrefix: '/grouper/' });
}

function renderGrouperGroupChips() {
    const grid = document.getElementById('grouperGroupChips');
    const presets = PCM_URL_HELPERS.GROUPER_GROUP_PRESETS || [];
    grid.innerHTML = presets.map((p, i) =>
        `<button class="chip" data-idx="${i}">${p.label}</button>`
    ).join('');
    grid.querySelectorAll('.chip').forEach(btn => {
        btn.addEventListener('click', () => openGrouperGroup(presets[btn.dataset.idx].url));
    });
}

const DEFAULT_CATEGORIES = [
    { name: 'Portals', links: [
        { name: 'SCSM Support Portal', url: 'https://support.nwu.ac.za/View/HomePage#/', icon: '🎫' },
        { name: 'Scopserve', url: 'http://143.160.36.111:5555/reports/telephony.php', icon: '📞' },
    ] },
    { name: 'Printing', links: [
        { name: 'SVCP Portal', url: 'https://svcp.nwu.ac.za', icon: '🖨️' },
        { name: 'PaperCut Admin Portal', url: 'http://v-pcut-win1.nwu.ac.za:9191/app', icon: '🖨️' },
    ] },
    { name: 'Identity', links: [
        { name: 'IDM', url: 'https://idm.nwu.ac.za', icon: '👤' },
        { name: 'Grouper', url: 'https://grp.nwu.ac.za/grouper/', icon: '👥' },
        { name: 'Microsoft Entra', url: 'https://entra.microsoft.com/#home', icon: '🪪' },
    ] },
    { name: 'SIS (Omnia)', links: [
        { name: 'Omnia Pwd Reset', url: 'https://omnia.nwu.ac.za/omnia/send_sis_password_info', icon: '🔑' },
        { name: 'Omnia Profile', url: 'https://omnia.nwu.ac.za/omnia/get_sis_provisioning_info_page', icon: '📋' },
    ] },
    { name: 'NAC', links: [
        { name: 'MAN NAC', url: 'https://196.252.138.240:8443/gui/hosts/view', icon: '🌐' },
        { name: 'NAC 1 B LAN', url: 'https://196.252.138.242:8443/gui/hosts/adapters', icon: '🏛️' },
        { name: 'NAC 1 B WIFI', url: 'https://196.252.138.241:8443/gui/hosts/view', icon: '📶' },
        { name: 'NAC 2 A LAN', url: 'https://196.252.138.243:8443/gui/hosts/adapters', icon: '🏛️' },
        { name: 'NAC 2 A WIFI', url: 'https://196.252.138.244:8443/gui/hosts/view', icon: '📶' },
    ] },
];

function renderLinks(categories) {
    const grid = document.getElementById('quickLinks');
    grid.innerHTML = categories.map(cat => `
        <div class="link-group">
            <div class="link-group-title">${cat.name}</div>
            <div class="links-grid">${cat.links.map(l => `<a href="${l.url}" target="_blank">${l.icon} ${l.name}</a>`).join('')}</div>
        </div>
    `).join('');
}

async function loadQuickLinks() {
    try {
        const appUrl = await getAppUrl();
        const res = await fetch(`${appUrl}/api/links`);
        const data = await res.json();
        renderLinks(data.categories || DEFAULT_CATEGORIES);
    } catch {
        renderLinks(DEFAULT_CATEGORIES);
    }
}

document.getElementById('printerInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') document.getElementById('printerSearchBtn').click();
});
document.getElementById('userIdInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') document.getElementById('idmConsolidationBtn').click();
});

const settingsPanel = document.getElementById('settingsPanel');
const settingsBtn = document.getElementById('settingsBtn');

function toggleSettings() {
    settingsPanel.classList.toggle('hidden');
    if (!settingsPanel.classList.contains('hidden')) {
        getAppUrl().then(url => { document.getElementById('appUrlInput').value = url; });
    }
}

settingsBtn.addEventListener('click', toggleSettings);

document.getElementById('appUrlSaveBtn').addEventListener('click', () => {
    let url = document.getElementById('appUrlInput').value.trim();
    if (!url) return;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'http://' + url;
    }
    chrome.storage.local.set({ app_url: url }, () => {
        settingsPanel.classList.add('hidden');
        loadQuickLinks();
    });
});

document.getElementById('appUrlResetBtn').addEventListener('click', () => {
    chrome.storage.local.remove('app_url', () => {
        document.getElementById('appUrlInput').value = DEFAULT_APP_URL;
        settingsPanel.classList.add('hidden');
        loadQuickLinks();
    });
});

async function checkReloadNeeded() {
    const manifestVersion = chrome.runtime.getManifest().version;
    try {
        const res = await fetch(chrome.runtime.getURL('version.json'));
        const data = await res.json();
        if (data.version && data.version !== manifestVersion) {
            document.getElementById('reloadBanner').classList.remove('hidden');
        }
    } catch (e) {
        // version.json missing — assume up to date
    }
}

document.getElementById('extVersion').textContent =
    `v${chrome.runtime.getManifest().version}`;

document.getElementById('whatsNewLink').addEventListener('click', e => {
    e.preventDefault();
    chrome.tabs.create({ url: chrome.runtime.getURL('changelog.html') });
});

document.addEventListener('DOMContentLoaded', () => {
    populateDatalist('printer-history', STORAGE_KEYS.printer);
    populateDatalist('user-history', STORAGE_KEYS.userId);
    loadQuickLinks();
    renderGrouperGroupChips();
    checkReloadNeeded();
});
