// PCM Compass - Shared JS

// Admin auth
async function checkAdminStatus() {
    try {
        const res = await fetch('/api/admin/status');
        const data = await res.json();
        return data.is_admin;
    } catch { return false; }
}

async function adminLogin(password) {
    const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `password=${encodeURIComponent(password)}`
    });
    return res.json();
}

async function adminLogout() {
    await fetch('/api/admin/logout', { method: 'POST' });
}

// Message display
function showMessage(container, message, type) {
    container.innerHTML = `<div class="message ${type}">${message}</div>`;
    setTimeout(() => container.innerHTML = '', 5000);
}
