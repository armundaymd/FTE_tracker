# ED Capacity Planner — Roadmap Addendum: Phase D (Category-Level Hours)

**Supersedes:** the "Deferred (not scheduled)" note in `ROADMAP_PHASE1.5.md`.
This phase is now scheduled — it comes **after** Phases A–C
(`PROMPTS_PHASE1.5.md`) and **before** QGenda sync
(`ROADMAP.md` Phase 3), because QGenda sync needs a real per-category time
model to sync into, not the current single `clinical_pct` split.

**Why this phase exists:** the app currently stores one number
(`clinical_pct`) per physician. The real staffing grid
(`2026-staffing.xlsx`) tracks **10 categories of time, each broken out by
month**, and derives clinical/non-clinical percentages and FTE from those
category hours rather than storing a percentage directly. This phase
rebuilds the app's time-tracking data model to match.

---

## What the Excel actually does (verified from formulas, not just headers)

Each physician row has 10 category columns, each summing 12 monthly
sub-columns (Jan–Dec):

| Category | Clinical? |
|---|---|
| Adult ED | Yes |
| Peds ED | Yes |
| P2P | Yes |
| VUC | Yes |
| IHS | Yes |
| Elmhurst | Yes |
| Admin | No |
| Nocturnist | No |
| Teaching | No |
| Research | No |

("Buy Down" in the sheet is a subtotal column — `Admin + Nocturnist +
Teaching + Research` — not an 11th category. It's a mislabeled grouping
for "non-clinical total," not literal FTE buy-down.)

Derived values, all computed from the 10 category × 12 month grid:
- **Clinical hours** = Adult ED + Peds ED + P2P + VUC + IHS + Elmhurst
  (each itself `SUM(Jan:Dec)` for that category)
- **Non-clinical hours** = Admin + Nocturnist + Teaching + Research
- **Total Hrs Check** = Clinical + Non-clinical — **must equal** `MSH Hrs`
  (`yearly_hours × site FTE`). This is the sheet's built-in integrity
  check; rows where it doesn't match indicate a data-entry error.
- **MSH cFTE** = `(Clinical hours / yearly_hours) × site FTE`
- **MSH ncFTE** = `(Non-clinical hours / yearly_hours) × site FTE`
- **`clinical_pct`** (the app's current single field) = `Clinical hours /
  (Clinical hours + Non-clinical hours)` — i.e. in the target model,
  `clinical_pct` becomes a **derived** value, not a stored one.

In practice, month-to-month values within a category are usually flat
(an even split of the year), and the real complexity is **when** a
person's category mix changes mid-year (a K-award start, FMLA return,
end of a nocturnist stint) — which is exactly what Phase B's FTE History
already exists to capture for site/role changes, and this phase extends
to category hours too.

---

## Data model changes

### New table: `time_categories`
A lookup table, same pattern as `provider_types` / `role_types`.

```sql
CREATE TABLE time_categories (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(50) NOT NULL UNIQUE,   -- 'Adult ED', 'Peds ED', 'P2P', 'VUC',
                                                   -- 'IHS', 'Elmhurst', 'Admin',
                                                   -- 'Nocturnist', 'Teaching', 'Research'
    is_clinical   BOOLEAN NOT NULL,
    display_order INTEGER NOT NULL
);
```
Seed with the 10 categories above, `is_clinical` set per the table above.
Keep it a lookup table (not a hardcoded enum) so a new category can be
added later without a migration touching application code.

### New table: `time_allocations`
The physician × category × month × hours grid itself.

```sql
CREATE TABLE time_allocations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    physician_id      UUID NOT NULL REFERENCES physicians(id) ON DELETE CASCADE,
    site_id           UUID REFERENCES sites(id),   -- nullable: some categories
                                                     -- (e.g. Research) may not be
                                                     -- site-specific
    time_category_id  INTEGER NOT NULL REFERENCES time_categories(id),
    year              INTEGER NOT NULL,
    month             INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    hours             NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (hours >= 0),
    change_reason     TEXT,                          -- consistent with Phase B
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_time_allocation UNIQUE (physician_id, site_id, time_category_id, year, month)
);

CREATE INDEX idx_time_allocations_physician_year ON time_allocations (physician_id, year);
```

This is intentionally one row per physician/site/category/month rather
than a wide table with 12 month columns — matches the existing schema's
normalized style (see `monthly_demand`) and makes "as of" queries and
partial-year updates straightforward.

### Changes to `physicians`
- Keep `clinical_pct` and `total_fte` as columns (other parts of the app
  and the capacity views still read them), but stop treating them as
  directly editable inputs. Instead:
  - Add a backend job/trigger that recalculates `clinical_pct` for a
    physician whenever their `time_allocations` rows change, using:
    `clinical_pct = SUM(hours WHERE is_clinical) / SUM(hours)` across
    that physician's current-year allocations.
  - If a physician has **no** `time_allocations` rows yet (not yet
    migrated / QGenda-created stub), fall back to the existing stored
    `clinical_pct` value — so this is additive, not a hard cutover.
- Add `needs_time_allocation_config BOOLEAN NOT NULL DEFAULT FALSE` —
  parallel to the existing `needs_fte_config`, flags physicians whose
  category hours don't yet sum to their `yearly_hours × total_fte`
  ("Total Hrs Check" fails), so admins can find and fix them.

### View: recreate the "Total Hrs Check"
```sql
CREATE VIEW v_time_allocation_check AS
SELECT
    p.id AS physician_id,
    p.last_name, p.first_name,
    p.yearly_hours,
    COALESCE(SUM(ta.hours), 0) AS allocated_hours,
    p.yearly_hours - COALESCE(SUM(ta.hours), 0) AS hours_variance
FROM physicians p
LEFT JOIN time_allocations ta
    ON ta.physician_id = p.id AND ta.year = EXTRACT(YEAR FROM CURRENT_DATE)
WHERE p.is_active
GROUP BY p.id, p.last_name, p.first_name, p.yearly_hours;
```
Rows where `hours_variance != 0` are exactly the Excel's "Total Hrs Check"
failures — surfaced as a worklist, not just a per-row visual flag.

---

## Backend

### Endpoints
```
GET    /api/time-categories                          — list lookup values
GET    /api/physicians/{id}/time-allocations?year=2026
                                                       — full category × month
                                                         grid for one physician/year
PUT    /api/physicians/{id}/time-allocations          — bulk upsert
       body: { year, allocations: [
         { time_category_id, site_id, month, hours, change_reason }, ...
       ] }
GET    /api/time-allocations/check?year=2026          — physicians whose
                                                          hours don't sum
                                                          correctly (from
                                                          v_time_allocation_check)
```
- The bulk-upsert endpoint should recalculate and persist `clinical_pct`
  and `needs_time_allocation_config` on the physician row as part of the
  same transaction — don't leave that to a separate step.
- Reuse Phase B's audit-logging helper on every write here, same as every
  other mutating endpoint.
- Reuse Phase B's history pattern loosely: since `time_allocations` is
  already keyed by year/month, a "change" is naturally visible by
  comparing two `PUT`s — no close-and-insert needed here the way it was
  for `site_assignments` (those didn't have a month dimension; this
  table already does). `change_reason` on each row is enough.

### Capacity calculation
`/api/capacity` currently reads `p.clinical_pct` directly (see
`v_active_assignments` in `schema.sql`). No change needed there — once
`clinical_pct` is kept in sync from `time_allocations`, the existing
capacity math automatically reflects real category data without needing
to be rewritten. Confirm this is true rather than assuming — the exact
recalculation trigger matters (see Backend prompt below).

---

## Frontend

- New "Time Allocations" tab (or a section within the provider detail
  view — your call on which reads better, but a dedicated tab probably
  matches the Excel's grid nature better than nesting it).
- A grid UI: rows = the 10 categories (grouped visually into Clinical /
  Non-clinical, matching the Excel), columns = Jan–Dec, editable cells.
  A per-provider selector (reuse Phase C1's `PhysicianSearchSelect`).
- Running totals: Clinical total, Non-clinical total, Total Hrs Check
  (green if it matches `yearly_hours`, red with the variance amount if
  not) — shown live as cells are edited, before saving.
- A "Needs configuration" list (physicians failing the Total Hrs Check),
  reading from `GET /api/time-allocations/check`.

---

## Leave hours: truncate vs. makeup (bundled into this phase)

Separate from `time_allocations` but touching the same "how many hours
does this physician actually have this month" question: `leaves` already
has an `fte_during_leave` column, already correctly read by
`capacity.py`'s `_leave_reduction` — `NULL` means a full wipe-out for the
leave period (hours not made up), a numeric value means only a partial
reduction (they're covering some fraction of their normal time). The
math is already right; the Leaves form in the frontend never exposes the
choice, so every leave entered today is implicitly a full wipe-out.

This phase adds that choice to the Leaves form explicitly — "will this
physician make up these hours?" — rather than leaving it as an unused
backend field. `time_allocations` (this phase's main work) describes a
physician's *planned* category mix for the year; leave reductions are
applied on top of that by `capacity.py`, not by editing
`time_allocations` rows. The two stay intentionally independent — a
leave never modifies category-hours data directly.

---

## Migration for existing data

Physicians currently only have `clinical_pct` — no category breakdown
exists yet. Do **not** attempt to auto-derive category splits from a
single percentage (there's no way to know if 60% clinical came from
Adult ED alone or a mix). Instead:
- Ship this as purely additive: existing `clinical_pct` values keep
  working via the fallback described above until an admin fills in real
  category hours for a physician.
- `needs_time_allocation_config` starts `TRUE` for every currently-active
  physician (no rows exist yet), giving you a natural worklist matching
  the eventual size of the roster.
- No bulk-import script in this phase — filling in the grid by hand per
  provider is the expected path, since the *source* is the Excel you
  already have, not a format the app can read automatically (that's a
  separate, optional prompt below if useful).

---

## Where this leaves QGenda sync (next phase, not part of this one)

Once this phase is done, the physician data model is category/month-aware
the same way QGenda's shift data naturally is — each QGenda shift has a
date and, depending on how your QGenda instance is configured, a
schedule/task type that can map to a `time_category`. That mapping is
the real integration work and depends on details of your QGenda setup
you don't have yet — worth scoping as its own phase once you've explored
the API, rather than guessing the mapping now.
