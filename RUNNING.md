# Running the ED Capacity Planner

**Last updated:** 2026-06-24 — update this file as the setup changes.

---

## Prerequisites

- Docker Desktop (or Docker Engine + Compose) installed and running
- A `.env` file in the project root (copy from `.env.example` and fill in real values — never commit `.env`)

---

## Start everything

```bash
docker compose up -d --build
```

This builds and starts three containers:

| Service    | What it is              | URL                          |
|------------|--------------------------|-------------------------------|
| `postgres` | PostgreSQL 16 database   | `localhost:5432`              |
| `backend`  | FastAPI app (hot-reload) | http://localhost:8001         |
| `frontend` | React/Vite app (hot-reload) | http://localhost:5173      |

- Swagger/OpenAPI docs for the backend: http://localhost:8001/docs
- A `404` at `http://localhost:8001/` alone is expected — there's no root endpoint defined.

## Check status / logs

```bash
docker compose ps          # see container status
docker compose logs -f     # follow logs from all services
docker compose logs -f backend   # just the backend
```

## Stop everything

```bash
docker compose down
```

This stops and removes the containers but keeps the `postgres_data` volume (your data persists).

## Reset the database from scratch

```bash
docker compose down -v     # also removes the postgres_data volume
docker compose up -d --build
```

The schema in `database/schema.sql` is only applied automatically when the Postgres data directory is empty (first run, or after `-v`).

## Applying schema changes to an existing database

Because `schema.sql` only runs on an empty data directory, an environment
with a real database already running it (Coolify included) does **not**
pick up schema changes on its own — deploying new backend code against an
out-of-date schema will fail on missing tables/columns.

When `database/schema.sql` changes, add (or update) a migration file under
`database/migrations/` with the equivalent DDL written idempotently
(`IF NOT EXISTS`, guarded `DO` blocks for constraint changes, `ON CONFLICT
DO NOTHING` for seed rows) and run it against the target database before
deploying the code that depends on it:

```bash
psql "$DATABASE_URL" -f database/migrations/<file>.sql
```

or, against a container that isn't exposing its port to the host:

```bash
docker exec -i <postgres_container> psql -U postgres -d ed_capacity \
  < database/migrations/<file>.sql
```

**Back up the database first** (`pg_dump`) — every migration here is meant
to be additive and safe to re-run, but this is DDL against a live database
and a backup should be on hand regardless.

`database/migrations/2026_phase1_5_and_phase_d.sql` brings a database that
was initialized before Phase 1.5 (auth/audit log/error log) and Phase D
(time allocations) up to date; it's a no-op if some or all of it is already
applied.

---

## One-time data migration scripts

### `backend/scripts/import_time_allocations.py`

Imports `2026-staffing.xlsx` (10 categories × 12 months of hours per physician)
into `time_allocations` via the running API. **One-time migration, not a
recurring sync** — run it once against a populated physician roster, review
the printed summary, done.

```bash
cd backend
ADMIN_EMAIL=you@yourdomain.com ADMIN_PASSWORD='...' \
API_BASE_URL=http://localhost:8001 \
python -m scripts.import_time_allocations
```

Env vars:

| Var | Default | Purpose |
|---|---|---|
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | *(required)* | Logs in as this admin user to call the API |
| `API_BASE_URL` | `http://localhost:8000` | Base URL of the running backend |
| `EXCEL_PATH` | `<repo root>/2026-staffing.xlsx` | Path to the workbook |
| `IMPORT_YEAR` | `2026` | Year written to `time_allocations` |
| `DRY_RUN` | *(unset)* | Set to any value to parse and match without writing — review the match/skip list first |

What it does:
- Identifies real physician rows in the `"MD Staffing Grid"` sheet via column A (`Life No`) == `'#REF!'` (skips subtotal/summary rows)
- Matches each row to an existing physician by exact `last_name` + `first_name` (case/whitespace-normalized only — never fuzzy-matched); anything with zero or more than one match is **skipped and printed for manual review**, not guessed
- Extracts each of the 10 categories' Jan–Dec hours and calls `PUT /api/physicians/{id}/time-allocations` with `year=2026`, `change_reason="Imported from 2026-staffing.xlsx"`
- Separately reports any rows where the Excel's own `Total Hrs Check` column doesn't match `MSH Hrs` — pre-existing source-data issues, not something the import caused
- Prints a final summary: physicians matched/updated, physicians skipped with reasons, Excel check mismatches

Depends on `openpyxl` (in `backend/requirements.txt`) and reads the workbook directly from disk — the API only needs to be reachable, the Excel file does not need to be mounted into the backend container.

`import_staffing.py` and `seed_physicians.py` at the project root are earlier, superseded prototypes for loading roster/physician data — prefer the script above for `time_allocations` specifically.
