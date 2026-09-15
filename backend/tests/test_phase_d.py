"""
End-to-end verification script for ROADMAP_PHASE_D (Time Allocations).

Exercises the real HTTP API against a running backend + database — it is
NOT a pytest suite, just a standalone script. Run it with:

    python backend/tests/test_phase_d.py

Requires the same setup as test_phase1_5.py: a reachable backend +
Postgres, this script's Python env to have the backend's dependencies
installed, and DATABASE_URL resolving to that database from wherever
this runs.

Override the API base URL with the API_BASE env var if it's not the
default local docker-compose setup:

    API_BASE=https://api-capacity.example.com/api python backend/tests/test_phase_d.py

Everything this script creates (a throwaway admin user, an isolated
test site, a test physician, and its site assignment + time_allocations
rows) is deleted again at the end — audit_log rows are the one
exception, left alone deliberately, same as test_phase1_5.py.
"""

import asyncio
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

from auth.security import hash_password  # noqa: E402
from db import AsyncSessionLocal, engine  # noqa: E402
from models.physician import Physician  # noqa: E402
from models.site import Site  # noqa: E402
from models.user import User  # noqa: E402
from sqlalchemy import delete  # noqa: E402

API_BASE = os.environ.get("API_BASE", "http://localhost:8001/api")
TEST_ADMIN_EMAIL = f"phase_d_test_{uuid.uuid4().hex[:8]}@test.local"
TEST_ADMIN_PASSWORD = "TestPassword123!"
TEST_ADMIN_NAME = "Phase D Verification Script"

YEARLY_HOURS = 1440
# Excel row 2 example: 600 hours in Adult ED (clinical), evenly across 12
# months, plus 840 hours in Research (non-clinical), evenly across 12
# months. 600 / 1440 = 0.41666... -> clinical_pct ~= 0.4167.
ADULT_ED_TOTAL = 600
RESEARCH_TOTAL = 840
ADULT_ED_MONTHLY = Decimal(ADULT_ED_TOTAL) / 12   # 50
RESEARCH_MONTHLY = Decimal(RESEARCH_TOTAL) / 12   # 70
EXPECTED_CLINICAL_PCT = Decimal("0.4167")

results: list[tuple[str, bool, str]] = []


def record(step: str, passed: bool, detail: str = "") -> None:
    results.append((step, passed, detail))
    status = "PASS" if passed else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {step}{suffix}")


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
    time_allocations both have ON DELETE CASCADE on physician_id, so this
    also removes the assignment and time_allocations rows this script
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


def close(a, b, tol=Decimal("0.0001")) -> bool:
    return abs(Decimal(str(a)) - Decimal(str(b))) <= tol


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

    created = {"physician_id": None, "site_id": None}
    current_year = date.today().year

    async with httpx.AsyncClient(base_url=API_BASE, timeout=15.0) as client:
        try:
            # ── 2. Log in ────────────────────────────────────────────────
            resp = await client.post("/auth/login", json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD})
            if resp.status_code != 200:
                record("2. Log in and get a token", False, f"status {resp.status_code}: {resp.text}")
                return 1
            token = resp.json()["access_token"]
            record("2. Log in and get a token", True)
            auth = {"Authorization": f"Bearer {token}"}

            # ── 3. Create test physician (yearly_hours = 1440) ──────────────
            resp = await client.post(
                "/physicians/", headers=auth,
                json={
                    "last_name": "PhaseDTestPhysician", "first_name": "Verify",
                    "clinical_pct": "1.0", "yearly_hours": YEARLY_HOURS,
                },
            )
            if resp.status_code != 201:
                record("3. Create test physician", False, f"status {resp.status_code}: {resp.text}")
                return 1
            physician = resp.json()
            physician_id = physician["id"]
            created["physician_id"] = physician_id
            record("3. Create test physician", True, physician_id)

            # Baseline: fresh physician starts needing time allocation config.
            baseline_ok = physician["needs_time_allocation_config"] is True
            record("3a. Fresh physician needs_time_allocation_config = true", baseline_ok, str(physician.get("needs_time_allocation_config")))

            # A dedicated, isolated site so the capacity check in step 6
            # isn't skewed by anything else assigned to a shared site.
            site_name = f"PhaseD Test Site {uuid.uuid4().hex[:6]}"
            resp = await client.post("/sites/", headers=auth, json={"name": site_name, "areas": []})
            if resp.status_code != 201:
                record("3b. Create isolated test site", False, f"status {resp.status_code}: {resp.text}")
                return 1
            site = resp.json()
            site_id = site["id"]
            created["site_id"] = site_id
            record("3b. Create isolated test site", True, site_id)

            resp = await client.post(
                f"/physicians/{physician_id}/assignments", headers=auth,
                json={"site_id": site_id, "fte_fraction": "1.0", "effective_date": f"{current_year}-01-01"},
            )
            if resp.status_code != 201:
                record("3c. Create site assignment", False, f"status {resp.status_code}: {resp.text}")
                return 1
            record("3c. Create site assignment", True, resp.json()["id"])

            # ── 4. Look up time category ids for Adult ED / Research ────────
            resp = await client.get("/time-categories", headers=auth)
            if resp.status_code != 200:
                record("4. GET /time-categories", False, f"status {resp.status_code}: {resp.text}")
                return 1
            categories = resp.json()
            adult_ed = next((c for c in categories if c["name"] == "Adult ED"), None)
            research = next((c for c in categories if c["name"] == "Research"), None)
            cats_ok = adult_ed is not None and research is not None and adult_ed["is_clinical"] and not research["is_clinical"]
            record("4. Found Adult ED (clinical) and Research (non-clinical) categories", cats_ok,
                   "" if cats_ok else str(categories))
            if not cats_ok:
                return 1

            # ── 5. PUT a full year of time_allocations (Excel row 2 example) ─
            def full_year_allocations():
                allocations = []
                for month in range(1, 13):
                    allocations.append({
                        "time_category_id": adult_ed["id"], "site_id": site_id,
                        "month": month, "hours": str(ADULT_ED_MONTHLY),
                    })
                    allocations.append({
                        "time_category_id": research["id"], "site_id": site_id,
                        "month": month, "hours": str(RESEARCH_MONTHLY),
                    })
                return allocations

            resp = await client.put(
                f"/physicians/{physician_id}/time-allocations", headers=auth,
                json={"year": current_year, "allocations": full_year_allocations()},
            )
            if resp.status_code != 200:
                record("5. PUT full year of time_allocations", False, f"status {resp.status_code}: {resp.text}")
                return 1
            grid = resp.json()
            full_year_ok = close(grid["allocated_hours"], YEARLY_HOURS) and close(grid["hours_variance"], 0)
            record("5. PUT full year of time_allocations", full_year_ok,
                   "" if full_year_ok else f"allocated={grid['allocated_hours']} variance={grid['hours_variance']}")

            # ── 6. GET /api/physicians/{id} reflects clinical_pct + flag ────
            resp = await client.get(f"/physicians/{physician_id}", headers=auth)
            physician = resp.json()
            clinical_pct_ok = close(physician["clinical_pct"], EXPECTED_CLINICAL_PCT)
            record("6a. clinical_pct ≈ 0.4167 after full-year allocation", clinical_pct_ok,
                   f"got {physician['clinical_pct']}")
            flag_ok = physician["needs_time_allocation_config"] is False
            record("6b. needs_time_allocation_config = false after full-year allocation", flag_ok,
                   f"got {physician['needs_time_allocation_config']}")

            # ── 7. GET /api/time-allocations/check excludes this physician ──
            resp = await client.get(f"/time-allocations/check?year={current_year}", headers=auth)
            if resp.status_code != 200:
                record("7. GET /time-allocations/check", False, f"status {resp.status_code}: {resp.text}")
            else:
                check_rows = resp.json()
                excluded = not any(r["physician_id"] == physician_id for r in check_rows)
                record("7. Balanced physician does NOT appear in /time-allocations/check", excluded)

            # ── 8. Capacity reflects the new clinical_pct ────────────────────
            resp = await client.get(f"/capacity/?year={current_year}&site_id={site_id}", headers=auth)
            if resp.status_code != 200:
                record("8. GET /capacity/ (after full-year allocation)", False, f"status {resp.status_code}: {resp.text}")
            else:
                rows = resp.json().get("rows", [])
                jan_row = next((r for r in rows if r["month"] == 1), None)
                # available_hours for a 1.0 FTE physician in Jan; clinical_hours should be
                # available_hours * clinical_pct.
                capacity_ok = (
                    jan_row is not None
                    and close(jan_row["clinical_hours"], jan_row["available_hours"] * float(physician["clinical_pct"]), tol=Decimal("0.5"))
                )
                record("8. /capacity/ clinical_hours reflects updated clinical_pct", capacity_ok,
                       "" if capacity_ok else str(jan_row))

            # ── 9. PUT an incomplete year for the same physician ─────────────
            def incomplete_year_allocations():
                # Only fund Adult ED, and only 500 hours total (not 1440) —
                # deliberately doesn't sum to yearly_hours.
                allocations = []
                for month in range(1, 13):
                    allocations.append({
                        "time_category_id": adult_ed["id"], "site_id": site_id,
                        "month": month, "hours": str(Decimal("500") / 12),
                    })
                    # Zero out Research so the total really is short, not just
                    # missing rows for a category that still has old hours.
                    allocations.append({
                        "time_category_id": research["id"], "site_id": site_id,
                        "month": month, "hours": "0",
                    })
                return allocations

            resp = await client.put(
                f"/physicians/{physician_id}/time-allocations", headers=auth,
                json={"year": current_year, "allocations": incomplete_year_allocations()},
            )
            if resp.status_code != 200:
                record("9. PUT incomplete year of time_allocations", False, f"status {resp.status_code}: {resp.text}")
                return 1
            grid = resp.json()
            incomplete_ok = not close(grid["allocated_hours"], YEARLY_HOURS)
            record("9. PUT incomplete year of time_allocations", incomplete_ok,
                   f"allocated={grid['allocated_hours']} (expected != {YEARLY_HOURS})")

            # ── 10. Flag flips back to true; physician reappears in check ───
            resp = await client.get(f"/physicians/{physician_id}", headers=auth)
            physician = resp.json()
            flag_flip_ok = physician["needs_time_allocation_config"] is True
            record("10a. needs_time_allocation_config flips back to true", flag_flip_ok,
                   f"got {physician['needs_time_allocation_config']}")

            resp = await client.get(f"/time-allocations/check?year={current_year}", headers=auth)
            check_rows = resp.json()
            reappears = any(r["physician_id"] == physician_id for r in check_rows)
            record("10b. Physician reappears in /time-allocations/check", reappears)

            return 0 if all(ok for _, ok, _ in results) else 1

        finally:
            # ── 11. Clean up everything this script created ──────────────────
            cleanup_ok = True
            cleanup_detail = []
            async with AsyncSessionLocal() as db:
                try:
                    if created["physician_id"]:
                        # Cascades away its site_assignments and time_allocations rows too.
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

            record("11. Clean up test data", cleanup_ok, "; ".join(cleanup_detail))
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
