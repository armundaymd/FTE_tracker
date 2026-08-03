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

---

## Notes / things to revisit as the project develops

- As of 2026-06-24, the FastAPI backend (`backend/`) is scaffolded but has no real endpoints yet — routers in `backend/routers/` are stubs. Update the table above and the docs link once endpoints exist.
- The React app currently runs as a single-file prototype (`frontend/src/App.jsx`) with hardcoded data for year 2026. It is not yet wired up to the backend.
- `import_staffing.py` and `seed_physicians.py` exist at the project root for loading the `2026-staffing.xlsx` data — document how/when to run these here once they're part of the regular workflow.
