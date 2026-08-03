# ED Capacity Planner — Project Roadmap

**Project:** FTE-Scheduler  
**Stack:** React + Vite · FastAPI · PostgreSQL · Docker  
**Owner:** Adam Munday, Clinical Informatics Fellow, Mount Sinai  
**Started:** May 2026

---

## Project Goal

Replace the manual Excel staffing grid with a web application that tracks ED physician and APP capacity across MSH, MSB, and MSQ — showing available vs. required clinical hours and FTE per month, before scheduling begins.

---

## Current State

- ✅ React prototype complete (`/frontend/src/App.jsx`)
- ✅ PostgreSQL schema designed (`/database/schema.sql`)
- ✅ QGenda REST API documented and test script written
- ⬜ Backend not yet built
- ⬜ Data not yet persistent
- ⬜ Not yet deployed

---

## Phase 1 — Full-Stack Foundation
**Goal:** Data persists. Multiple people can use it. Nothing is lost on refresh.  
**Target:** 2–3 weeks

### Tasks
- [ ] Scaffold FastAPI backend (`/backend`)
- [ ] Connect FastAPI to PostgreSQL
- [ ] Implement CRUD endpoints for all tables:
  - `GET/POST /sites`
  - `GET/POST /physicians`
  - `GET/PUT/DELETE /physicians/{id}`
  - `GET/POST /physicians/{id}/assignments`
  - `GET/POST /physicians/{id}/roles`
  - `GET/POST /leaves`
  - `GET/PUT /demand`
  - `GET /capacity?year=2026` ← core calculation endpoint
  - `GET /capacity?year=2026&site_id=...` ← filtered by site
- [ ] Update React frontend to call real API (replace all in-memory state)
- [ ] Create `docker-compose.yml` (frontend + backend + postgres)
- [ ] Run database schema (`/database/schema.sql`)
- [ ] Seed sample data matching existing Excel file
- [ ] Verify dashboard shows correct gap calculations

### Done When
You can add a physician, enter a leave, and see the dashboard update — and it is still there after you close the browser and reopen.

---

## Phase 2 — Authentication and Role-Based Access
**Goal:** Control who can do what before sharing with anyone else.  
**Target:** 1 week after Phase 1

### Tasks
- [ ] Add login endpoint (`POST /auth/login`) returning JWT token
- [ ] Add token refresh endpoint
- [ ] Protect all API routes with JWT middleware
- [ ] Enforce role permissions on endpoints:
  - `admin` — full access to everything
  - `editor` — add/edit/delete leaves only; read-only on physicians and sites
  - `viewer` — dashboard and physician list read-only; no access to leaves tab
- [ ] Build login screen in React frontend
- [ ] Store JWT in httpOnly cookie (not localStorage)
- [ ] Add logout
- [ ] Seed default admin user (`admin@mountsinai.org` / `changeme`)

### Done When
A coordinator can log in as editor, enter a leave, and cannot accidentally change a physician's FTE. A department chief can log in as viewer and see the dashboard only.

---

## Phase 3 — QGenda Sync
**Goal:** Stop manually maintaining the physician roster. QGenda is the source of truth for who exists.  
**Target:** 1–2 weeks after Phase 2

### Tasks
- [ ] Write QGenda authentication helper (POST to `/v2/login`, cache token)
- [ ] Write staff sync function:
  - Pull all active staff from `GET /v2/staffmember`
  - Match by NPI first, then fuzzy name match (rapidfuzz)
  - Matched: update name, active status, last synced timestamp
  - Unmatched: insert with `needs_fte_config = TRUE`
  - Deactivated in QGenda: set `is_active = FALSE` in our DB
  - Log everything to `qgenda_sync_log`
- [ ] Build admin UI page "QGenda Sync":
  - Last sync timestamp and result summary
  - Table of providers flagged `needs_fte_config`
  - "Configure FTE" action per flagged provider
  - "Run sync now" button
- [ ] Schedule nightly sync job (2am via APScheduler or cron)
- [ ] Store credentials in environment variables:
  - `QGENDA_EMAIL`
  - `QGENDA_PASSWORD`
  - `QGENDA_COMPANY_KEY`

### Done When
Adding a physician to QGenda causes them to appear in the capacity planner the next morning, flagged for FTE configuration.

---

## Phase 4 — Deployment
**Goal:** Off your laptop and onto a server your team can reach.  
**Target:** 1 week after Phase 3

### Tasks
- [ ] Containerize all services with production-ready Dockerfiles
- [ ] Set up Azure VM (or equivalent inside Mount Sinai infrastructure)
- [ ] Configure nginx as reverse proxy with HTTPS
- [ ] Set up SSL certificate (Let's Encrypt or institutional cert)
- [ ] Configure environment variables for production secrets
- [ ] Set up automated daily database backups
- [ ] Set up basic uptime monitoring
- [ ] IT security review (data classification, access controls)
- [ ] Pilot with 2–3 admin users before broad rollout

### Done When
Any authorized team member can open a URL, log in, and use the app without needing your laptop running.

---

## Phase 5 — Polish and Integrations
**Goal:** Make it feel like a real institutional tool.  
**Target:** Ongoing after Phase 4

### Features (prioritized)
- [ ] **Excel export** — monthly capacity report matching the existing spreadsheet format, suitable for leadership meetings
- [ ] **Email alerts** — notify department chief when a new leave creates a future month deficit
- [ ] **Annual hours commitment tracking** — target hours vs. actual hours worked per physician per year
- [ ] **Actual hours from QGenda** — nightly sync of shifts worked to auto-fill hours tracking
- [ ] **FTE history timeline** — view how a physician's FTE has changed over time
- [ ] **Audit log UI** — admin view of all changes (who changed what and when)
- [ ] **Institutional SSO** — replace email/password login with Azure AD / Okta
- [ ] **Sub-area breakdown** — Adult ED vs. Peds ED hours tracked separately within MSH
- [ ] **Mobile-responsive UI** — basic usability on tablet for coordinators

---

## Folder Structure

```
FTE-Scheduler/
├── frontend/                  ← React + Vite app
│   ├── src/
│   │   ├── App.jsx            ← main component
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
│
├── backend/                   ← FastAPI app
│   ├── main.py                ← app entry point
│   ├── routers/
│   │   ├── physicians.py
│   │   ├── sites.py
│   │   ├── leaves.py
│   │   ├── demand.py
│   │   ├── capacity.py        ← core calculation endpoint
│   │   ├── auth.py            ← Phase 2
│   │   └── qgenda.py          ← Phase 3
│   ├── models/                ← SQLAlchemy models
│   ├── schemas/               ← Pydantic schemas
│   ├── db.py                  ← database connection
│   ├── requirements.txt
│   └── .env                   ← secrets (never commit this)
│
├── database/
│   ├── schema.sql             ← full PostgreSQL schema
│   └── migrations/            ← future Alembic migrations
│
├── docker-compose.yml         ← local orchestration
├── docker-compose.prod.yml    ← production overrides
├── ROADMAP.md                 ← this file
└── PROMPTS.md                 ← Claude Code prompt sequence
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Backend language | Python / FastAPI | Matches informatics skill set; async support; auto docs |
| Database | PostgreSQL | Handles JSONB for roles; strong UUID support; reliable |
| Auth (Phase 1–3) | JWT tokens | Simple to implement; stateless; easy to replace with SSO |
| Auth (Phase 4+) | Azure AD SSO | Mount Sinai is Microsoft shop; no separate password management |
| FTE source of truth | QGenda (roster) + this app (FTE fractions) | QGenda owns identity; we own capacity math |
| Deployment | Docker on Azure VM | Inside institutional firewall; no PHI leaves the network |
| Leave entry | Manual in this app | HR system integration is Phase 5; manual is good enough to start |

---

## Estimated Timeline

| Phase | Duration | Cumulative |
|---|---|---|
| Phase 1 — Full stack | 2–3 weeks | Week 3 |
| Phase 2 — Auth | 1 week | Week 4 |
| Phase 3 — QGenda sync | 1–2 weeks | Week 6 |
| Phase 4 — Deploy | 1 week | Week 7 |
| Phase 5 — Polish | Ongoing | — |

At 8–10 hours/week alongside fellowship duties, a usable internal tool is realistic by **end of August 2026** — well before your ABEM exam in late October.

---

## Notes and Decisions Log

| Date | Note |
|---|---|
| May 2026 | QGenda integrations page reviewed — Schedule Export and Staff Demographic Export are grayed out (not in current contract). REST API access TBD — need to confirm with QGenda rep or call 855-399-9945 ext 2. |
| May 2026 | Decided to build custom tool rather than buy — no commercial product does pre-scheduling FTE capacity planning with leave-adjusted availability cleanly. |
| May 2026 | React prototype completed and validated against existing Excel staffing grid (`2026_MSH_Staffing_MD_only.xlsx`). |
