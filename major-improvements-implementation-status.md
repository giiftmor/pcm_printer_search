# PCM Compass — Major Improvements: Implementation Status

> Living planning + status document for the tests / CI / hardening improvement program.
> Derived from the repository analysis on 2026-08-03.

**Status key:** ✅ Done · 🚧 In progress · ⬜ Not started · ⚠️ Blocked

## Purpose

PCM Compass is a production-deployed internal IT helpdesk toolkit (Flask dashboard + Chrome extension MV3) for the NWU PCM IT Service Desk. It works today, but it has grown without automated safety nets. This document tracks the program to add **automated tests**, **continuous integration**, and **security hardening** so the app can evolve safely.

## Current State Audit (baseline)

### What works today
- Modular Flask app (app factory + blueprints): printer search, quick links, user lookup, extension distribution
- Printer inventory loaded from a Nextcloud-hosted Excel workbook, auto-reloaded every 60s in a background thread
- Chrome extension (MV3) opening NWU services directly — browser-native auth, zero credentials stored
- Docker multi-stage build, non-root user, healthcheck, dev/prod mode switcher (`bin/switch.sh`)
- Extension packaging + Nextcloud WebDAV distribution (`bin/build-extension.sh`)

### Gaps identified
| Area | Current state | Risk |
|------|--------------|------|
| Tests | Partial. `tests/` has pytest suites (quick links, SVCP URL builder/enrichment, `/api/status`) + `node --test` for extension `url_helpers.js`; run via Docker `pcm-test` image (host has no usable Python) | Medium — coverage gaps remain (see Stream 1) |
| CI | None. No GitHub Actions / no lint / no typecheck / no format check | High — nothing gates merges |
| Security | See hardening backlog below | High — see findings |

## Program Structure

Four streams (Stream 0 feature + three remaining). Each becomes its own plan (`.opencode/plans/` or `docs/superpowers/plans/`) executed task-by-task.

### Stream 0 — Feature: Quick Links Categorization ✅

**Goal:** Group quick links into categories across engine, API, web UI, and extension.

- Link inventory expanded from 4 to 14 links across 5 categories: Portals (SCSM, Scopserve), Printing (SVCP, PaperCut), Identity (IDM, Grouper, Entra), SIS Omnia (Password Reset, Profile Overview), NAC (MAN, Campus A/B LAN + WIFI).
- Two-level data model `{"categories": [{id, name, links}]}` with legacy flat-data auto-migration to a "General" category.
- New admin endpoints: `POST /api/links/categories`, `DELETE /api/links/categories/<id>` (409 if non-empty); `POST /api/links` now requires `category_id`.
- Extension popup renders grouped, scrollable Quick Links with matching offline fallback.
- Spec: `docs/superpowers/specs/2026-08-03-quick-links-categorization-design.md`
- Plan: `.opencode/plans/2026-08-03-quick-links-categorization.md`

### Stream 1 — Automated Tests 🚧 (partial)

**Goal:** Confidence that the app behaves correctly and regressions are caught.

Planned work:
- ✅ Add pytest + pytest-cov to `requirements-dev.txt`
- ⬜ Unit tests for `modules/printer_search/engine.py`:
  - URL load/save round-trip (`get_saved_url` / `save_url`)
  - Excel parsing (mock `requests.get` / `pd.read_excel`)
  - `search_all_sheets` — match, no-match, empty-data, multi-sheet concat, `nan` cleanup
  - auto-reload thread behavior (short interval, mock loader)
- ⬜ Unit tests for `modules/user_lookup/urls.py` — URL construction + quoting for the 3 builders
- ✅ Unit tests for `modules/user_lookup/urls.py` grouper group presets — 7 full-URL `{id,label,url}` presets (UUID/subjectId equality, uniqueness, `sourceId=g:gsa`) + `GET /api/user-lookup/grouper-presets` endpoint test (`tests/test_grouper_groups.py`, via Docker `pcm-test`)
- ✅ Unit tests for `modules/quick_links/engine.py` — CRUD, defaults, persistence, legacy migration
- ✅ Unit tests for `modules/printer_search/svcp.py` — `build_svcp_url` hostname sanitization (12 param cases) + `search_all_sheets` `svcp_url` enrichment + non-mutation of input rows (`test_printer_svcp.py`, `test_printer_search_svcp_enrichment.py`)
- ✅ Unit tests for `browser_extension/url_helpers.js` — IDM/Grouper URL builders, `matchesPrefix` tab-reuse matcher (query-string invisible to Chrome match patterns), `buildSvcpUrl` mirroring the Python rules, `GROUPER_GROUP_PRESETS` full-URL list mirroring the Python presets (`tests/url_helpers.test.js`, run via host `node --test`)
- ⬜ Unit tests for `core/auth.py` — hash/check round-trip, `admin_required` guard
- ⬜ Flask integration tests via `app.test_client()`:
  - `POST /api/printer/search` (hit + miss + empty term)
  - `GET /api/printer/last-update`
  - `/api/user-lookup/urls` (valid + missing user_id)
  - ✅ `/api/user-lookup/grouper-presets` (preset shape, 7 full-URL entries matching Python `GROUPER_GROUP_PRESETS`) — `group-url` endpoint removed in v2.3.2 (free-text lookup dropped)
  - ✅ `/api/links` GET/POST/DELETE + category endpoints (incl. admin-required 403)
  - ✅ `GET /api/status` — returns app + extension versions; `app_version` matches the `VERSION` file
  - `/api/admin/login` success/failure, `/api/admin/status`, protected endpoints
  - Page routes render (dashboard, printer-search, quick-links, user-lookup, download-extension)
- ⬜ Templating safety test: assert user-supplied `q` is escaped (no XSS via `?q=` on printer-search)
- ⬜ Test fixture strategy: local sample Excel (multi-sheet) instead of hitting Nextcloud

**Success criteria:** `pytest` green locally and in CI; no network dependency in the test suite.

> **How tests run today (host has no usable Python):** pytest in the Docker `pcm-test` image (`docker run --rm -v "$PWD:/app" -w /app pcm-test bash -c "pip install -q pytest && python -m pytest -p no:cacheprovider -q"`); always append `-p no:cacheprovider` so no root-owned `.pytest_cache` is left on the host volume. Extension JS via host `node --test tests/url_helpers.test.js`.

### Stream 2 — Continuous Integration ⬜

**Goal:** Every change is verified before merge; lint + typecheck + tests run automatically.

Planned work:
- ⬜ Add GitHub Actions workflow (`.github/workflows/ci.yml`) on `push` + `pull_request`:
  - Job: `test` — Python 3.11, install deps, run pytest + coverage report
  - Job: `lint` — ruff (import order, unused imports, formatting)
  - Job: `typecheck` (optional) — mypy on `core/`, `modules/`, `config.py`
- ⬜ Add `pyproject.toml` (ruff/mypy/pytest config) or `.flake8`/`.ruff.toml`
- ⬜ Add `bin/lint.sh` and `bin/test.sh` wrapper scripts (mirror `bin/switch.sh` style)
- ⬜ Optional: build the Docker image in CI to validate the multi-stage build + extension packaging
- ⬜ Enforce branch protection: PRs must pass CI before merge

**Success criteria:** CI runs on every PR; red builds block merge; lint and tests are locally reproducible with one command.

### Stream 3 — Security Hardening ⬜

**Goal:** Reduce attack surface and remove the findings below.

Findings to remediate (prioritized):

1. **P0 — Committed plaintext credential.** `docs/superpowers/plans/2026-07-20-authenticated-redirect.md` contains an NWU password in plaintext (line ~85). Even though the proxy approach was abandoned, the secret lives in git history. **Action:** scrub the file, rewrite git history with `git filter-repo`, coordinate secret rotation with NWU.
2. **P1 — Hardcoded Nextcloud share token.** `bin/build-extension.sh` embeds a default share token. **Action:** require `NEXTCLOUD_SHARE_TOKEN` env var, remove fallback, keep token out of the repo.
3. **P1 — Default admin credentials.** `.env.example`, `core/auth.py` default to `print@NWU`; single password, no username. **Action:** fail hard if `ADMIN_PASSWORD` unset in prod; add username (admin id) + enforce strong password on init; move admin routes under `/admin/` prefix.
4. **P1 — No CSRF protection.** All state-changing endpoints (`/api/admin/*`, `/api/links` POST/DELETE) rely on same-site cookies only. **Action:** enable Flask-WTF CSRF (or `SESSION_COOKIE_SAMESITE="Lax"` + origin check) and enforce on mutating routes.
5. **P1 — No rate limiting / brute-force protection** on `/api/admin/login`. **Action:** add Flask-Limiter (per-IP + per-username backoff), log failed attempts.
6. **P2 — No auth on printer search/read APIs.** Likely acceptable for internal use, but document intended trust boundary (internal-only network) or add optional shared-secret header for server-to-server.
7. **P2 — Admin password hashing is done at startup each boot** (`init_admin_password` re-hashes from env). Fine functionally; document. If a static hash is preferred, store bcrypt hash in env (`ADMIN_PASSWORD_HASH`).
8. **P2 — Session cookie defaults.** Set `SESSION_COOKIE_HTTPONLY=True`, `SAMESITE=Lax`, `SESSION_COOKIE_SECURE=True` behind TLS; `PERMANENT_SESSION_LIFETIME` bounded.
9. **P2 — XSS review.** Results table and quick-links grid inject HTML via innerHTML. Data is helpdesk-internal, but escape/encode or use textContent where feasible; validate `q` param handling.
10. **P2 — Supply chain.** Pin dependency versions (requirements.txt currently uses ranges); add hash-checked lockfile or `pip-tools` + dependabot.
11. **P2 — Docker hardening.** Runs as non-root already (good). Consider `--no-new-privileges`, read-only rootfs where possible, and don't ship `.env.example`/`browser_extension/` source in prod image if unused at runtime.

Also:
- ⬜ Document the security model (which endpoints are public, which are admin-only, trust boundary) in `docs/`.
- ⬜ Rotate the exposed Nextcloud share token and the leaked NWU password (with NWU).

## Execution Workflow

Follow repo conventions established in previous work:
- One plan per stream (`.opencode/plans/YYYY-MM-DD-*.md`) using the superpowers subagent-driven development pattern (task briefs + reports + per-task review).
- Order: **Stream 1 (tests)** → **Stream 2 (CI)** → **Stream 3 (hardening)**. Tests and CI are prerequisites for safely landing hardening changes.
- Every meaningful change updates `CHANGELOG.md` (`[Unreleased]`) and the tailnet-changelog one-liner.
- Verify with `bin/test.sh` + `bin/lint.sh` (to be created) before marking tasks complete.

## Progress Log

| Date | Stream | Item | Status |
|------|--------|------|--------|
| 2026-08-03 | — | Baseline audit + this document | ✅ |
| 2026-08-03 | Stream 0 | Quick Links categorization | ✅ |
| 2026-08-03 | Stream 0 (follow-up) | SVCP as a shared function + printer web links, extension tab-reuse fix, independent app/extension versioning | ✅ |
| 2026-08-03 | Stream 1 | SVCP URL-builder + enrichment tests, `/api/status` test, `url_helpers.js` node tests | ✅ |
| 2026-08-04 | Stream 1 | Grouper group lookup — Python + JS group URL builders + 7 presets, 2 API endpoints, web card, extension popup section (pytest `tests/test_grouper_groups.py` + node `buildGrouperGroupURL`/presets cases) | ✅ |
| 2026-08-04 | Stream 1 (v2.3.2) | Grouper presets → full URLs `{id,label,url}`, free-text lookup removed (`group-url` endpoint dropped), inline App URL settings, reload-nudge banner via `version.json`, "Open app" to footer | ✅ |
