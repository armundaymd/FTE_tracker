#!/usr/bin/env python3
"""
Import physicians from 2026-staffing.xlsx into the ed_capacity database.

Rules:
 - Skips rows that are totals / blank (no last_name).
 - Skips any physician already in the DB (matched by last_name + first_name,
   case-insensitive). Existing records are preserved unchanged.
 - Deduplicates within the spreadsheet itself (Rosario appears twice).
 - Creates site_assignments for MSH always; adds MSQ/MSB when notes say so.
 - Parses physician_roles from the Role(s) column (hours_credit and pct_credit).

Run: python3 import_staffing.py
Requires: openpyxl  (pip3 install openpyxl)
Requires: Docker container fte-scheduler-postgres-1 running.
"""

import re
import subprocess
import sys
import uuid
import openpyxl

CONTAINER = "fte-scheduler-postgres-1"
DB_USER = "postgres"
DB_NAME = "ed_capacity"

# ── Site UUIDs (from schema seed) ────────────────────────────────────────────
MSH = "c49408d2-34c8-4ddd-8daa-fc90f8616361"
MSB = "14da590d-43cf-4651-8fe3-8e6ed367a631"
MSQ = "14ddd509-97c7-4d17-86fa-899ceb8069f0"

# ── Provider type IDs ─────────────────────────────────────────────────────────
PT = {
    "MD": 1, "DO": 2, "PA": 3, "NP": 4,
    "Fellow - Med Ed": 5, "Fellow - US": 6, "Fellow - SIM": 7,
    "Fellow - Sports Med": 8, "Fellow - Informatics": 9,
}

# ── Role type IDs ─────────────────────────────────────────────────────────────
# Keyword → role_type id.  Checked in order; first match wins per token.
ROLE_KEYWORDS = [
    ("residency director",            1),
    ("associate residency director",  2),
    ("assistant residency",           3),   # catches "Assistant Residency PD", etc.
    ("assist resident pd",            3),
    ("assist resident",               3),
    ("medical director",              4),
    ("associate medical director",    5),
    ("associate med director",        5),
    ("vice chair",                    6),
    ("vc research",                   6),
    ("vc clinical",                   6),
    ("program director",              7),
    ("fellowship director",           8),
    ("fellowship pd",                 8),
    ("fellow pd",                     8),
    ("pem director",                  8),
    ("sim director",                  8),
    ("clerkship director",            9),
    ("assistant clerkship",           9),
    ("nocturnist",                   10),
    ("scheduler",                    11),
    ("k awardee",                    12),
    ("kawardee",                     12),
    ("k award",                      12),
    ("research grant",               13),
    ("med ed",                       14),
    ("administrative",               15),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_sql(sql: str, fetch=False) -> str:
    cmd = ["docker", "exec", "-i", CONTAINER, "psql",
           "-U", DB_USER, "-d", DB_NAME, "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"SQL failed:\n{res.stderr}\nSQL: {sql[:300]}")
    return res.stdout.strip()


def escape(val) -> str:
    """Return SQL-safe quoted string or NULL."""
    if val is None:
        return "NULL"
    s = str(val).replace("'", "''")
    return f"'{s}'"


def num(val, default="NULL") -> str:
    """Return numeric literal or NULL/default."""
    if val is None:
        return str(default)
    try:
        return str(float(val))
    except (ValueError, TypeError):
        return str(default)


def infer_provider_type(role_str: str | None, yearly_hours: int | None) -> int:
    """Infer provider_type id from role text and yearly hours."""
    if role_str:
        rl = role_str.lower()
        if "informatics fellow" in rl:
            return PT["Fellow - Informatics"]
        if "sim fellow" in rl:
            return PT["Fellow - SIM"]
        if "sports med fellow" in rl or "sports fellow" in rl:
            return PT["Fellow - Sports Med"]
        if "us fellow" in rl:
            return PT["Fellow - US"]
        if "med ed fellow" in rl:
            return PT["Fellow - Med Ed"]
        if "pem fellow" in rl:
            return PT["Fellow - Med Ed"]
    if yearly_hours:
        if yearly_hours == 300:
            return PT["Fellow - Informatics"]
        if yearly_hours == 450:
            return PT["Fellow - Sports Med"]
        if yearly_hours == 900:
            return PT["Fellow - Med Ed"]  # best guess for 900-hr fellows
    return PT["MD"]


def parse_role_tokens(role_str: str | None):
    """
    Split 'Role A (200 hrs), Role B (10%)' into a list of dicts:
      [{"title": str, "role_type_id": int|None,
        "hours_credit": int, "pct_credit": float|None}]
    """
    if not role_str:
        return []

    tokens = [t.strip() for t in role_str.split(",")]
    results = []
    for token in tokens:
        if not token:
            continue
        tl = token.lower()

        # Extract hours / pct from parenthetical
        hours_credit = 0
        pct_credit = None

        m_hrs = re.search(r"\((\d+)\s*hrs?\)", token, re.IGNORECASE)
        if m_hrs:
            hours_credit = int(m_hrs.group(1))

        m_pct = re.search(r"\((\d+(?:\.\d+)?)\s*%\)", token)
        if m_pct:
            pct_credit = round(float(m_pct.group(1)) / 100, 4)

        # Match role type
        role_type_id = None
        for kw, rid in ROLE_KEYWORDS:
            if kw in tl:
                role_type_id = rid
                break

        if role_type_id is None:
            role_type_id = 16  # Other

        results.append({
            "title": token.strip(),
            "role_type_id": role_type_id,
            "hours_credit": hours_credit,
            "pct_credit": pct_credit,
        })
    return results


def infer_other_site(notes: str | None) -> str | None:
    """Return site UUID if notes clearly name MSQ or MSB as the other site."""
    if not notes:
        return None
    n = notes.upper()
    if "MSQ" in n:
        return MSQ
    if "MSB" in n or "MSBI" in n:
        return MSB
    return None


# ── Load spreadsheet ──────────────────────────────────────────────────────────

def load_rows(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["MD Staffing Grid"]

    rows = []
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=2, max_row=93, values_only=True), start=2
    ):
        last = row[1]
        first = row[2]

        # Skip blank / totals rows
        if not last or not first:
            continue
        last_s = str(last).strip()
        first_s = str(first).strip()
        if last_s in ("Total", "Schedule", "Staffing", "FTE") or first_s in (
            "Faculty", "Total", "Physician", "Margin",
        ):
            continue

        life_raw = row[0]
        life_no = None if (life_raw is None or str(life_raw).startswith("#")) else str(life_raw).strip()

        role_str  = str(row[3]).strip() if row[3] else None
        core_raw  = str(row[4]).strip() if row[4] else None
        notes_raw = str(row[5]).strip() if row[5] else None
        # Normalise 'None' strings from the cell evaluator
        notes_val = None if notes_raw in (None, "None") else notes_raw

        total_fte = row[6]
        msh_fte   = row[7]
        other_fte = row[8]
        fte_hrs   = row[11]
        clinical  = row[14]   # annual clinical hours

        is_core = bool(core_raw and "Y" in core_raw.upper())

        # clinical_pct = annual_clinical_hrs / (fte * yearly_hrs)
        try:
            clin_pct = round(float(clinical) / (float(total_fte) * float(fte_hrs)), 4)
            clin_pct = max(0.0, min(1.0, clin_pct))
        except (TypeError, ValueError, ZeroDivisionError):
            clin_pct = 1.0  # DB default; applies to fellows with no hours data

        rows.append({
            "row":          row_idx,
            "last_name":    last_s,
            "first_name":   first_s,
            "life_no":      life_no,
            "role_str":     role_str,
            "is_core":      is_core,
            "notes":        notes_val,
            "total_fte":    total_fte,
            "msh_fte":      msh_fte,
            "other_fte":    other_fte,
            "yearly_hours": int(fte_hrs) if fte_hrs else 1440,
            "clinical_pct": clin_pct,
            "provider_type_id": infer_provider_type(role_str, int(fte_hrs) if fte_hrs else None),
        })
    return rows


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    path = "2026-staffing.xlsx"
    print(f"Reading {path}…")
    rows = load_rows(path)
    print(f"  {len(rows)} data rows found in spreadsheet.")

    # Fetch existing physicians from DB
    existing_raw = run_sql(
        "SELECT LOWER(last_name), LOWER(first_name) FROM physicians;"
    )
    existing = set()
    for line in existing_raw.splitlines():
        parts = line.split("|")
        if len(parts) == 2:
            existing.add((parts[0].strip(), parts[1].strip()))

    print(f"  {len(existing)} physicians already in DB — will be skipped.")

    inserted = 0
    skipped_dup_db = 0
    skipped_dup_sheet = 0
    seen_in_sheet: set[tuple[str, str]] = set()

    for r in rows:
        key = (r["last_name"].lower(), r["first_name"].lower())

        # Dedup within spreadsheet
        if key in seen_in_sheet:
            print(f"  SKIP (dupe in sheet) row {r['row']}: {r['last_name']}, {r['first_name']}")
            skipped_dup_sheet += 1
            continue
        seen_in_sheet.add(key)

        # Dedup against DB
        if key in existing:
            print(f"  SKIP (already in DB) : {r['last_name']}, {r['first_name']}")
            skipped_dup_db += 1
            continue

        # ── INSERT physician ──────────────────────────────────────────────
        phys_id = str(uuid.uuid4())

        sql_phys = f"""
INSERT INTO physicians (
    id, last_name, first_name, life_no,
    provider_type_id, yearly_hours, clinical_pct, total_fte,
    core_site_id, is_core_faculty, is_active, notes
) VALUES (
    '{phys_id}',
    {escape(r['last_name'])},
    {escape(r['first_name'])},
    {escape(r['life_no'])},
    {r['provider_type_id']},
    {r['yearly_hours']},
    {num(r['clinical_pct'], 'NULL')},
    {num(r['total_fte'], 'NULL')},
    '{MSH}',
    {'TRUE' if r['is_core'] else 'FALSE'},
    TRUE,
    {escape(r['notes'])}
);"""
        try:
            run_sql(sql_phys)
        except RuntimeError as e:
            print(f"  ERROR inserting physician {r['last_name']}, {r['first_name']}: {e}", file=sys.stderr)
            continue

        # ── INSERT site assignments ───────────────────────────────────────
        msh_fte = r["msh_fte"]
        if msh_fte and float(msh_fte) > 0:
            sa_id = str(uuid.uuid4())
            run_sql(f"""
INSERT INTO site_assignments (id, physician_id, site_id, fte_fraction, effective_date)
VALUES ('{sa_id}', '{phys_id}', '{MSH}', {float(msh_fte)}, '2026-01-01');""")

        other_fte = r["other_fte"]
        other_site = infer_other_site(r["notes"])
        if other_site and other_fte and float(other_fte) > 0:
            sa_id2 = str(uuid.uuid4())
            run_sql(f"""
INSERT INTO site_assignments (id, physician_id, site_id, fte_fraction, effective_date)
VALUES ('{sa_id2}', '{phys_id}', '{other_site}', {float(other_fte)}, '2026-01-01');""")

        # ── INSERT physician roles ────────────────────────────────────────
        for role in parse_role_tokens(r["role_str"]):
            pr_id = str(uuid.uuid4())
            run_sql(f"""
INSERT INTO physician_roles (
    id, physician_id, role_type_id, custom_title,
    hours_credit, pct_credit, effective_date
) VALUES (
    '{pr_id}', '{phys_id}',
    {role['role_type_id']},
    {escape(role['title'])},
    {role['hours_credit']},
    {num(role['pct_credit'], 'NULL')},
    '2026-01-01'
);""")

        print(f"  INSERTED row {r['row']}: {r['last_name']}, {r['first_name']}")
        inserted += 1

    print(f"\nDone.")
    print(f"  Inserted : {inserted}")
    print(f"  Skipped (already in DB)   : {skipped_dup_db}")
    print(f"  Skipped (dupe in sheet)   : {skipped_dup_sheet}")


if __name__ == "__main__":
    main()
