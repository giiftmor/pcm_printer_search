# PCM Compass — SCSM Search Skeleton Loaders Design

Date: 2026-08-11
Status: Approved (design discussion)
Predecessor: `docs/superpowers/specs/2026-08-11-scsm-search-ui-ux-improvements-design.md` (the UI/UX redesign this refines — SR/IR chips, status badges, 4-container detail pane).

## 1. Purpose

Replace the textual loading indicators on the SCSM Search page (`/scsm-search`) with row-shaped skeleton loaders that mirror the real result rows.

Two loading states currently show text via the `#scsm-status` bar and a placeholder row:

1. **Initial keyword search** (`doSearch`) — `setStatus('Searching…')`.
2. **Related-tickets role tab** (`loadRoleTickets`, polled every 2s while the cache warms) — `setStatus('Loading related tickets…')` + `renderPlaceholder()` ("Gathering tickets…").

**Scope:** skeletons replace only the *loading* states. Error messages (`Search failed…`, `Related tickets unavailable…`) keep the existing `#scsm-status` text behavior. No backend, API, or test-suite changes.

## 2. Design (Approach A — JS skeleton builder + CSS shimmer)

All changes live in `templates/scsm_search.html` (vanilla JS + scoped CSS, matching the existing pattern used by `ticketRowHtml`).

### 2.1 JS

- **`renderSkeletons(count)`** — replaces `#scsm-results` innerHTML with `count` row-shaped skeleton rows. Each row mirrors a real result row:
  - a chip-sized block (for SR/IR),
  - a title line (medium-width bar),
  - a meta line (small badge block + two text bars).
- Rows are plain `<div class="scsm-skeleton">` (no click handlers), wrapped in `aria-hidden="true"` so assistive tech skips them.
- **Call sites:**
  - `doSearch(q)` — replace `setStatus('Searching…'); clearList();` with `clearList(); renderSkeletons(5);` (status cleared).
  - `loadRoleTickets(role)` — replace `setStatus('Loading related tickets…'); renderPlaceholder();` with `renderSkeletons(3);` (keep the 2s poll loop; tab count `…` unchanged).
  - On success/error, skeletons are replaced by rendered results or the error status text.
- **`renderPlaceholder()` is retired** (its only caller was the role path).

### 2.2 CSS

- `.scsm-skeleton` — block rows using the same `.9rem .9rem` padding + `1px #f0f2f5` bottom border as `.scsm-result`, `border-radius: 8px`.
- Inner bars: light gray `#eef0f2` base with a shimmer animation (`@keyframes` translating a translucent highlight across via `background-position`), rounded corners.
- `@media (prefers-reduced-motion: reduce)` disables the shimmer animation (static gray bars).

### 2.3 Counts

- Initial search: **5** skeleton rows.
- Role-tab loading: **3** skeleton rows.

## 3. Non-goals

- No change to `#scsm-status` / `setStatus()` error behavior.
- No backend, API, or scsm-search changes.
- No test changes (page test only asserts the page renders; skeleton is client-side).
- No new libraries.

## 4. Risks

1. **Skeleton ≠ final content** — rows are placeholders, never clickable; replaced atomically on response. Screen readers skipped via `aria-hidden`.
2. **Poll loop flicker** — role path polls every 2s; skeletons persist across polls until `ready`, so no per-poll flicker.
3. **Reduced motion** — shimmer disabled under `prefers-reduced-motion: reduce`.

## 5. Scope Rollup

- **In:** `renderSkeletons()` helper, CSS skeleton block + shimmer, wiring at both call sites, retire `renderPlaceholder()`.
- **Out:** extension changes, backend/API changes, error-state changes, detail-pane skeleton.
