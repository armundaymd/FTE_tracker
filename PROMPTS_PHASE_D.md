# ED Capacity Planner — Claude Code Prompt Sequence (Phase D)

Use these prompts in order. Complete each fully before moving to the next.
Each prompt is designed to be pasted directly into Claude Code.

This sequence implements `ROADMAP_PHASE_D.md`. It assumes Phases A, B, and C
(`PROMPTS_PHASE1.5.md`) are already done — Phase D reuses the audit logging
from Phase A and the change-reason pattern from Phase B. Do this **before**
QGenda sync (`ROADMAP.md` Phase 3) — QGenda needs a category-aware time
model to sync into.

---

## Before You Start

Make sure `ROADMAP_PHASE_D.md` is in the project root alongside
`ROADMAP.md` and `ROADMAP_PHASE1.5.md`.

```bash
cd FTE-Scheduler
claude
```

---

## PHASE D — Category-Level Hours

---

### Prompt D.1 — Orient Claude to the target model

```
Before doing anything else, read these files in full:
1. ROADMAP_PHASE_D.md            — the plan for what we're building,
                                     including the exact Excel formulas
                                     this needs to reproduce
2. database/schema.sql            — current schema, in particular the
                                     physicians table (clinical_pct,
                                     yearly_hours, total_fte) and the
                                     v_active_assignments /
                                     capacity views at the bottom
3. backend/routers/physicians.py  — current physician endpoints
4. backend/schemas/physician.py   — current physician schemas

After reading, confirm your understanding of:
- Why clinical_pct is currently a stored, manually-entered value and
  why this phase turns it into a derived value instead
- Exactly how /api/capacity currently uses clinical_pct (trace it
  through v_active_assignments) so we know what must keep working
  unchanged once clinical_pct is computed rather than stored
- The relationship between yearly_hours, total_fte, and the new
  time_allocations concept described in ROADMAP_PHASE_D.md

Do not write any code yet. Just read and summarize back to me,
specifically flagging anything in the current capacity calculation
that you think might break once clinical_pct stops being a static
column value and starts being recalculated.
```

---

### Prompt D.2 — Schema: time_categories and time_allocations

```
Implement the data model from ROADMAP_PHASE_D.md.

1. Add to database/schema.sql:
   - The time_categories table, seeded with exactly these 10 rows
     (name, is_clinical, display_order):
       Adult ED    | true  | 1
       Peds ED     | true  | 2
       P2P         | true  | 3
       VUC         | true  | 4
       IHS         | true  | 5
       Elmhurst    | true  | 6
       Admin       | false | 7
       Nocturnist  | false | 8
       Teaching    | false | 9
       Research    | false | 10
   - The time_allocations table exactly as specified in
     ROADMAP_PHASE_D.md (including the unique constraint on
     physician_id/site_id/time_category_id/year/month, and the index)
   - Add needs_time_allocation_config BOOLEAN NOT NULL DEFAULT TRUE to
     the physicians table (default TRUE, per the migration notes in
     ROADMAP_PHASE_D.md — every existing physician starts flagged since
     no allocation rows exist yet)
   - The v_time_allocation_check view exactly as specified

2. Create backend/models/time_category.py and
   backend/models/time_allocation.py — SQLAlchemy models matching the
   above, following the existing style (see backend/models/leave.py for
   a table with a similar year/month/physician shape).

3. Create backend/schemas/time_allocation.py with:
   - TimeCategoryRead
   - TimeAllocationRead (single row)
   - TimeAllocationGrid — the full year's grid for one physician,
     shaped however makes sense for the bulk endpoints in the next
     prompt (your call on exact shape, but it should be easy for the
     frontend to render as a category × month table)
   - TimeAllocationBulkUpsert — the PUT request body shape from
     ROADMAP_PHASE_D.md

Do not build any endpoints yet — just the schema, models, and Pydantic
schemas. Show me the migration and confirm it applies cleanly against
the current schema.sql.
```

---

### Prompt D.3 — Endpoints and the clinical_pct recalculation

```
Now build the endpoints from ROADMAP_PHASE_D.md:

GET  /api/time-categories
GET  /api/physicians/{id}/time-allocations?year=2026
PUT  /api/physicians/{id}/time-allocations
GET  /api/time-allocations/check?year=2026

Requirements for PUT /api/physicians/{id}/time-allocations:
1. Upsert every row in the request body's allocations array (respecting
   the unique constraint on physician_id/site_id/time_category_id/
   year/month — update hours and change_reason if the row exists,
   insert if not)
2. In the same transaction, after the upsert:
   a. Recalculate this physician's clinical_pct as:
      SUM(hours WHERE time_category.is_clinical) /
      SUM(hours) across all of this physician's time_allocations rows
      for the given year. If the sum is zero, leave clinical_pct
      unchanged (avoid divide-by-zero) rather than erroring.
   b. Recalculate needs_time_allocation_config: TRUE if
      SUM(hours) != yearly_hours for this physician/year, FALSE if it
      matches exactly.
   c. Persist both back to the physicians row.
3. Apply the audit logging helper from Phase A to this endpoint the
   same way it's applied to other mutating endpoints — log old/new
   clinical_pct and needs_time_allocation_config alongside the
   allocation changes.
4. Require admin auth via get_current_user, same as every other
   mutating endpoint.

For GET /api/physicians/{id}/time-allocations, if the physician has no
rows for the requested year, return an empty/zeroed grid (not a 404) —
the frontend will render this as "not yet configured."

After building this, trace through /api/capacity (specifically
v_active_assignments in schema.sql) and confirm it reads
physicians.clinical_pct directly with no other changes needed — it
should now automatically reflect real category data as soon as
clinical_pct is kept in sync by step 2 above. If you find anywhere
that capacity calculation needs an actual code change beyond this,
tell me before making it and explain why.

Show me how to test: PUT a full year of category hours for one test
physician (matching the Excel example — 600 hours Adult ED across the
year, 840 hours Research — should produce clinical_pct ≈ 0.417), then
confirm GET /api/physicians/{id} shows the updated clinical_pct and
needs_time_allocation_config = false.
```

---

### Prompt D.4 — Frontend: Time Allocations grid

```
Now build the frontend for Phase D.

1. Add a new "Time Allocations" tab (nav item + page), following the
   existing pattern in App.jsx (see the NAV/PAGE constants and how
   other tabs like Monthly Demand are structured, since that one is
   probably the closest existing precedent — a grid of numbers by
   month).

2. Layout:
   - A physician selector at the top (reuse PhysicianSearchSelect from
     Phase C1) and a year selector
   - A grid: rows are the 10 time categories from
     GET /api/time-categories (ordered by display_order), grouped
     visually into two sections — Clinical (Adult ED, Peds ED, P2P,
     VUC, IHS, Elmhurst) and Non-clinical (Admin, Nocturnist, Teaching,
     Research) — columns are Jan–Dec, cells are editable number inputs
     for hours
   - Live running totals below the grid, matching the Excel's summary
     rows: Clinical total, Non-clinical total, Total Hrs Check
     (Clinical + Non-clinical), shown against the physician's
     yearly_hours — green checkmark if they match, red with the exact
     variance if not, recalculated live as cells are edited (before
     saving)
   - A "Save" button that sends the whole grid via
     PUT /api/physicians/{id}/time-allocations, with an optional
     "reason for this change" text field applied to any cells that
     changed since load
   - Loading and empty states consistent with the rest of the app —
     an empty grid (physician not yet configured) should be obviously
     editable, not look broken

3. Add a "Needs Configuration" panel or tab section showing physicians
   from GET /api/time-allocations/check where hours_variance != 0,
   with a quick link to jump to that physician's grid.

After this, move on to Prompt D.5 before considering Phase D complete —
there's one more real gap in how leave hours interact with capacity.
```

---

### Prompt D.5 — Leave truncate-vs-makeup option

```
There's a gap between what the backend already supports and what the
Leaves form exposes, worth fixing as part of this phase since it's the
same "how many hours does this physician actually have this month"
math that time_allocations and capacity.py both depend on.

Background (confirm this before changing anything): leaves.fte_during_leave
already exists in the schema and is already read by capacity.py's
_leave_reduction function:
- fte_during_leave = NULL  → full leave: 100% of the overlapping period's
  hours are removed from that month (the physician does not make it up)
- fte_during_leave = a value → partial leave: only
  (1 - fte_during_leave) fraction of hours are removed (the physician is
  covering some or all of the time some other way)

Today, the Leaves form in App.jsx never sets fte_during_leave — every
leave entered through the UI is implicitly a full wipe-out, even though
the backend already supports the partial case. There's no bug in the
math; the gap is purely that the UI never surfaces the choice.

What to build:

1. In the Leaves form (add/edit), add a clear choice — not a buried
   optional field — presented as something like:
     "Will this physician make up these hours?"
     ( ) No — hours are simply reduced for this period (default)
     ( ) Yes — they'll cover it, reduce by a different amount
   If "No" is selected, submit fte_during_leave = null (today's
   default behavior, unchanged).
   If "Yes" is selected, show a numeric input for what fraction of
   their normal time they're still covering during the leave (0-100%,
   stored as fte_during_leave), so partial coverage during a leave
   period is explicit and adjustable, not all-or-nothing.

2. Do NOT change _leave_reduction's math in capacity.py — it already
   does the right thing. This is a frontend-only prompt UNLESS you
   find the leave create/update schemas (schemas/leave.py) don't
   already accept fte_during_leave on write — check first, only add
   backend support if it's actually missing.

3. Update the Leaves tab's summary/list view (the existing
   fte_during_leave != null display logic at App.jsx around line 857)
   so it's clear at a glance which leaves are full wipe-outs vs.
   partial/made-up, not just in the edit form.

4. This interacts with, but is separate from, time_allocations: a
   physician's category-hours grid (Phase D's main work) describes
   their planned mix for the year; leave reductions are applied on top
   of that by capacity.py, not by editing time_allocations rows
   directly. Confirm you understand this separation before changing
   anything, and don't try to make leaves write to time_allocations —
   the two mechanisms are intentionally independent.

Show me how to verify: create a 2-week full leave (no makeup) for a
physician and confirm their available hours for that month drop
correctly in /api/capacity; then create a partial leave (e.g. covering
50% of their normal time) and confirm the reduction is smaller and
proportional, not a full wipe-out.
```

---

After D.5, Phase D is complete. Show me how to verify end-to-end:
select a physician, enter a full year of hours matching a real Excel
row, save, confirm the totals and clinical_pct match what the Excel
computes for that same row, and confirm capacity calculation
(/api/capacity) reflects the change — including the leave-reduction
cases from D.5.

---

## Verification — Full Phase D

```
Phase D is fully implemented. Write backend/tests/test_phase_d.py that:

1. Creates a test physician (yearly_hours = 1440)
2. PUTs a full year of time_allocations matching the Excel's row 2
   example: 600 hours split across Adult ED (clinical), 840 hours in
   Research (non-clinical), evenly across 12 months
3. Confirms GET /api/physicians/{id} shows clinical_pct ≈ 0.4167 and
   needs_time_allocation_config = false
4. Confirms GET /api/time-allocations/check does NOT include this
   physician (their hours balance)
5. PUTs an incomplete year (hours that don't sum to yearly_hours) for
   the same physician and confirms needs_time_allocation_config flips
   back to true and the physician DOES appear in
   /api/time-allocations/check
6. Confirms /api/capacity for this physician's site reflects the
   updated clinical_pct
7. Cleans up all test data
8. Prints PASS/FAIL for each step

Run it with: python backend/tests/test_phase_d.py

Also verify manually:
- The Time Allocations grid renders correctly for a physician with no
  existing data (all zeros, editable)
- Entering hours and saving updates the totals and Total Hrs Check
  live and correctly
- The Needs Configuration list shows the expected physicians and
  shrinks as they're configured
```

---

## Optional — Bulk import from the existing Excel

Only do this if manually re-entering every provider's hours from
`2026-staffing.xlsx` by hand turns out to be too slow. This is optional
and separate from the core Phase D work above.

```
I have the existing staffing spreadsheet at
database/reference/2026-staffing.xlsx (or wherever you've placed it)
with one row per physician and 10 categories × 12 months of hours,
matching the layout described in ROADMAP_PHASE_D.md.

Write a one-time script, backend/scripts/import_time_allocations.py,
that:
1. Reads the workbook with openpyxl (data_only=True, to get computed
   values not formulas)
2. For each row, matches to an existing physician by last_name +
   first_name (print anything that doesn't match cleanly for manual
   review — do not guess)
3. For matched physicians, extracts the Jan–Dec hours for each of the
   10 categories (columns as documented in ROADMAP_PHASE_D.md) and
   calls PUT /api/physicians/{id}/time-allocations with year=2026 and
   change_reason="Imported from 2026-staffing.xlsx"
4. Prints a summary: physicians matched/updated, physicians skipped
   with reasons, any rows where the Excel's own Total Hrs Check column
   didn't match (so we know the source data had existing issues before
   import, not just after)

This is a one-time migration script, not a recurring sync — do not
build this to run automatically or repeatedly.
```

---

## Troubleshooting Prompts

---

### When the Total Hrs Check math looks wrong

```
The Total Hrs Check for physician {name/id} doesn't match what I'd
expect from the Excel.

Excel says: {paste the Excel's values for this row — category hours
and Total Hrs Check}

The app shows: {paste GET /api/physicians/{id}/time-allocations
response and GET /api/physicians/{id} for clinical_pct}

Please check the recalculation logic in the PUT
/api/physicians/{id}/time-allocations endpoint and fix any discrepancy.
```

---

### When capacity numbers change unexpectedly after Phase D

```
After implementing Phase D, /api/capacity results changed for
{site/month/physician}.

Before Phase D: {paste old numbers if you have them, or describe}
After Phase D: {paste new numbers}

Since Phase D is meant to make clinical_pct more accurate (not change
the capacity formula itself), please check whether this is expected
(the physician's real category mix differs from their old stored
clinical_pct) or a bug in how clinical_pct gets recalculated.
```

---

## Git Workflow

```bash
# Phase D complete
git add .
git commit -m "Phase D: category-level time allocations (Adult ED, Research, etc.)"
```

Never commit `.env` files. Check `git status` before every commit.
