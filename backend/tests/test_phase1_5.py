"""
End-to-end verification script for ROADMAP_PHASE1.5 (Phases A, B, C).

Exercises the real HTTP API against a running backend + database — it is
NOT a pytest suite, just a standalone script. Run it with:

    python backend/tests/test_phase1_5.py

Requires:
- The backend + Postgres to be reachable (e.g. `docker compose up`).
- This script's Python environment to have the backend's dependencies
  installed (it imports db.py/models/auth.security directly, the same
  way scripts/create_admin.py does, to create/remove its own throwaway
  admin user without needing one to already exist).
- DATABASE_URL resolving to the database from wherever this runs (the
  project's .env already points at localhost:5432, which works from the
  host machine since docker-compose publishes that port).

Override the API base URL with the API_BASE env var if it's not the
default local docker-compose setup:

    API_BASE=https://api-capacity.example.com/api python backend/tests/test_phase1_5.py

Everything this script creates (a throwaway admin user, an isolated
test site, a test physician, its site-assignment history, and its
role) is deleted again at the end — audit_log rows are the one
exception, left alone deliberately, since the audit trail is supposed
to persist independent of whether the record it describes still exists.

Everything runs inside a single asyncio.run() call. Mixing several
separate asyncio.run() calls against the same module-level SQLAlchemy
async engine (db.py's `engine`/`AsyncSessionLocal`) orphans pooled
connections on the event loop each call tears down — that was tried
first and broke cleanup with "attached to a different loop" errors.
"""

import asyncio
import os
import sys
import uuid
from datetime import date

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

from auth.security import hash_password  # noqa: E402
from db import AsyncSessionLocal, engine  # noqa: E402
from models.physician import Physician  # noqa: E402
from models.site import Site  # noqa: E402
from models.user import User  # noqa: E402
from sqlalchemy import delete  # noqa: E402

API_BASE = os.environ.get("API_BASE", "http://localhost:8001/api")
TEST_ADMIN_EMAIL = f"phase1_5_test_{uuid.uuid4().hex[:8]}@test.local"
TEST_ADMIN_PASSWORD = "TestPassword123!"
TEST_ADMIN_NAME = "Phase1.5 Verification Script"

results: list[tuple[str, bool, str]] = []


def record(step: str, passed: bool, detail: str = "") -> None:
    results.append((step, passed, detail))
    status = "PASS" if passed else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {step}{suffix}")


def fte(value) -> float:
    return float(value)


# ── DB-level helpers (for the admin user + final hard-delete cleanup) ──────

async def create_test_admin(db) -> uuid.UUID:
    user = User(
        name=TEST_ADMIN_NAME,
        email=TEST_ADMIN_EMAIL,
        hashed_password=hash_password(TEST_ADMIN_PASSWORD),
        role="admin",
    )
    db.add(user)
    await db.commit()
    return user.id


async def hard_delete_physician(db, physician_id: uuid.UUID) -> None:
    """
    Hard-deletes the physician row directly (bypassing the API's soft
    delete) so the test leaves no trace. site_assignments and
    physician_roles both have ON DELETE CASCADE on physician_id, so this
    also removes the assignment history and role rows this script
    created — audit_log rows are untouched (no FK; that's intentional).
    """
    await db.execute(delete(Physician).where(Physician.id == physician_id))
    await db.commit()


async def hard_delete_site(db, site_id: uuid.UUID) -> None:
    """
    site_assignments.site_id is ON DELETE RESTRICT, so this must run
    AFTER hard_delete_physician has removed its assignment rows.
    """
    await db.execute(delete(Site).where(Site.id == site_id))
    await db.commit()


async def delete_test_admin(db, user_id: uuid.UUID) -> None:
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


async def main() -> int:
    print(f"API_BASE = {API_BASE}\n")

    # ── 1. Create admin user ────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        try:
            admin_user_id = await create_test_admin(db)
            record("1. Create admin user", True, TEST_ADMIN_EMAIL)
        except Exception as exc:
            record("1. Create admin user", False, str(exc))
            _summarize()
            return 1

    created = {"physician_id": None, "assignment_id": None, "new_assignment_id": None, "role_id": None, "site_id": None}

    async with httpx.AsyncClient(base_url=API_BASE, timeout=15.0) as client:
        try:
            # ── 2. Log in and get a token ────────────────────────────────
            resp = await client.post("/auth/login", json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD})
            if resp.status_code != 200:
                record("2. Log in and get a token", False, f"status {resp.status_code}: {resp.text}")
                return 1
            token = resp.json()["access_token"]
            record("2. Log in and get a token", True)
            auth = {"Authorization": f"Bearer {token}"}

            # ── 3. Unauthenticated request is rejected ─────────────────────
            resp = await client.get("/physicians/")
            record("3. Unauthenticated GET /physicians/ returns 401", resp.status_code == 401, f"got {resp.status_code}")

            # ── 4. Create physician + assignment + role; confirm in audit log ──
            resp = await client.post(
                "/physicians/", headers=auth,
                json={"last_name": "Phase1_5TestPhysician", "first_name": "Verify", "clinical_pct": "1.0", "yearly_hours": 1440},
            )
            if resp.status_code != 201:
                record("4a. Create test physician", False, f"status {resp.status_code}: {resp.text}")
                return 1
            physician = resp.json()
            created["physician_id"] = physician["id"]
            record("4a. Create test physician", True, physician["id"])

            # A dedicated, isolated site — not one of the real seeded sites —
            # so the capacity check in step 6 sees ONLY this test physician's
            # contribution and isn't skewed by whatever else is already
            # assigned to a shared site in this environment.
            site_name = f"Phase1_5 Test Site {uuid.uuid4().hex[:6]}"
            resp = await client.post("/sites/", headers=auth, json={"name": site_name, "areas": []})
            if resp.status_code != 201:
                record("4b(i). Create isolated test site", False, f"status {resp.status_code}: {resp.text}")
                return 1
            site = resp.json()
            created["site_id"] = site["id"]
            site_id = site["id"]
            record("4b(i). Create isolated test site", True, site_id)

            current_year = date.today().year

            resp = await client.post(
                f"/physicians/{created['physician_id']}/assignments", headers=auth,
                json={"site_id": site_id, "fte_fraction": "1.0", "effective_date": f"{current_year}-01-01"},
            )
            if resp.status_code != 201:
                record("4b. Create site assignment", False, f"status {resp.status_code}: {resp.text}")
                return 1
            assignment = resp.json()
            created["assignment_id"] = assignment["id"]
            record("4b. Create site assignment", True, assignment["id"])

            resp = await client.get("/physicians/lookup-tables", headers=auth)
            role_types = resp.json().get("role_types", [])
            role_type_id = role_types[0]["id"] if role_types else None

            resp = await client.post(
                f"/physicians/{created['physician_id']}/roles", headers=auth,
                json={"role_type_id": role_type_id, "hours_credit": 100, "effective_date": f"{current_year}-01-01"},
            )
            if resp.status_code != 201:
                record("4c. Create role", False, f"status {resp.status_code}: {resp.text}")
                return 1
            role = resp.json()
            created["role_id"] = role["id"]
            record("4c. Create role", True, role["id"])

            resp = await client.get("/audit-log/?table_name=physicians&action=INSERT", headers=auth)
            found = any(e["record_id"] == created["physician_id"] for e in resp.json())
            record("4d. Physician INSERT appears in audit log", found)

            resp = await client.get("/audit-log/?table_name=site_assignments&action=INSERT", headers=auth)
            found = any(e["record_id"] == created["assignment_id"] for e in resp.json())
            record("4e. Site assignment INSERT appears in audit log", found)

            resp = await client.get("/audit-log/?table_name=physician_roles&action=INSERT", headers=auth)
            found = any(e["record_id"] == created["role_id"] for e in resp.json())
            record("4f. Role INSERT appears in audit log", found)

            # ── 5. Update the assignment's FTE mid-year; check history ─────
            new_effective = f"{current_year}-07-01"
            resp = await client.put(
                f"/physicians/{created['physician_id']}/assignments/{created['assignment_id']}", headers=auth,
                json={"fte_fraction": "0.5", "effective_date": new_effective, "change_reason": "phase1.5 verification script"},
            )
            if resp.status_code != 200:
                record("5a. Update assignment FTE (close-and-insert)", False, f"status {resp.status_code}: {resp.text}")
                return 1
            new_assignment = resp.json()
            created["new_assignment_id"] = new_assignment["id"]
            record("5a. Update assignment FTE (close-and-insert)", True, new_assignment["id"])

            resp = await client.get(f"/physicians/{created['physician_id']}/fte-history", headers=auth)
            entries = resp.json().get("entries", [])
            assignment_entries = [e for e in entries if e["type"] == "assignment"]
            old_row = next((e for e in assignment_entries if e["detail"]["id"] == created["assignment_id"]), None)
            new_row = next((e for e in assignment_entries if e["detail"]["id"] == created["new_assignment_id"]), None)

            old_ok = bool(old_row) and old_row["detail"]["end_date"] is not None and fte(old_row["detail"]["fte_fraction"]) == 1.0
            record("5b. History shows the OLD assignment row, closed at 1.0 FTE", old_ok,
                   "" if old_ok else str(old_row))

            new_ok = (
                bool(new_row) and new_row["detail"]["end_date"] is None
                and fte(new_row["detail"]["fte_fraction"]) == 0.5
                and new_row.get("change_reason") == "phase1.5 verification script"
            )
            record("5c. History shows the NEW assignment row, open at 0.5 FTE with change_reason", new_ok,
                   "" if new_ok else str(new_row))

            # ── 6. Capacity still correct after the history change ─────────
            resp = await client.get(f"/capacity/?year={current_year}&site_id={site_id}", headers=auth)
            if resp.status_code != 200:
                record("6. GET /capacity/?year=... returns 200", False, f"status {resp.status_code}: {resp.text}")
            else:
                rows = resp.json().get("rows", [])
                jan_row = next((r for r in rows if r["month"] == 1), None)
                jul_row = next((r for r in rows if r["month"] == 7), None)
                capacity_ok = (
                    jan_row is not None and jul_row is not None
                    and jan_row["available_fte"] == 1.0
                    and jul_row["available_fte"] == 0.5
                )
                record(
                    "6. Capacity reflects old FTE pre-change and new FTE post-change",
                    capacity_ok,
                    "" if capacity_ok else f"jan={jan_row}, jul={jul_row}",
                )

            return 0 if all(ok for _, ok, _ in results) else 1

        finally:
            # ── 7. Clean up everything this script created ──────────────────
            cleanup_ok = True
            cleanup_detail = []
            async with AsyncSessionLocal() as db:
                try:
                    if created["physician_id"]:
                        # Cascades away its site_assignments and physician_roles rows too.
                        await hard_delete_physician(db, uuid.UUID(created["physician_id"]))
                except Exception as exc:
                    cleanup_ok = False
                    cleanup_detail.append(f"physician cascade delete failed: {exc}")

                try:
                    if created["site_id"]:
                        # Must run after the physician delete above (site_assignments.site_id
                        # is ON DELETE RESTRICT, not CASCADE).
                        await hard_delete_site(db, uuid.UUID(created["site_id"]))
                except Exception as exc:
                    cleanup_ok = False
                    cleanup_detail.append(f"test site delete failed: {exc}")

                try:
                    await delete_test_admin(db, admin_user_id)
                except Exception as exc:
                    cleanup_ok = False
                    cleanup_detail.append(f"admin user delete failed: {exc}")

            record("7. Clean up test data", cleanup_ok, "; ".join(cleanup_detail))
            _summarize()
            await engine.dispose()


def _summarize() -> None:
    print()
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"{passed}/{total} checks passed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
