#!/usr/bin/env python3
"""
One-time seed script: inserts the 10 prototype physicians and 3 leave events
into the running API at localhost:8001.

Run once after a fresh database: python3 seed_physicians.py
"""
import json
import sys
import urllib.request
import urllib.error

API = "http://localhost:8001/api"

# ── Site UUIDs (from SELECT id, name FROM sites) ──────────────────────────
MSH = "c49408d2-34c8-4ddd-8daa-fc90f8616361"  # Mount Sinai Hospital
MSB = "14da590d-43cf-4651-8fe3-8e6ed367a631"  # Mount Sinai Beth Israel
MSQ = "14ddd509-97c7-4d17-86fa-899ceb8069f0"  # Mount Sinai Queens

# ── provider_type ids (from SELECT id, name FROM provider_types) ──────────
MD  = 1
PA  = 3
NP  = 4
FME = 5   # Fellow - Med Ed
FIN = 9   # Fellow - Informatics

# ── role_type ids (from SELECT id, name FROM role_types) ──────────────────
RD   = 1   # Residency Director
ARD  = 2   # Associate Residency Director
FD   = 8   # Fellowship Director
ADM  = 15  # Administrative
KAW  = 12  # K Awardee


def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = json.loads(e.read()).get("detail", str(e))
        print(f"  ERROR {e.code} on POST {path}: {detail}", file=sys.stderr)
        raise


PHYSICIANS = [
    {
        "life_no": "10042", "last_name": "Abbott", "first_name": "Ethan",
        "provider_type_id": MD, "yearly_hours": 1440, "clinical_pct": 0.42,
        "core_site_id": MSH, "notes": "K Awardee end date TBD",
        "assignments": [{"site_id": MSH, "fte_fraction": 1.0}],
        "roles": [{"role_type_id": KAW, "hours_credit": 840}],
    },
    {
        "life_no": "10087", "last_name": "Brown", "first_name": "Cara",
        "provider_type_id": MD, "yearly_hours": 1440, "clinical_pct": 0.80,
        "core_site_id": MSH, "notes": "US Fellowship Director (20%)",
        "assignments": [{"site_id": MSH, "fte_fraction": 1.0}],
        "roles": [{"role_type_id": FD, "hours_credit": 200}, {"role_type_id": ADM, "hours_credit": 96}],
    },
    {
        "life_no": "10103", "last_name": "Rabin", "first_name": "Elaine",
        "provider_type_id": MD, "yearly_hours": 1440, "clinical_pct": 0.44,
        "core_site_id": MSH, "notes": "",
        "assignments": [{"site_id": MSH, "fte_fraction": 1.0}],
        "roles": [{"role_type_id": RD, "hours_credit": 810}],
    },
    {
        "life_no": "10055", "last_name": "Levene", "first_name": "Rachel",
        "provider_type_id": MD, "yearly_hours": 1440, "clinical_pct": 0.90,
        "core_site_id": MSH, "notes": "PEM Associate PD (10%), 1296 clinical hrs",
        "assignments": [{"site_id": MSH, "fte_fraction": 1.0}],
        "roles": [{"role_type_id": ARD, "hours_credit": 144}],
    },
    {
        "life_no": "10201", "last_name": "Goodin", "first_name": "Dania",
        "provider_type_id": MD, "yearly_hours": 1440, "clinical_pct": 0.50,
        "core_site_id": MSH, "notes": "Asst Director Diversity; 0.4 MSQ",
        "assignments": [{"site_id": MSH, "fte_fraction": 0.6}, {"site_id": MSQ, "fte_fraction": 0.4}],
        "roles": [{"role_type_id": ADM, "hours_credit": 48}],
    },
    {
        "life_no": "10312", "last_name": "Webb", "first_name": "Marcus",
        "provider_type_id": MD, "yearly_hours": 1440, "clinical_pct": 1.0,
        "core_site_id": MSH, "notes": "0.6 MSH, 0.4 MSB",
        "assignments": [{"site_id": MSH, "fte_fraction": 0.6}, {"site_id": MSB, "fte_fraction": 0.4}],
        "roles": [],
    },
    {
        "life_no": "10445", "last_name": "Patel", "first_name": "Vaishali",
        "provider_type_id": PA, "yearly_hours": 1440, "clinical_pct": 0.83,
        "core_site_id": MSH, "notes": "Director of PA Program (16.67%); .05 VUC",
        "assignments": [{"site_id": MSH, "fte_fraction": 1.0}],
        "roles": [{"role_type_id": ADM, "hours_credit": 240}],
    },
    {
        "life_no": "10502", "last_name": "Singh", "first_name": "Amar",
        "provider_type_id": NP, "yearly_hours": 1440, "clinical_pct": 1.0,
        "core_site_id": MSB, "notes": "0.5 MSH, 0.5 MSB",
        "assignments": [{"site_id": MSH, "fte_fraction": 0.5}, {"site_id": MSB, "fte_fraction": 0.5}],
        "roles": [],
    },
    {
        "life_no": "10601", "last_name": "Munday", "first_name": "Adam",
        "provider_type_id": FIN, "yearly_hours": 300, "clinical_pct": 1.0,
        "core_site_id": MSH, "notes": "7/1/25 - 6/30/27; Informatics Fellow",
        "assignments": [{"site_id": MSH, "fte_fraction": 0.6}, {"site_id": MSB, "fte_fraction": 0.4}],
        "roles": [{"role_type_id": ADM, "hours_credit": 0}],
    },
    {
        "life_no": "10701", "last_name": "Baldwin", "first_name": "Cassidy",
        "provider_type_id": FME, "yearly_hours": 900, "clinical_pct": 1.0,
        "core_site_id": MSH, "notes": "Term 6/30/27; Yr1 50/50 MSH/MSQ",
        "assignments": [{"site_id": MSH, "fte_fraction": 0.5}, {"site_id": MSQ, "fte_fraction": 0.5}],
        "roles": [],
    },
]

# ── Leaves reference physicians by position (0-indexed) ───────────────────
# p1=Abbott, p3=Rabin, p5=Goodin  (0-indexed: 0, 2, 4)
LEAVES_TEMPLATE = [
    {"physician_idx": 0, "leave_type": "Research Protected Time",
     "start_date": "2026-01-01", "end_date": "2026-12-31",
     "notes": "K Award protected time"},
    {"physician_idx": 2, "leave_type": "FMLA",
     "start_date": "2026-03-01", "end_date": "2026-04-30",
     "notes": ""},
    {"physician_idx": 4, "leave_type": "Maternity/Paternity",
     "start_date": "2026-06-01", "end_date": "2026-08-31",
     "notes": ""},
]


def main():
    print("Seeding physicians…")
    physician_ids = []
    for p in PHYSICIANS:
        result = post("/physicians/", p)
        physician_ids.append(result["id"])
        print(f"  ✓ {result['last_name']}, {result['first_name']} ({result['id']})")

    print("\nSeeding leaves…")
    for lt in LEAVES_TEMPLATE:
        ph_id = physician_ids[lt["physician_idx"]]
        result = post("/leaves/", {
            "physician_id": ph_id,
            "leave_type": lt["leave_type"],
            "start_date": lt["start_date"],
            "end_date": lt["end_date"],
            "notes": lt["notes"],
        })
        print(f"  ✓ Leave {result['leave_type']} for physician {ph_id[:8]}…")

    print("\nDone. Reload http://localhost:5173 to see the data.")


if __name__ == "__main__":
    main()
