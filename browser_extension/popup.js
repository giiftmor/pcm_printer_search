// Storage keys for autocomplete history
const STORAGE_KEYS = {
  hostname: 'hostname_history',
  pidUser: 'pidUser_history'
};

const APP_URL_KEY = 'app_url';
const DEFAULT_APP_URL = 'http://196.252.43.75:5000';

// Maximum number of autocomplete suggestions to store
const MAX_SUGGESTIONS = 10;

// Current mode: 'svcp' or 'search'
let currentMode = 'svcp';

// Load autocomplete suggestions from localStorage
function loadSuggestions(inputId) {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS[inputId]);
    return stored ? JSON.parse(stored) : [];
  } catch (e) {
    console.error('Error loading suggestions:', e);
    return [];
  }
}

// Save a new suggestion to localStorage
function saveSuggestion(inputId, value) {
  if (!value || value.trim() === '') return;

  let suggestions = loadSuggestions(inputId);
  suggestions = suggestions.filter(item => item !== value);
  suggestions.unshift(value);
  suggestions = suggestions.slice(0, MAX_SUGGESTIONS);

  try {
    localStorage.setItem(STORAGE_KEYS[inputId], JSON.stringify(suggestions));
  } catch (e) {
    console.error('Error saving suggestion:', e);
  }
}

// Populate datalist with suggestions
function populateDatalist(inputId) {
  const suggestions = loadSuggestions(inputId);
  const datalist = document.getElementById(`${inputId}-suggestions`);

  if (!datalist) return;

  datalist.innerHTML = '';
  suggestions.forEach(suggestion => {
    const option = document.createElement('option');
    option.value = suggestion;
    datalist.appendChild(option);
  });
}

// Get the app URL from storage
function getAppUrl() {
  return localStorage.getItem(APP_URL_KEY) || DEFAULT_APP_URL;
}

// Save the app URL to storage
function saveAppUrl(url) {
  const cleanUrl = url.trim().replace(/\/$/, '');
  localStorage.setItem(APP_URL_KEY, cleanUrl);
  return cleanUrl;
}

// Validate and sanitize hostname
function sanitizeHostname(value) {
  return value.toLowerCase().replace(/[^a-z0-9.-]/g, '');
}

// Handle hostname action (SVCP or Search)
async function handleHostnameAction() {
  const input = document.getElementById('hostname');
  const value = sanitizeHostname(input.value.trim());

  if (!value) {
    alert('Please enter a Printer Hostname');
    return;
  }

  saveSuggestion('hostname', value);

  const appUrl = getAppUrl();

  try {
    let tab;

    if (currentMode === 'svcp') {
      // Open SVCP portal
      const url = `https://${value}.svcp.nwu.ac.za`;
      tab = await chrome.tabs.create({ url: url });
    } else {
      // Open web app with search query
      const url = `${appUrl}/?q=${encodeURIComponent(value)}`;
      tab = await chrome.tabs.create({ url: url });
    }

    // Bring entire window to foreground (OS level)
    if (tab && tab.windowId) {
      await chrome.windows.update(tab.windowId, { focused: true });
    }
  } catch (error) {
    console.error('Error opening tab:', error);
    // Fallback
    const url = currentMode === 'svcp'
      ? `https://${value}.svcp.nwu.ac.za`
      : `${getAppUrl()}/?q=${encodeURIComponent(value)}`;
    await chrome.tabs.create({ url: url });
  }
}

// Handle pidUser redirect
async function handlePidUserRedirect() {
  const input = document.getElementById('pidUser');
  const value = input.value.trim();

  if (!value) {
    alert('Please enter a PID User');
    return;
  }

  saveSuggestion('pidUser', value);

  const url = `https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Consolidation&USN=${encodeURIComponent(value)}`;

  try {
    const tabs = await chrome.tabs.query({
      url: 'https://idm.nwu.ac.za/profileinfo/profileinfo.jsp*'
    });

    let tab;
    if (tabs.length > 0) {
      tab = await chrome.tabs.update(tabs[0].id, {
        url: url,
        active: true
      });
    } else {
      tab = await chrome.tabs.create({ url: url });
    }

    // Bring entire window to foreground (OS level)
    if (tab && tab.windowId) {
      await chrome.windows.update(tab.windowId, { focused: true });
    }
  } catch (error) {
    console.error('Error handling tab:', error);
    const tab = await chrome.tabs.create({ url: url });
    if (tab && tab.windowId) {
      await chrome.windows.update(tab.windowId, { focused: true });
    }
  }
}

// Handle toggle pill click
function handleModeToggle(mode) {
  currentMode = mode;

  const pillSVCP = document.getElementById('pill-svcp');
  const pillSearch = document.getElementById('pill-search');
  const hostnameBtn = document.getElementById('hostname-btn');
  const hostnameInput = document.getElementById('hostname');

  if (mode === 'svcp') {
    pillSVCP.classList.add('active');
    pillSearch.classList.remove('active');
    hostnameBtn.textContent = 'Go to SVCP';
    hostnameInput.placeholder = 'Enter Printer Hostname';
  } else {
    pillSearch.classList.add('active');
    pillSVCP.classList.remove('active');
    hostnameBtn.textContent = 'Search Data';
    hostnameInput.placeholder = 'Hostname, Serial, or MAC';
  }
}

// Handle settings toggle
function toggleSettings() {
  const panel = document.getElementById('settingsPanel');
  panel.classList.toggle('hidden');
}

// Handle URL save
function handleUrlSave() {
  const input = document.getElementById('appUrl');
  const statusEl = document.getElementById('urlStatus');
  const url = input.value.trim();

  if (!url) {
    statusEl.textContent = 'Please enter a URL';
    statusEl.className = 'url-status error';
    return;
  }

  const savedUrl = saveAppUrl(url);
  statusEl.textContent = `Saved: ${savedUrl}`;
  statusEl.className = 'url-status success';
}

// Initialize when popup loads
document.addEventListener('DOMContentLoaded', () => {
  // Populate autocomplete suggestions
  populateDatalist('hostname');
  populateDatalist('pidUser');

  // Load saved app URL
  const savedUrl = getAppUrl();
  document.getElementById('appUrl').value = savedUrl;

  // Get DOM elements - Hostname section
  const hostnameInput = document.getElementById('hostname');
  const hostnameBtn = document.getElementById('hostname-btn');
  const pillSVCP = document.getElementById('pill-svcp');
  const pillSearch = document.getElementById('pill-search');

  // Get DOM elements - PID User
  const pidUserInput = document.getElementById('pidUser');
  const pidUserBtn = document.getElementById('pidUser-btn');

  // Get DOM elements - Settings
  const settingsToggle = document.getElementById('settingsToggle');
  const saveUrlBtn = document.getElementById('saveUrl-btn');

  // Add button click handler - Hostname action
  hostnameBtn.addEventListener('click', handleHostnameAction);

  // Add toggle click handlers
  pillSVCP.addEventListener('click', () => handleModeToggle('svcp'));
  pillSearch.addEventListener('click', () => handleModeToggle('search'));

  // Add button click handlers - PID User
  pidUserBtn.addEventListener('click', handlePidUserRedirect);

  // Add button click handlers - Settings
  settingsToggle.addEventListener('click', toggleSettings);
  saveUrlBtn.addEventListener('click', handleUrlSave);

  // Add Enter key handlers - Hostname
  hostnameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleHostnameAction();
  });

  // Add Enter key handlers - PID User
  pidUserInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handlePidUserRedirect();
  });

  // Add Enter key handler - Settings
  document.getElementById('appUrl').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleUrlSave();
  });

  // Focus first input on load
  hostnameInput.focus();
});