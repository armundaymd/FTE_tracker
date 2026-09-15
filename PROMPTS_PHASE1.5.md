# ED Capacity Planner — Claude Code Prompt Sequence (Phase 1.5)

Use these prompts in order. Complete each phase fully before moving to the
next. Each prompt is designed to be pasted directly into Claude Code.

This sequence implements `ROADMAP_PHASE1.5.md`, which supersedes the old
"Phase 2 — Authentication" section of `ROADMAP.md`. Phases 3–5 in the
original `ROADMAP.md` / `PROMPTS.md` are unchanged and still come after
everything here.

---

## Before You Start

Make sure `ROADMAP_PHASE1.5.md` is in the project root alongside the
existing `ROADMAP.md`. Start Claude Code from the project root as usual:

```bash
cd FTE-Scheduler
claude
```

---

## PHASE A — Auth, Roles, and Audit Log

---

### Prompt A.1 — Orient Claude to the current state

```
Before doing anything else, read these files in full:
1. ROADMAP_PHASE1.5.md         — the plan for what we're building next
2. database/schema.sql          — full schema, including the existing
                                   users and audit_log tables
3. backend/main.py               — current app structure and routers
4. backend/routers/physicians.py — an example of current router patterns
5. backend/schemas/physician.py  — an example of current schema patterns

After reading, confirm your understanding of:
- The current auth state (there is none — every endpoint is open)
- The users and audit_log tables already in schema.sql and what's
  missing to actually use them
- The existing router/schema conventions (async SQLAlchemy, Pydantic
  v2 with ConfigDict, UUID primary keys) so new code matches style

Do not write any code yet. Just read and summarize back to me.
```

---

### Prompt A.2 — Auth data model and login endpoints

```
Implement Phase A from ROADMAP_PHASE1.5.md — auth, roles, and audit log.
Start with the data model and login flow.

1. Update database/schema.sql:
   - Add physician_id UUID REFERENCES physicians(id) to the users table
     (nullable — NULL for admin-only accounts, set for accounts tied to
     a specific provider)
   - Update the role CHECK constraint on users to allow
     ('admin','editor','viewer','provider')
   - Remove the hardcoded seed admin user with the "changeme" password.
     Instead, write a note in schema.sql that the admin user must be
     created via a setup script (build this script next)

2. Create backend/models/user.py — SQLAlchemy model matching the
   updated users table, following the same style as
   backend/models/physician.py

3. Create backend/schemas/auth.py with Pydantic schemas for:
   - LoginRequest (email, password)
   - TokenResponse (access_token, token_type, expires_in)
   - UserRead (id, name, email, role, physician_id)

4. Create backend/routers/auth.py:
   POST /api/auth/login    — verify email/password against
                              users.hashed_password (bcrypt via passlib),
                              return a JWT access token; set a refresh
                              token in an httpOnly cookie
   POST /api/auth/refresh  — issue a new access token from a valid
                              refresh cookie
   POST /api/auth/logout   — clear the refresh cookie
   GET  /api/auth/me       — return the current user from a valid
                              access token

5. Create backend/auth/dependencies.py with a get_current_user
   dependency (FastAPI Depends) that:
   - Extracts and validates the JWT from the Authorization header
   - Returns the current user (id, role, physician_id)
   - Raises 401 if missing/invalid/expired
   - Is written so a future "scoped to own physician_id" check is a
     small addition, not a rewrite — for now, only admin-role checks
     need to actually be enforced anywhere

6. Create backend/scripts/create_admin.py — a standalone script that
   prompts for (or reads from env vars ADMIN_EMAIL / ADMIN_PASSWORD /
   ADMIN_NAME) an admin user's details, hashes the password with bcrypt,
   and inserts the user row. Print clear usage instructions.

7. Add to requirements.txt if not already present:
   python-jose[cryptography]
   passlib[bcrypt]

8. Add to .env.example:
   SECRET_KEY=replace_with_64_random_chars
   ACCESS_TOKEN_EXPIRE_MINUTES=480
   REFRESH_TOKEN_EXPIRE_DAYS=14

9. This app runs in two environments off the same codebase: locally via
   docker-compose.yml (http://localhost) and in production via
   docker-compose.coolify.yml (https://capacity.adamrmunday.com,
   api-capacity.adamrmunday.com). Do not hardcode either environment:
   - Read the refresh-token cookie's Secure and SameSite settings from
     an env var (e.g. COOKIE_SECURE=false in .env.example, true in
     prod) rather than hardcoding either. Secure=true cookies won't be
     sent over local http://localhost, so this must be togglable.
   - Do not hardcode a cookie `domain` — omit it so the cookie defaults
     to the request's own host, which works for both environments
     without changes.
   - Confirm ALLOWED_ORIGINS (already read from env in main.py) is what
     governs which frontend origins can call the API — do not add any
     new hardcoded origin checks.
   Add COOKIE_SECURE=false to .env.example with a comment that it must
   be true in the Coolify/production environment.

Do not protect any other endpoints yet — that's the next prompt. Just
get login, token issuance, and the admin-creation script working, and
show me how to test /api/auth/login with curl.
```

---

### Prompt A.3 — Protect existing endpoints with admin auth

```
Now apply get_current_user (from backend/auth/dependencies.py) to every
existing router: physicians, sites, leaves, demand, capacity.

Requirements:
- Every route in these routers requires a valid JWT
- For this phase, any authenticated user with role='admin' has full
  access to all of them — do not build editor/viewer/provider
  enforcement logic yet, just require admin for all writes and reads
- Return 401 for missing/invalid token, 403 if the token is valid but
  the role isn't admin
- Update main.py CORS config if needed so the frontend can send the
  Authorization header and receive/send cookies (allow_credentials=True
  should already be set — confirm)

After this, every endpoint in Swagger docs (/docs) should show a lock
icon and require a bearer token to try. Show me how to get a token via
/api/auth/login and use it to call GET /api/physicians/ successfully,
and confirm it fails with 401 without a token.
```

---

### Prompt A.4 — Audit log

```
Now implement the audit log — the second half of Phase A.

1. Create backend/models/audit_log.py matching the audit_log table in
   schema.sql

2. Create backend/audit/logger.py with a reusable helper, e.g.
   log_audit(db, user, action, table_name, record_id, old_values,
   new_values) that writes a row to audit_log. old_values/new_values
   should be JSON-serializable dicts (use Pydantic's model_dump or
   similar to snapshot before/after state).

3. Wire this helper into every mutating endpoint (POST, PUT, PATCH,
   DELETE) in the physicians, sites, leaves, and demand routers:
   - INSERT: log new_values only
   - UPDATE: log both old_values and new_values (capture the row's
     state before applying changes)
   - DELETE: log old_values only
   - Use the current user from get_current_user for user_id/user_email

4. Add GET /api/audit-log (admin only) with optional query params:
   ?table_name=&user_id=&action=&start_date=&end_date=
   Return most-recent-first, paginated (limit/offset, default limit 50).

5. Add a schemas/audit_log.py with an AuditLogRead schema.

After this, walk me through a manual test: create a physician, update
it, delete it, then call GET /api/audit-log and confirm all three
actions appear with correct old_values/new_values.
```

---

### Prompt A.5 — Frontend: login screen and app shell

```
Now build the frontend side of Phase A.

1. Add a login screen to frontend/src/App.jsx (or split into a new
   component file if that's cleaner — your call, but keep the existing
   visual style: dark sidebar, same fonts/colors as the rest of the app):
   - Email + password fields, login button
   - Show a clear error message on failed login
   - On success, store the access token in React state (in memory, NOT
     localStorage) and show the main app

2. Update the existing apiFetch helper (used throughout App.jsx) to:
   - Attach "Authorization: Bearer {token}" to every request
   - Include credentials so the refresh-token cookie is sent
   - On a 401 response, attempt POST /api/auth/refresh once; if that
     also fails, clear the token and show the login screen

3. Add to the app shell (top bar or sidebar):
   - Current user's name/email (from GET /api/auth/me)
   - A logout button that calls POST /api/auth/logout and clears state

4. Gate the entire app: if there's no valid token, only the login
   screen renders — no tab content, no API calls.

Keep this frontend-only change scoped to auth plumbing — don't touch
the Providers/Sites/Leaves/Demand tab logic in this prompt.
```

---

### Prompt A.6 — Frontend: Audit Log tab

```
Add a new "Audit Log" tab to the app, visible only when logged in as
admin (which, for now, is everyone who can log in — but write the check
as if(user.role === "admin") so it's correct once other roles exist).

Requirements:
- New NAV entry and PAGE entry following the existing pattern in
  App.jsx (see the NAV and PAGE constants)
- Table showing: timestamp, user email, action, table changed, and a
  short human-readable summary of what changed (e.g. derive from
  old_values/new_values — you decide a reasonable summary format)
- Filter bar above the table: table name (dropdown), action (dropdown:
  INSERT/UPDATE/DELETE), date range (two date inputs)
- Reads from GET /api/audit-log with the filters as query params
- Reasonable empty state and loading state, matching the style of
  other tabs in the app

After this, Phase A is complete. Tell me how to fully verify it:
creating a user via the admin script, logging in, making a change in
any tab, and confirming it shows up correctly in the Audit Log tab.
```

---

## PHASE B — FTE History

---

### Prompt B.1 — Close-and-insert semantics for assignments and roles

```
Implement Phase B from ROADMAP_PHASE1.5.md — FTE history — using
Option 1 (the recommended approach): make the existing effective_date /
end_date columns on site_assignments and physician_roles function as a
real history, instead of adding a separate history table.

1. Add change_reason TEXT (nullable) to both site_assignments and
   physician_roles in schema.sql, and to the matching SQLAlchemy models
   and Pydantic schemas.

2. Change the behavior of:
   PUT /api/physicians/{id}/assignments/{assignment_id}
   — when the request changes fte_fraction (or site_id), do NOT update
   the existing row in place. Instead:
     a. Set end_date = day before the new effective date on the
        existing row (default new effective date = today, unless the
        request specifies one)
     b. Insert a new site_assignments row with the new fte_fraction,
        effective_date = the date from (a), end_date = NULL,
        change_reason = from the request body if provided
   — if the request ONLY changes notes or change_reason (nothing
   FTE-affecting), it's fine to update the existing row in place —
   don't create history noise for non-substantive edits.

3. Apply the same close-and-insert logic to the physician_roles
   equivalent endpoint for hours_credit / pct_credit changes.

4. Update the relevant Pydantic *Update schemas to accept an optional
   change_reason and an optional effective_date for the change.

5. Confirm /api/capacity continues to work correctly — it should now
   naturally reflect whichever row is active in the requested month
   (it already filters on end_date IS NULL for "current", but check
   whether it needs a date-aware filter for past months within the
   requested year — if a physician's FTE changed mid-year, capacity for
   earlier months in that same year should reflect the value that was
   effective in those months, not just whatever's active today).

Show me how you handled the mid-year capacity correctness question in
step 5 specifically, and how to test it: create an assignment, change
its FTE mid-year, and confirm GET /api/capacity?year=2026 shows the old
value for earlier months and the new value for later months.
```

---

### Prompt B.2 — FTE history endpoint

```
Add GET /api/physicians/{id}/fte-history that returns a single merged,
chronological timeline combining:
- site_assignments (all rows, not just currently-active, ordered by
  effective_date) — including change_reason
- physician_roles (all rows, ordered by effective_date) — including
  change_reason
- leaves for that physician (ordered by start_date)

Each entry in the response should have a consistent shape so the
frontend can render one timeline without knowing which source table it
came from — something like:
  { date, type: "assignment" | "role" | "leave", description,
    change_reason, detail: {...the original fields...} }

Write the "description" field as a short human-readable summary (e.g.
"MSH assignment changed from 0.5 to 0.75 FTE", "Started FMLA leave",
"Added role: K Awardee (20% credit)").

Add a schemas/fte_history.py with the response schema.

Show me an example response for a physician with at least one
assignment change and one leave.
```

---

### Prompt B.3 — Frontend: FTE history timeline and change-reason field

```
Now build the frontend for Phase B.

1. On the provider detail view (wherever a single physician's full
   record is currently shown/edited in App.jsx), add a "History"
   section: a vertical timeline of entries from
   GET /api/physicians/{id}/fte-history, each showing the date, a short
   description, and the change_reason if present. Style it consistently
   with the rest of the app (reuse existing card/list styles).

2. When editing a site assignment's fte_fraction, or a role's
   hours_credit/pct_credit, add an optional "Reason for change" text
   input to the edit form. Send it as change_reason in the update
   request.

After this, Phase B is complete. Tell me how to verify: change a
provider's site FTE with a reason, then confirm it shows up in their
History timeline with that reason, and confirm the old FTE value is
still correctly reflected in past months via /api/capacity.
```

---

## PHASE C — UX Gaps

---

### Prompt C.1 — Typeahead provider search component

```
Implement Phase C1 from ROADMAP_PHASE1.5.md.

Build one reusable component, PhysicianSearchSelect, in
frontend/src/ (new file is fine) that:
- Takes the full physicians list (already loaded in App.jsx state) and
  a selected physician_id + onChange callback as props
- Renders a text input; as the user types, filters physicians by
  partial match on first_name + last_name (case-insensitive, matches
  anywhere in either name, not just prefix)
- Shows a dropdown of matching results below the input as they type
- Selecting a result sets the value and closes the dropdown
- Shows the currently-selected physician's name in the input when not
  actively searching
- Keyboard accessible: arrow keys to move through results, Enter to
  select, Escape to close
- Match the existing visual style of inputs/dropdowns in the app

Then replace every plain physician <select> in App.jsx with this
component:
- The Leaves form (physician_id field)
- The site-assignment form (if physician is selected there)
- The role-assignment form (if physician is selected there)
- Any other physician picker you find while doing this

Show me a list of every place you swapped in the new component, and
confirm existing add/edit flows in Leaves still work end-to-end.
```

---

### Prompt C.2 — Site editing

```
Implement Phase C2 from ROADMAP_PHASE1.5.md.

This should be frontend-only — confirm backend/routers/sites.py already
supports PATCH /api/sites/{id} and POST/DELETE
/api/sites/{id}/areas/{area_id} before writing any backend code. If
something needed is missing, add it, but check first.

Update the Sites tab in App.jsx:
1. Each site row becomes editable in place (or via a modal — your
   call, match whatever pattern the app already uses elsewhere for
   editing, e.g. how physicians are edited) allowing changes to:
   - name
   - short_name
   - active (toggle)
2. Inline management of site areas per site:
   - Show existing areas as removable tags (reuse the .rtag style
     already used elsewhere in the app)
   - An "add area" input + button per site
3. Saves call the existing PATCH/area endpoints and refresh the list.

Show me how to verify: rename a site, toggle it inactive and back,
add an area, remove an area — confirm all persist after a page reload.
```

---

### Prompt C.3 — Provider filters

```
Implement Phase C3 from ROADMAP_PHASE1.5.md.

1. Check backend/routers/physicians.py's list_physicians endpoint —
   confirm whether it already accepts query params for site, provider
   type, active status, core faculty, or needs_fte_config. Add whatever
   is missing as optional query params on GET /api/physicians/:
   ?site_id=&provider_type_id=&is_active=&is_core_faculty=&needs_fte_config=
   (Note: site is a join through site_assignments — filtering by site
   means "has an active assignment at this site.")

2. In the frontend Providers tab, add a filter bar above the table:
   - Site (dropdown, from the sites already loaded)
   - Provider type (dropdown, from the lookup-tables endpoint)
   - Status (All / Active / Inactive)
   - Core faculty (All / Core / Non-core)
   - Needs FTE config (checkbox — show only flagged)
   Filters combine (AND, not OR). Persist filter state in component
   state (does not need to survive a page reload).

3. Show the count of matching providers ("Showing 12 of 45") above the
   table.

After this, Phase C is complete. Show me how to verify each filter
individually and in combination.
```

---

## Verification — Full Phase 1.5

```
Phase A, B, and C are all implemented. Write a verification script,
backend/tests/test_phase1_5.py, that:

1. Creates an admin user (or uses one already seeded)
2. Logs in and gets a token
3. Confirms an unauthenticated request to GET /api/physicians/ returns
   401
4. Creates a physician, a site assignment, and a role — confirms each
   appears in GET /api/audit-log
5. Updates the site assignment's fte_fraction — confirms via
   GET /api/physicians/{id}/fte-history that both the old and new
   assignment rows appear correctly
6. Confirms GET /api/capacity?year=<current year> still returns correct
   results after the history change in step 5
7. Cleans up all test data it created
8. Prints PASS/FAIL for each step

Run it with: python backend/tests/test_phase1_5.py

Also verify manually and tell me what to look for:
- Logging in and out works and the app is fully gated behind login
- The Audit Log tab shows real entries with correct old/new values
- A provider's History timeline shows FTE changes with reasons
- Every physician picker in the app is now a searchable typeahead
- A site can be renamed and have areas added/removed without deleting it
- The Providers tab filters work individually and combined
```

---

## Troubleshooting Prompts

Use these whenever something breaks — same as the Phase 1 sequence.

---

### When a Docker service won't start

```
The {service name} Docker service is failing to start.
Here is the error output:

{paste the full error here}

Please diagnose the issue and fix it. Show me the exact
commands to restart after your fix.
```

---

### When an API endpoint returns an error

```
The {endpoint} endpoint is returning an error.

Request:
{paste the request details — method, URL, body, headers}

Response:
{paste the full response including status code and body}

Error in the backend logs:
{paste any traceback from docker logs backend}

Please fix the issue.
```

---

### When auth is misbehaving

```
{Describe the symptom — e.g. "I get logged out immediately after
logging in", "refresh token isn't working", "getting 403 when I should
get 200"}

Here's what I did:
{steps to reproduce}

Here's the response I got:
{paste response/status code}

Here's the relevant backend log output:
{paste logs}

Please diagnose whether this is a token expiry issue, a cookie/CORS
issue, or a role-check bug, and fix it.
```

---

### When the FTE history timeline looks wrong

```
The FTE history for physician {name/id} doesn't look right.

Here's what GET /api/physicians/{id}/fte-history returned:
{paste response}

Here's what I expected:
{describe the expected sequence of changes}

Please check whether this is a close-and-insert bug in the assignment/
role update endpoints, or a rendering bug in the frontend timeline, and
fix it.
```

---

## Git Workflow

Run these after each phase completes successfully:

```bash
# Phase A complete
git add .
git commit -m "Phase A: auth, roles, and audit log"

# Phase B complete
git add .
git commit -m "Phase B: FTE history via close-and-insert assignments/roles"

# Phase C complete
git add .
git commit -m "Phase C: typeahead search, site editing, provider filters"
```

Never commit `.env` or `.env.local` files. Check `git status` before
every commit — the existing `.gitignore` should already exclude `.env`,
`__pycache__/`, `node_modules/`, and `dist/`; confirm rather than assume.

**After Phase A specifically:** pushing to GitHub does not update the
running Hetzner/Coolify deployment's environment variables — those are
set separately in the Coolify UI. Before (or right after) that push,
add every new var introduced in Prompt A.2 (SECRET_KEY,
ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, COOKIE_SECURE,
ADMIN_EMAIL/ADMIN_PASSWORD/ADMIN_NAME for the create_admin script) to
Coolify's environment settings for the backend service — with
COOKIE_SECURE=true there, unlike local. Then run create_admin.py
against production once, the same way you'll run it locally.
