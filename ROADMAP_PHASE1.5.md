# ED Capacity Planner — Roadmap Addendum: Phase 1.5

**Supersedes:** the old "Phase 2 — Authentication and Role-Based Access"
section of `ROADMAP.md`. Everything else in `ROADMAP.md` (Phases 3–5)
still applies and comes after this.

**Why this exists:** `ROADMAP.md` was written before Phase 1 was actually
finished. Phase 1 (full CRUD backend + wired frontend) is now essentially
complete — this document reflects what's really built and defines the next
increment: auth with audit trail, FTE history, and three UX gaps
(typeahead search, site editing, filters).

Do these in order: **A → B → C**. Each depends on the one before it.

---

## Current State (as of this doc)

- ✅ FastAPI backend with full CRUD: physicians, site assignments,
  physician roles, leaves, sites, site areas, monthly demand
- ✅ `/api/capacity` calculation engine (leave-adjusted, per site/month)
- ✅ React frontend (`App.jsx`) fully wired to the live API — no hardcoded
  data remains
- ✅ Deployed (Coolify)
- ❌ No auth — anyone with the URL has full read/write access
- ❌ `audit_log` table exists in schema but nothing writes to it
- ❌ `users` table exists in schema but is unused
- ❌ FTE changes overwrite in place — no history of what changed when
- ❌ Physician pickers are plain `<select>` dropdowns — no search
- ❌ Sites can be added/deleted but not renamed or edited
- ❌ No filtering on the Providers list

---

## Phase A — Auth, Roles, and Audit Log

**Goal:** Every write is attributable to a logged-in person. Admins can
log in and manage everything. The permission model is designed now to
support every provider eventually logging in to see their own record —
even though that UI isn't built yet — so it isn't redone later.

### Roles
- `admin` — full read/write everywhere. The only role with UI built in
  this phase.
- `provider` — schema/permission-level support only. Scoped to
  read/write their own `physicians` row (via `users.physician_id`) and
  nothing else. No frontend screens for this role yet.
- `editor` / `viewer` — left in the schema's CHECK constraint for future
  use; no UI or enforcement built for them in this phase.

### Data model changes
- `users.physician_id UUID REFERENCES physicians(id)` — nullable. NULL
  for admin-only accounts; set for any account tied to a specific
  provider.
- Add `'provider'` to the `role` CHECK constraint on `users`.

### Backend
- `POST /api/auth/login` — email + password → JWT access token +
  httpOnly-cookie refresh token
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `get_current_user` dependency applied to all routers; must be able to
  express "row scoped to self" for future `provider`-role use, even
  though nothing calls it that way yet
- Audit logging on every INSERT/UPDATE/DELETE across physicians,
  site_assignments, physician_roles, leaves, sites, site_areas,
  monthly_demand — writes `user_id`, `user_email`, `action`,
  `table_name`, `record_id`, `old_values`, `new_values` to `audit_log`
- `GET /api/audit-log` — filterable by table, user, action, date range
  (admin only)
- Replace the hardcoded `changeme` seed password in `schema.sql` with a
  setup step that requires an env-provided password

### Frontend
- Login screen; access token held in memory, refresh token in httpOnly
  cookie; redirect to login on 401
- App shell shows current user + logout
- New "Audit Log" admin tab, filterable, reading from `GET /api/audit-log`

### Done when
Nothing in the app is visible or editable without logging in. Every
change anywhere shows up in the Audit Log tab with who/what/when.

---

## Phase B — FTE History

**Goal:** FTE-affecting changes are preserved over time, not overwritten,
so "what was Dr. X's FTE at MSH in March?" is answerable and admins can
see *why* something changed.

### Approach (recommended: Option 1)
`site_assignments` and `physician_roles` already have `effective_date` /
`end_date` — they were designed for this but the update endpoints
currently mutate rows in place instead of closing-and-inserting.

- Change `PUT /api/physicians/{id}/assignments/{assignment_id}` (and the
  role equivalent) so that changing `fte_fraction` / `hours_credit` /
  `pct_credit` **closes** the current row (`end_date = day before
  change`) and **inserts** a new row (`effective_date = change date`)
  rather than editing in place.
- Add `change_reason TEXT` (optional) to `site_assignments` and
  `physician_roles`.
- `/api/capacity` can now answer "as of" questions by filtering on
  `effective_date <= X AND (end_date IS NULL OR end_date >= X)`.

**Fallback (Option 2)**, only if the above proves too invasive: add a
separate `fte_history` table written alongside every change, purely for
display, without changing existing update semantics.

### Backend
- Update assignment/role PUT endpoints per Option 1
- `GET /api/physicians/{id}/fte-history` — merged chronological timeline
  of site-assignment changes, role changes, and leaves

### Frontend
- Timeline panel on each provider's detail view
- Optional "reason for change" field when editing an assignment or role's
  FTE-affecting fields

### Done when
Opening any provider shows a dated history of FTE-affecting changes this
year. Capacity can be computed as of a specific date, not just "today."

---

## Phase C — UX Gaps

### C1 — Typeahead provider search
- One reusable `<PhysicianSearchSelect>` component: type partial name,
  see matches, select
- Replaces every plain physician `<select>` (Leaves form, site-assignment
  forms, role forms)
- Client-side filtering against the existing `GET /api/physicians/` list
  is sufficient at current roster size; revisit server-side search only
  if it becomes slow

### C2 — Site editing
- Frontend-only — backend already supports `PATCH /api/sites/{id}` and
  site-area add/remove, just not surfaced in the UI
- Add rename, short_name edit, active toggle, and inline area management
  to the Sites tab

### C3 — Filters
- Providers list filterable by: site, provider type, active/inactive,
  core faculty, needs-FTE-config
- Extend `GET /api/physicians/` with optional query params if not
  already supported; add a filter bar in the frontend

### Done when
No physician picker anywhere is a plain dropdown. Sites can be edited in
place. The Providers tab can be narrowed by any combination of the
filters above.

---

## Deferred (not scheduled)

**Category-level hours** — the source Excel (`2026-staffing.xlsx`) tracks
hours per category per month (Adult ED, Peds ED, P2P, VUC, IHS, Elmhurst,
Buy Down, Admin, Nocturnist, Teaching, Research) rather than the app's
current single `clinical_pct` split. Deliberately not modeled in Phase
A–C. Revisit as its own project later.

---

## After Phase C

Continue with `ROADMAP.md` Phase 3 (QGenda Sync) onward — unchanged,
except note that Phase A's JWT design should make swapping in
institutional SSO later a login-mechanism change, not a permission-model
rewrite.
