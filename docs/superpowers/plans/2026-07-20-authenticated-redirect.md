# Authenticated Redirect — Final Decision

**Date:** 2026-07-20
**Decision:** Approach B for everything (in-app proxy)

---

## Background

We explored three approaches for opening IDM/Grouper with pre-filled user IDs:

- **A: Content script injection** — Extension opens login page → content script fills credentials → auto-submits
- **B: Display in-app** — Flask authenticates → fetches profile → returns JSON → extension renders
- **C: Hybrid** — Try A first, fall back to B

## Investigation Results

### IDM (form-based auth)
- Login form at `https://idm.nwu.ac.za/profileinfo/profileinfo.jsp?Menu=Consolidation`
- Form has `UserName` + `Password` fields, auto-submit works
- Content script can fill form and submit
- **Problem:** After auto-submit, authenticated session is isolated to that browser tab. Can't transfer session/cookies to other tabs or the extension.

### Grouper (HTTP Basic Auth)
- Uses HTTP Basic Auth at HAProxy level
- No form to fill — content script injection cannot work
- Must send `Authorization` header on **every request** (cookies alone don't work)
- Grouper WS API returns 404 (not deployed)

### Auth State Isolation
After content script auto-submits the login form:
- The authenticated session exists only in that one browser tab
- Extension can't read or transfer the session cookies
- Can't open other pages with the same authenticated session
- This is a fundamental limitation of the content script approach

## Final Decision

**Use Approach B (in-app proxy) for both IDM and Grouper.**

### How it works:
1. User enters ID in extension popup
2. Extension prompts for PIN
3. Extension decrypts password and sends to Flask
4. Flask authenticates to IDM/Grouper
5. Flask fetches profile data
6. Flask returns JSON
7. Extension renders data in a new tab

### Advantages:
- Reliable — no auth state isolation issues
- Simpler — no content script complexity
- Works for both IDM and Grouper
- Error handling built into Flask

### Disadvantages:
- Profile data displayed in-app, not on the actual IDM/Grouper page
- Requires Flask server to be running

---

## Files

### Backend
- `modules/idm_lookup/engine.py` — IDM form POST auth + Consolidation table parser
- `modules/idm_lookup/routes.py` — `/api/idm/lookup` proxy endpoint
- `modules/grouper/engine.py` — Grouper Basic Auth proxy
- `modules/grouper/routes.py` — `/api/grouper/lookup` proxy endpoint
- `core/auth.py` — AES-GCM credential encryption
- `core/http_client.py` — Shared requests wrapper

### Extension
- `browser_extension/popup.js` — `proxyLookup()` function for in-app display
- `browser_extension/settings.html` — AES-GCM credential encryption
- `browser_extension/manifest.json` — v2.0.0 (no content scripts)

### Templates
- `templates/idm_lookup.html` — In-page results with IDM password fallback
- `templates/grouper.html` — In-page results with badRole error handling

---

## What we learned

1. **NWU password works for both IDM and Grouper** — same `He1!0n3@rth`
2. **Grouper needs `Authorization` header on every request** — cookies alone don't work
3. **Grouper returns `badRole` for our test account** — auth succeeds but no Grouper roles
4. **Grouper WS API not deployed** — returns 404
5. **IDM and Grouper have different backends** — IDM uses form POST, Grouper uses Basic Auth
6. **Content script approach has auth state isolation** — can't transfer session to other tabs
7. **Approach B is more reliable** — no auth state issues, works for both services
