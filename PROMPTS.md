# FTE-Scheduler — Claude Code Prompt Sequence

Use these prompts in order. Complete each phase fully before moving to the next.  
Each prompt is designed to be pasted directly into Claude Code.

---

## Before You Start

Make sure your folder structure looks like this:

```
FTE-Scheduler/
├── frontend/        ← your Vite React app (App.jsx is here)
├── database/
│   └── schema.sql   ← the PostgreSQL schema file
├── ROADMAP.md
└── PROMPTS.md       ← this file
```

Open your terminal, navigate to the project folder, and start Claude Code:

```bash
cd FTE-Scheduler
claude
```

---

## PHASE 1 — Full-Stack Foundation

---

### Prompt 1.1 — Orient Claude to the project

```
I am building a web application called the ED Capacity Planner for 
tracking emergency medicine physician and APP workforce capacity 
across multiple hospital sites at Mount Sinai Health System.

Before doing anything else, please read these two files in full:
1. frontend/src/App.jsx     — the complete React prototype
2. database/schema.sql      — the full PostgreSQL schema

After reading both files, give me a summary of:
- The data model (what entities exist and how they relate)
- What the app currently does in the prototype
- What will need to change when we connect it to a real backend

Do not write any code yet. Just read and summarize.
```

---

### Prompt 1.2 — Scaffold the backend

```
Now scaffold the FastAPI backend. Create the following folder structure 
inside /backend:

backend/
├── main.py              ← FastAPI app entry point
├── db.py                ← database connection (SQLAlchemy async)
├── models/
│   ├── __init__.py
│   ├── physician.py
│   ├── site.py
│   ├── leave.py
│   └── demand.py
├── schemas/
│   ├── __init__.py
│   ├── physician.py
│   ├── site.py
│   ├── leave.py
│   └── demand.py
├── routers/
│   ├── __init__.py
│   ├── physicians.py
│   ├── sites.py
│   ├── leaves.py
│   ├── demand.py
│   └── capacity.py
├── requirements.txt
└── .env.example         ← template for secrets, never the real .env

Use these dependencies in requirements.txt:
  fastapi
  uvicorn[standard]
  sqlalchemy[asyncio]
  asyncpg
  pydantic
  pydantic-settings
  python-dotenv
  passlib[bcrypt]
  python-jose[cryptography]
  httpx
  rapidfuzz

The database connection in db.py should use asyncpg with SQLAlchemy 
async session. Read the schema.sql to get the exact table and 
column names — match them exactly.

Do not create any endpoints yet. Just scaffold the structure, 
models, and database connection.
```

---

### Prompt 1.3 — Build the CRUD endpoints

```
Now build the API endpoints. Implement all routes in the routers/ 
folder based on the data model in database/schema.sql.

Required endpoints:

Sites:
  GET    /api/sites                     — list all active sites
  POST   /api/sites                     — create a site
  DELETE /api/sites/{id}                — deactivate a site

Physicians:
  GET    /api/physicians                — list all (filter: ?active=true, ?type=MD)
  POST   /api/physicians                — create a physician
  GET    /api/physicians/{id}           — get one physician with assignments and roles
  PUT    /api/physicians/{id}           — update a physician
  DELETE /api/physicians/{id}           — deactivate (soft delete, set is_active=false)
  POST   /api/physicians/{id}/assignments — add site assignment
  PUT    /api/physicians/{id}/assignments/{assignment_id} — update assignment
  DELETE /api/physicians/{id}/assignments/{assignment_id} — remove assignment
  POST   /api/physicians/{id}/roles     — add role
  DELETE /api/physicians/{id}/roles/{role_id} — remove role

Leaves:
  GET    /api/leaves                    — list all leaves (filter: ?physician_id=, ?year=)
  POST   /api/leaves                    — create a leave
  PUT    /api/leaves/{id}               — update a leave
  DELETE /api/leaves/{id}               — delete a leave

Monthly demand:
  GET    /api/demand?year=2026          — get all demand for a year
  PUT    /api/demand                    — upsert demand (body: {site_id, year, month, hours_required})

Capacity:
  GET    /api/capacity?year=2026        — monthly capacity for all sites
  GET    /api/capacity?year=2026&site_id={uuid} — filtered by site

The capacity endpoint is the most important. It must:
1. For each month of the requested year, for each site:
   - Sum available hours from active physicians with site assignments
   - Reduce availability proportionally for any leave events that 
     overlap that month (overlap days / days in month)
   - Return: available_hours, clinical_hours, non_clinical_hours,
     required_hours, hours_gap, available_fte, required_fte, fte_gap
2. Accept an optional site_id filter
3. Use the v_active_assignments view from the schema for base data

After building endpoints, also add CORS middleware to main.py 
so the React frontend (running on localhost:5173) can call the API.
```

---

### Prompt 1.4 — Docker Compose

```
Create a docker-compose.yml in the project root that runs three 
services together:

1. postgres
   - Image: postgres:16
   - Database name: ed_capacity
   - User: postgres
   - Password: from environment variable POSTGRES_PASSWORD
   - Mount the database/schema.sql to auto-run on first start
   - Persist data with a named volume
   - Port: 5432

2. backend
   - Build from ./backend/Dockerfile (create this too)
   - Depends on postgres being healthy
   - Port: 8000
   - Environment variables from .env file
   - Hot reload in development (mount the source directory)
   - Run command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

3. frontend
   - Build from ./frontend/Dockerfile (create this too)
   - Depends on backend
   - Port: 5173
   - Mount the source directory for hot reload
   - Run command: npm run dev -- --host

Also create:
- backend/Dockerfile (Python 3.12 slim base)
- frontend/Dockerfile (Node 20 alpine base)
- .env.example with all required variables:
    POSTGRES_PASSWORD=changeme
    DATABASE_URL=postgresql+asyncpg://postgres:changeme@postgres:5432/ed_capacity
    SECRET_KEY=changeme_replace_with_random_64_char_string

Do NOT create the actual .env file — just the .env.example.
Tell me exactly what commands to run to start everything up.
```

---

### Prompt 1.5 — Connect the frontend to the API

```
Now update the React frontend (frontend/src/App.jsx) to call the 
real API instead of using in-memory state.

The API is running at http://localhost:8000/api.

Replace all useState with initial empty/null values and add 
useEffect hooks to load data from the API on mount.

Specifically:
1. On app load: fetch sites, physicians, leaves, and demand from API
2. All add/edit/delete actions should call the API and then 
   refresh the relevant data
3. Add a loading state (spinner or skeleton) while data is fetching
4. Add error handling — if an API call fails, show a clear error 
   message in the UI rather than crashing
5. The capacity calculation should now come from 
   GET /api/capacity?year=2026 — remove the client-side 
   calculation logic entirely

Keep the UI identical to the current prototype. Only the data 
layer changes.

After updating the frontend, tell me how to verify everything 
is working correctly end-to-end.
```

---

### Prompt 1.6 — Verify Phase 1

```
Phase 1 is almost done. Please write a verification script that 
tests the complete API end-to-end.

Create backend/tests/test_api.py that:
1. Creates a test site
2. Creates a test physician assigned to that site
3. Adds a role to that physician
4. Creates a leave event for next month
5. Fetches capacity for the current year and verifies the leave 
   reduces the available hours correctly
6. Deletes all the test data it created
7. Prints a clear PASS or FAIL for each step

Run it with: python backend/tests/test_api.py

Also verify these things manually and tell me what to look for:
- Docker Compose starts without errors
- Frontend loads at localhost:5173
- Dashboard shows data from the database
- Adding a physician in the UI creates a row in the database
- Refreshing the browser preserves all data
```

---

## PHASE 2 — Authentication

---

### Prompt 2.1 — Build authentication

```
Phase 1 is working. Now build Phase 2 — authentication.

Add to the backend:

1. JWT login endpoint:
   POST /api/auth/login
   Body: { email, password }
   Returns: { access_token, token_type, expires_in }
   Uses bcrypt to verify password against hashed_password in users table

2. Token refresh endpoint:
   POST /api/auth/refresh
   Returns a new token if the current one is still valid

3. Auth middleware:
   - All /api routes except /api/auth/login require a valid JWT
   - Invalid or expired token returns HTTP 401
   - Extract user_id and role from token payload

4. Role enforcement:
   admin  — full access to all endpoints
   editor — GET on all endpoints
           POST/PUT/DELETE only on /api/leaves
           POST/PUT/DELETE on /api/physicians and /api/sites returns 403
   viewer — GET only on /api/sites, /api/physicians, /api/capacity
           All other endpoints return 403

The default admin user is already in the database (from schema.sql seed).
Email: admin@yourdomain.com
Password: changeme

Update requirements.txt to include:
  python-jose[cryptography]
  passlib[bcrypt]

Add to .env.example:
  SECRET_KEY=replace_with_64_random_chars
  ACCESS_TOKEN_EXPIRE_MINUTES=480
```

---

### Prompt 2.2 — Login screen in React

```
Now add a login screen to the React frontend.

Requirements:
1. If there is no valid JWT in memory, show a login page 
   (email + password fields, login button)
2. On successful login, store the token in memory (not localStorage)
   and show the main app
3. On failed login, show a clear error message
4. Add a logout button in the top bar that clears the token 
   and returns to the login screen
5. Pass the Authorization header with every API call:
   Authorization: Bearer {token}
6. If any API call returns 401, redirect to the login screen
7. Based on the user role returned from the API, hide or 
   disable UI elements:
   - viewer: hide the Leaves tab entirely
   - editor: show Leaves tab; grey out Add Provider and 
     Add Site buttons with a tooltip "Admin access required"
   - admin: full access, no restrictions

The login page should match the existing visual style of the app 
(dark sidebar, same fonts and colors).
```

---

## PHASE 3 — QGenda Sync

---

### Prompt 3.1 — QGenda sync service

```
Phase 2 is working. Now build Phase 3 — QGenda sync.

The QGenda REST API:
  Base URL:  https://api.qgenda.com/v2
  Auth:      POST /v2/login
             Headers: Content-Type: application/x-www-form-urlencoded
             Body: email=EMAIL&password=PASSWORD
             Returns: { access_token, token_type, expires_in }
  Staff:     GET /v2/staffmember
             Headers: Authorization: bearer {token}
             Returns: array of staff objects with fields including
             StaffId, StaffKey, FName, LName, Email, NPI, IsActive

Create backend/services/qgenda_sync.py that:

1. Authenticates with QGenda using QGENDA_EMAIL and QGENDA_PASSWORD 
   from environment variables
   
2. Pulls all staff where IsActive = true

3. For each staff member:
   a. Try to match by NPI first (exact match on physicians.npi)
   b. If no NPI match, try fuzzy name match using rapidfuzz:
      - Compute token_sort_ratio on last_name
      - If score >= 90: auto-match and log as "auto-matched"
      - If score 70-89: flag for human review (do not auto-match)
      - If score < 70: create as new physician with needs_fte_config=TRUE
   c. For matched physicians:
      - Update qgenda_staff_id, qgenda_staff_key, last_synced_at
      - Update is_active status
   d. For new physicians:
      - Insert with is_active=TRUE, needs_fte_config=TRUE
      - Set last_name, first_name from QGenda
      - Leave provider_type_id, yearly_hours, site assignments NULL
        (admin will configure these via the UI)

4. For physicians in our DB who were NOT in the QGenda response:
   - Set is_active = FALSE (they left the department)

5. Write a full summary to qgenda_sync_log table:
   providers_found, providers_matched, providers_created, 
   providers_updated, providers_flagged

6. Write individual actions to audit_log with action='SYNC'

Add environment variables to .env.example:
  QGENDA_EMAIL=your.email@mountsinai.org
  QGENDA_PASSWORD=your_password
  QGENDA_COMPANY_KEY=

Add a sync endpoint:
  POST /api/admin/qgenda-sync — triggers sync immediately (admin only)
  GET  /api/admin/qgenda-sync/log — last 10 sync results
  GET  /api/admin/qgenda-sync/needs-config — providers needing FTE setup
```

---

### Prompt 3.2 — QGenda sync UI

```
Now add the QGenda Sync admin page to the React frontend.

Add a new nav item "QGenda Sync" (visible to admin only) with:

1. Sync status card:
   - Last sync timestamp
   - Result: X matched, X created, X flagged for configuration
   - "Run sync now" button that calls POST /api/admin/qgenda-sync
   - Show a spinner while sync is running

2. Needs configuration table:
   - List all physicians with needs_fte_config = TRUE
   - Columns: Name, QGenda Key, Synced at, Action
   - "Configure" button on each row opens a modal where admin can:
     - Set provider type
     - Set yearly hours
     - Set clinical percentage
     - Add site assignments with FTE fractions
     - Save (calls PUT /api/physicians/{id} and clears the flag)

3. Recent sync log:
   - Table showing last 10 sync runs
   - Columns: Date/time, Status, Found, Matched, Created, Flagged

4. Schedule a nightly sync using APScheduler in the FastAPI app:
   - Run at 2:00 AM daily
   - Log to qgenda_sync_log
```

---

## PHASE 4 — Deployment

---

### Prompt 4.1 — Production Docker setup

```
Phase 3 is working locally. Now prepare for production deployment.

Create production-ready versions of the Docker configuration:

1. backend/Dockerfile.prod
   - Multi-stage build
   - No --reload flag
   - Run as non-root user
   - Install only production dependencies

2. frontend/Dockerfile.prod
   - Build the Vite app (npm run build)
   - Serve static files with nginx
   - nginx config that proxies /api/* to the backend service

3. docker-compose.prod.yml
   - No source volume mounts (use built images)
   - Restart policies: always
   - Resource limits
   - postgres with named volume and daily backup command
   - Environment variables from .env file (no hardcoded secrets)

4. nginx.conf
   - Serve frontend static files
   - Proxy /api to backend:8000
   - HTTPS redirect (certificate path as environment variable)
   - Gzip compression
   - Security headers

Tell me the exact commands to:
- Build the production images
- Start the production stack
- Run the database schema on first deploy
- Back up the database manually
```

---

### Prompt 4.2 — Environment and secrets

```
Set up proper secrets management for production.

Create a checklist file DEPLOYMENT.md that covers:

1. Environment variables required for production:
   - DATABASE_URL
   - SECRET_KEY (must be 64+ random chars)
   - POSTGRES_PASSWORD
   - QGENDA_EMAIL
   - QGENDA_PASSWORD
   - QGENDA_COMPANY_KEY
   - ALLOWED_ORIGINS (comma-separated list of frontend URLs)

2. First-deploy checklist:
   - Generate a real SECRET_KEY
   - Change the default admin password
   - Run the schema
   - Verify all endpoints respond
   - Test login flow

3. Security checklist:
   - No secrets in git (confirm .env is in .gitignore)
   - HTTPS only in production
   - Database not exposed to public internet
   - Regular automated backups configured

Also add a .gitignore if one does not exist that excludes:
  .env
  __pycache__/
  *.pyc
  node_modules/
  dist/
  .DS_Store
```

---

## PHASE 5 — Polish (use these as needed, in any order)

---

### Prompt 5.A — Excel export

```
Add an Excel export feature that produces a report matching the 
existing MSH staffing spreadsheet format.

Create GET /api/export/capacity?year=2026 that returns an .xlsx file.

The spreadsheet should have one sheet per site with columns:
  Life No | Last | First | Type | Role(s) | Core | Notes | FTE | 
  Site FTE | Yearly Hrs | Clinical Hrs | Role Hrs | Jan | Feb | Mar | 
  Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec

Plus summary rows at the bottom:
  Staff Total | Schedule Total | Staffing Margin | FTE Margin

Add an "Export to Excel" button in the dashboard toolbar.

Use the openpyxl library. Match the column structure of the 
existing file: database/reference/2026_MSH_Staffing_MD_only.xlsx
if it exists, otherwise use the structure described above.
```

---

### Prompt 5.B — Email alerts

```
Add email alerts for deficit months.

When a new leave is created via POST /api/leaves:
1. Recalculate capacity for all months that the leave overlaps
2. If any month now has hours_gap < 0 (deficit):
   - Send an email alert to all admin users
   - Subject: "Coverage gap created — {site} {month} {year}"
   - Body: 
     - Provider name and leave type
     - Which months are affected
     - Hours deficit per month
     - Link to dashboard

Use fastapi-mail or smtplib. 
Add to .env.example:
  SMTP_HOST=
  SMTP_PORT=587
  SMTP_USER=
  SMTP_PASSWORD=
  ALERT_FROM_EMAIL=noreply@yourdomain.com
```

---

### Prompt 5.C — Annual hours tracking

```
Add annual clinical hours commitment tracking.

Each physician has a yearly_hours target. Track actual hours worked 
against that target.

Add a new table: hours_log
  id, physician_id, site_id, shift_date, hours_worked, 
  source (manual | qgenda), notes, created_at

Add endpoints:
  GET  /api/hours?physician_id=&year=2026
  POST /api/hours                          — manual entry
  GET  /api/hours/summary?year=2026        — all physicians, ytd vs target

Add a new "Hours Tracking" tab in the frontend showing:
  - Table of all physicians
  - YTD hours worked vs annual target
  - Percentage complete
  - Projected annual hours (YTD / months elapsed * 12)
  - Color coded: green if on track, amber if within 10% under, red if more than 10% under
```

---

### Prompt 5.D — Audit log UI

```
Add an audit log page to the admin section of the frontend.

Show a table of recent changes from the audit_log table:
  Timestamp | User | Action | What changed | Details

Filters:
  - By date range
  - By user
  - By action type (INSERT, UPDATE, DELETE, SYNC, LOGIN)
  - By table (physicians, leaves, demand, etc.)

Make sure all existing API endpoints write to audit_log:
  - Include old_values (JSONB) for UPDATE and DELETE operations
  - Include new_values (JSONB) for INSERT and UPDATE operations
  - Record user_id and user_email from the JWT token

This gives you a full trail of who changed what and when, 
which is important for a clinical operations tool.
```

---

## Troubleshooting Prompts

Use these whenever something breaks.

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

### When the frontend is not showing data

```
The {tab/component name} in the frontend is not showing data.
The API endpoint GET /api/{endpoint} returns this when called 
directly:

{paste the API response}

But the frontend shows {describe what you see — empty, error, 
wrong data}.

Please diagnose whether this is a CORS issue, a data mapping 
issue, or something else and fix it.
```

---

### When QGenda sync fails

```
The QGenda sync is failing with this error:

{paste the full error from the sync log or console}

The sync is running in backend/services/qgenda_sync.py.
Please diagnose and fix the issue.
```

---

## Git Workflow

Run these after each phase completes successfully:

```bash
# Phase 1 complete
git add .
git commit -m "Phase 1: full-stack foundation — FastAPI + PostgreSQL + React connected"

# Phase 2 complete
git add .
git commit -m "Phase 2: authentication — JWT login and role-based access"

# Phase 3 complete
git add .
git commit -m "Phase 3: QGenda sync — nightly roster sync with NPI matching"

# Phase 4 complete
git add .
git commit -m "Phase 4: production deployment — Docker + nginx + HTTPS"
```

Never commit `.env` files. Check with `git status` before every commit.
