"""
One-time migration: import 2026-staffing.xlsx into time_allocations via the
running API. NOT a recurring sync — run once, review the printed summary,
done.

Usage (from anywhere; defaults assume the API is running locally):

    ADMIN_EMAIL=you@yourdomain.com ADMIN_PASSWORD='...' \\
    python -m scripts.import_time_allocations

Env vars:
    ADMIN_EMAIL / ADMIN_PASSWORD   required — logs in as this admin user
    API_BASE_URL                   default http://localhost:8000
    EXCEL_PATH                     default <repo root>/2026-staffing.xlsx
    IMPORT_YEAR                    default 2026
    DRY_RUN                        if set (any value), parses and matches but
                                    does not call the PUT endpoint — useful to
                                    review the match/skip list before writing.

What this does NOT do: guess at ambiguous or missing physician name matches.
Anything that doesn't match exactly one active-or-inactive physician by
(last_name, first_name) is skipped and printed for manual review.
"""

import os
import sys

import httpx
import openpyxl

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
EXCEL_PATH = os.environ.get("EXCEL_PATH", os.path.join(REPO_ROOT, "2026-staffing.xlsx"))
IMPORT_YEAR = int(os.environ.get("IMPORT_YEAR", "2026"))
DRY_RUN = bool(os.environ.get("DRY_RUN"))
CHANGE_REASON = "Imported from 2026-staffing.xlsx"

SHEET_NAME = "MD Staffing Grid"
LIFE_NO_COL = 1       # column A — real physician data rows have exactly '#REF!' here
LAST_NAME_COL = 2     # column B
FIRST_NAME_COL = 3    # column C
MSH_HRS_COL = 13      # column M
TOTAL_HRS_CHECK_COL = 14  # column N — Excel's own Clinical+NonClinical check, must equal MSH_HRS_COL

# (category name, total column, first month column) — month columns run
# [month_start, month_start + 11] = Jan..Dec, and sit immediately BEFORE the
# category's own total column (verified by reconciling every category's
# month-sum against its total column across all 79 real data rows — 0
# mismatches — and cross-checked against physician Notes, e.g. ".25 P2P"
# summing to 360 hrs, ".1 VUC" to 144 hrs).
CATEGORIES = [
    ("Adult ED",   28,  16),
    ("Peds ED",    41,  29),
    ("P2P",        54,  42),
    ("VUC",        67,  55),
    ("IHS",        80,  68),
    ("Elmhurst",   93,  81),
    ("Admin",      107, 95),
    ("Nocturnist", 120, 108),
    ("Teaching",   133, 121),
    ("Research",   146, 134),
]


def _norm(name: str) -> str:
    return (name or "").strip().casefold()


def load_excel_rows(path: str):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[SHEET_NAME]

    rows = []
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=LIFE_NO_COL).value != "#REF!":
            continue  # summary/subtotal/blank row, not a real physician row
        last = ws.cell(row=r, column=LAST_NAME_COL).value
        first = ws.cell(row=r, column=FIRST_NAME_COL).value
        msh_hrs = ws.cell(row=r, column=MSH_HRS_COL).value or 0
        total_check = ws.cell(row=r, column=TOTAL_HRS_CHECK_COL).value or 0

        categories = {}
        for cat_name, _total_col, month_start in CATEGORIES:
            months = []
            for i in range(12):
                v = ws.cell(row=r, column=month_start + i).value
                months.append(float(v) if v is not None else 0.0)
            categories[cat_name] = months

        rows.append({
            "excel_row": r,
            "last_name": last,
            "first_name": first,
            "msh_hrs": float(msh_hrs),
            "total_hrs_check": float(total_check),
            "categories": categories,
        })
    return rows


def build_physician_index(client: httpx.Client):
    resp = client.get("/api/physicians/")
    resp.raise_for_status()
    index = {}
    for p in resp.json():
        key = (_norm(p["last_name"]), _norm(p["first_name"]))
        index.setdefault(key, []).append(p)
    return index


def build_category_id_map(client: httpx.Client):
    resp = client.get("/api/time-categories")
    resp.raise_for_status()
    return {c["name"]: c["id"] for c in resp.json()}


def login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print(f"Login failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()["access_token"]


def main():
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        print("ADMIN_EMAIL and ADMIN_PASSWORD environment variables are required.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(EXCEL_PATH):
        print(f"Excel file not found: {EXCEL_PATH}", file=sys.stderr)
        sys.exit(1)

    excel_rows = load_excel_rows(EXCEL_PATH)
    print(f"Read {len(excel_rows)} physician rows from {EXCEL_PATH}\n")

    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
        token = login(client, admin_email, admin_password)
        client.headers["Authorization"] = f"Bearer {token}"

        physician_index = build_physician_index(client)
        category_id_map = build_category_id_map(client)

        missing_categories = [c for c, _, _ in CATEGORIES if c not in category_id_map]
        if missing_categories:
            print(f"ERROR: API's /api/time-categories is missing expected categories: {missing_categories}", file=sys.stderr)
            sys.exit(1)

        matched = []
        skipped = []
        check_mismatches = []

        for row in excel_rows:
            label = f"{row['last_name']!r} {row['first_name']!r} (Excel row {row['excel_row']})"
            key = (_norm(row["last_name"]), _norm(row["first_name"]))
            candidates = physician_index.get(key, [])

            if abs(row["total_hrs_check"] - row["msh_hrs"]) >= 0.5:
                check_mismatches.append(
                    f"{label}: Excel Total Hrs Check={row['total_hrs_check']} != MSH Hrs={row['msh_hrs']} "
                    f"(diff={row['total_hrs_check'] - row['msh_hrs']:+.2f})"
                )

            if len(candidates) == 0:
                skipped.append(f"{label}: no physician found with this last_name + first_name")
                continue
            if len(candidates) > 1:
                ids = [c["id"] for c in candidates]
                skipped.append(f"{label}: ambiguous — {len(candidates)} physicians match this name ({ids})")
                continue

            physician = candidates[0]

            allocations = []
            for cat_name, _total_col, _month_start in CATEGORIES:
                category_id = category_id_map[cat_name]
                for month, hours in enumerate(row["categories"][cat_name], start=1):
                    allocations.append({
                        "time_category_id": category_id,
                        "month": month,
                        "hours": hours,
                        "change_reason": CHANGE_REASON,
                    })

            if DRY_RUN:
                matched.append(f"{label} -> physician {physician['id']} (DRY RUN — not written)")
                continue

            put_resp = client.put(
                f"/api/physicians/{physician['id']}/time-allocations",
                json={"year": IMPORT_YEAR, "allocations": allocations},
            )
            if put_resp.status_code != 200:
                skipped.append(f"{label}: PUT failed ({put_resp.status_code}): {put_resp.text}")
                continue

            grid = put_resp.json()
            matched.append(
                f"{label} -> physician {physician['id']}: "
                f"allocated_hours={grid['allocated_hours']}, clinical_pct={grid['clinical_pct']}"
            )

        print(f"=== Matched & updated ({len(matched)}) ===")
        for line in matched:
            print(f"  {line}")

        print(f"\n=== Skipped — needs manual review ({len(skipped)}) ===")
        for line in skipped:
            print(f"  {line}")

        print(f"\n=== Excel's own Total Hrs Check mismatches ({len(check_mismatches)}) ===")
        print("  (source data issues that predate this import, not caused by it)")
        for line in check_mismatches:
            print(f"  {line}")

        print(
            f"\nDone. {len(excel_rows)} rows read, {len(matched)} matched"
            f"{' (dry run — nothing written)' if DRY_RUN else ' and updated'}, "
            f"{len(skipped)} skipped, {len(check_mismatches)} source check mismatches."
        )


if __name__ == "__main__":
    main()
