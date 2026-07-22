#!/usr/bin/env python3
"""
See Your Whole Book — story seeder (Demo Centre gated tour 3).

Creates FIVE new households that legitimately trip the tour's step-4 flags
(matching stories/see-your-whole-book.md):

  - Overdue KYC review  (Next KYC Review in the past)
  - Gone quiet          (Date Last Contacted > 90 days, matching a real
                         last interaction — never a bare UDF date)

Scope (Lewis, 2026-07-20): NO investment or insurance data. The
account-movement / assets / GIC beats are dealer-feed data the engine
cannot fabricate; the capture cuts those flags rather than faking them.
Notes avoid products and account values on purpose.

Tenant constraints honoured (CLAUDE.md): dates relative, times
Pacific->UTC via zoneinfo, validated payload shapes only, keys to
manifest, 429 pacing, audit-note sweep, read-back verification.

Run:    python3 seed-see-your-whole-book.py
        python3 seed-see-your-whole-book.py --cleanup
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifests",
                        "see-your-whole-book-manifest.json")

TODAY = datetime.now()
PACE = 0.35  # seconds between calls (429 protection, validated)

SEG = "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)"
NEXTKYC = "Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)"
LASTCONTACT = "Udf/$TYPEID(60059)"
BIRTHDATE = "Udf/$TYPEID(124)"


def d(days_offset: int, hm: str = "10:00") -> str:
    """API datetime, days relative to today; hm is INTENDED Pacific wall time,
    converted to UTC (rule 7b, validated 2026-07-15)."""
    from zoneinfo import ZoneInfo
    day = TODAY + timedelta(days=days_offset)
    hour, minute = int(hm[:2]), int(hm[3:5])
    local = day.replace(hour=hour, minute=minute, second=0, microsecond=0,
                        tzinfo=ZoneInfo("America/Vancouver"))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def call(endpoint: str, payload: dict, quiet: bool = False) -> dict:
    time.sleep(PACE)
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if r.status_code == 429:
        wait = int(r.headers.get("Retry-After", "5"))
        print(f"  .. rate limited, waiting {wait}s")
        time.sleep(wait)
        return call(endpoint, payload, quiet)
    r.raise_for_status()
    data = r.json()
    if data.get("Code", 0) != 0 and not quiet:
        print(f"  !! Code={data.get('Code')} on {endpoint}: {json.dumps(data)[:500]}")
    return data


def created_key(data: dict, obj: str) -> Optional[str]:
    return data.get(obj, {}).get("Data", {}).get("Key")


def remember(manifest: dict, kind: str, key: Optional[str], label: str) -> None:
    if key:
        manifest.setdefault("records", []).append({"kind": kind, "key": key, "label": label})
        print(f"  + {kind}: {label}")
    else:
        print(f"  - FAILED {kind}: {label}")


def _save(manifest: dict) -> None:
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)


# ---------------------------------------------------------------- create helpers

def create_household(manifest: dict, name: str, addr1: str, city: str, prov: str,
                     postal: str, phone: str) -> Optional[str]:
    data = call("Create", {
        "AbEntry": {"Data": {
            "Key": None, "Type": "Household", "CompanyName": name,
            "Address": {"AddressLine1": addr1, "City": city,
                        "StateProvince": prov, "Country": "Canada", "ZipCode": postal},
            "Phone1": {"Number": phone},
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    key = created_key(data, "AbEntry")
    if key:
        remember(manifest, "AbEntry", key, f"{name} (Household)")
    else:
        print(f"  household create rejected ({name}): {json.dumps(data)[:300]}")
    return key


def create_contact(manifest: dict, parent_key: str, first: str, last: str,
                   age: int, email: str, phone: str) -> Optional[str]:
    birthdate = (TODAY - timedelta(days=age * 365 + (age * 37) % 200)).strftime("%Y-%m-%d")
    data = call("Create", {
        "AbEntry": {"Data": {
            "Key": None, "Type": "Contact", "ParentKey": parent_key,
            "FirstName": first, "LastName": last,
            "Email": {"Address": email}, "Phone1": {"Number": phone},
            BIRTHDATE: birthdate,
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    key = created_key(data, "AbEntry")
    if not key:  # retry without birthdate rather than fail the story
        data = call("Create", {
            "AbEntry": {"Data": {
                "Key": None, "Type": "Contact", "ParentKey": parent_key,
                "FirstName": first, "LastName": last,
                "Email": {"Address": email}, "Phone1": {"Number": phone},
            }},
            "Compatibility": {"AbEntryKey": "2.0"},
        }, quiet=True)
        key = created_key(data, "AbEntry")
        if key:
            print(f"    ({first}: created WITHOUT birthdate - set manually)")
    remember(manifest, "AbEntry", key, f"{first} {last}")
    return key


def set_profile(abentry_key: str, label: str, segmentation: str,
                kyc_days_offset: int, last_contact_days_ago: int) -> None:
    """Segmentation + Next KYC Review (negative offset = OVERDUE) +
    Date Last Contacted. All validated assignable UDFs; audit notes swept."""
    data = call("Update", {
        "AbEntry": {"Data": {
            "Key": abentry_key,
            SEG: segmentation,
            NEXTKYC: (TODAY + timedelta(days=kyc_days_offset)).strftime("%Y-%m-%d"),
            LASTCONTACT: (TODAY - timedelta(days=last_contact_days_ago)).strftime("%Y-%m-%d"),
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    ok = data.get("Code", 0) == 0
    print(f"  {'+' if ok else '-'} profile set: {label}")


def interaction_type_key(display_contains: str) -> Optional[str]:
    data = call("Read", {
        "InteractionLog": {"FieldOptions": {"Type": [{"Key": 1, "DisplayValue": 1}]}},
        "Compatibility": {"SchemaObject": "1.0"},
    }, quiet=True)
    for opt in data.get("InteractionLog", {}).get("FieldOptions", {}).get("Type", []) or []:
        if display_contains.lower() in str(opt.get("DisplayValue", "")).lower():
            return str(opt.get("Key"))
    return None


def create_call_log(manifest: dict, abentry_key: str, type_key: str, subject: str,
                    description: str, days_ago: int, duration_min: int,
                    direction: int = 2) -> None:
    end_minute = duration_min % 60
    payload = {
        "Key": None, "Subject": subject, "Description": description,
        "Type": type_key,
        "StartDate": d(-days_ago, "10:00"),
        "EndDate": d(-days_ago, f"10:{end_minute:02d}"),
        "User": "$CURRENTUSER()", "AbEntryKey": abentry_key, "Direction": direction,
    }
    data = call("Create", {"InteractionLog": {"Data": payload},
                           "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "InteractionLog", created_key(data, "InteractionLog"), subject)


def create_note(manifest: dict, parent_key: str, text: str, days_ago: int,
                hm: str = "14:30") -> None:
    data = call("Create", {"Note": {"Data": {
        "Key": None, "ParentKey": parent_key,
        "DateTime": d(-days_ago, hm), "Text": text,
    }}})
    remember(manifest, "Note", created_key(data, "Note"), text[:48])


def create_appointment(manifest: dict, abentry_keys: list, subject: str,
                       description: str, days_ago: int) -> None:
    data = call("Create", {"Appointment": {"Data": {
        "Key": None, "Subject": subject,
        "StartDate": d(-days_ago, "10:00"), "EndDate": d(-days_ago, "11:00"),
        "Description": description, "AbEntries": abentry_keys,
    }}, "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "Appointment", created_key(data, "Appointment"), subject)


# ---------------------------------------------------------------- audit sweep

AUDIT_MARKERS = ("Hotlist Task Created", "Hotlist Task Modified", "Opportunity created",
                 "changed from", "Changed from")


def sweep_audit_notes(manifest: dict, parent_keys: list) -> None:
    ours = {r["key"] for r in manifest.get("records", []) if r["kind"] == "Note"}
    swept = 0
    for pk in parent_keys:
        if not pk:
            continue
        data = call("Read", {"Note": {
            "Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
            "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": pk}}},
        }}, quiet=True)
        for note in data.get("Note", {}).get("Data", []) or []:
            key, text = note.get("Key"), str(note.get("Text", ""))
            if key in ours:
                continue
            if any(m in text for m in AUDIT_MARKERS):
                dele = call("Delete", {"Note": {"Data": {"Key": key}}}, quiet=True)
                if dele.get("Code", 0) == 0:
                    swept += 1
    print(f"  swept {swept} audit note(s)")


# ---------------------------------------------------------------- verify

def verify_flags(households: list) -> None:
    """Read back KYC + Date Last Contacted and print which flag each
    household trips. The tour needs at least 3 overdue and 3 quiet."""
    today = TODAY.date()
    overdue_n, quiet_n = 0, 0
    for name, key in households:
        if not key:
            continue
        data = call("Read", {
            "AbEntry": {"Scope": {"Fields": {"Key": 1, NEXTKYC: 1, LASTCONTACT: 1}},
                        "Criteria": {"SearchQuery": {"Key": {"$EQ": key}}}},
            "Compatibility": {"AbEntryKey": "2.0"},
        }, quiet=True)
        rows = data.get("AbEntry", {}).get("Data", []) or []
        row = rows[0] if rows else {}
        kyc_raw = row.get(NEXTKYC)
        lc_raw = row.get(LASTCONTACT)
        kyc_raw = kyc_raw[0] if isinstance(kyc_raw, list) and kyc_raw else kyc_raw
        lc_raw = lc_raw[0] if isinstance(lc_raw, list) and lc_raw else lc_raw
        flags = []
        if kyc_raw:
            kyc_date = datetime.strptime(str(kyc_raw)[:10], "%Y-%m-%d").date()
            if kyc_date < today:
                flags.append(f"KYC overdue {(today - kyc_date).days}d")
                overdue_n += 1
        if lc_raw:
            lc_date = datetime.strptime(str(lc_raw)[:10], "%Y-%m-%d").date()
            gap = (today - lc_date).days
            if gap > 90:
                flags.append(f"quiet {gap}d")
                quiet_n += 1
        print(f"  {name}: {', '.join(flags) if flags else 'NO FLAGS - check profile write'}")
    print(f"  => {overdue_n} overdue-review, {quiet_n} gone-quiet "
          f"({'OK' if overdue_n >= 3 and quiet_n >= 3 else 'BELOW TARGET - paste this back'})")


# ---------------------------------------------------------------- cleanup

def cleanup() -> None:
    if not os.path.exists(MANIFEST):
        sys.exit(f"No manifest at {MANIFEST} - nothing to clean.")
    with open(MANIFEST) as f:
        manifest = json.load(f)
    for rec in reversed(manifest.get("records", [])):
        data = call("Delete", {rec["kind"]: {"Data": {"Key": rec["key"]}}}, quiet=True)
        ok = data.get("Code", 0) == 0
        print(f"  {'deleted' if ok else 'FAILED to delete'} {rec['kind']}: {rec['label']}")
    os.remove(MANIFEST)
    print("Manifest removed.")


# ---------------------------------------------------------------- story data
#
# Five households. Days/gaps are all relative to seed day. Notes carry NO
# account values, products, or policies (scope decision 2026-07-20).
# last_contact_days_ago always equals the newest interaction's days_ago.

HOUSEHOLDS = [
    {
        "name": "Okafor Family", "hero": True,
        "addr": ("214 Aberdeen Ave", "Hamilton", "ON", "L8P 2P4", "(555) 010-7801"),
        "contacts": [("Dominic", "Okafor", 57, "dominic.okafor@mail.test", "(555) 010-7802"),
                     ("Rose", "Okafor", 54, "rose.okafor@mail.test", "(555) 010-7803")],
        "segmentation": "2",     # B - solid client, drifting
        "kyc_offset": -21,       # overdue 3 weeks
        "last_contact": 135,     # quiet ~4.5 months
        "appointments": [
            (1100, "Okafor household annual review", "Annual review meeting."),
            (745, "Okafor household annual review", "Annual review meeting."),
            (390, "Okafor household annual review", "Annual review meeting."),
        ],
        "notes": [
            (1100, "Annual review completed. KYC refreshed, no material changes. "
                   "Cadence agreed: yearly review plus spring check-in."),
            (745, "Annual review completed. Updated employment details for Dominic. "
                  "KYC refreshed."),
            (390, "Annual review completed. Rose asked about consolidating "
                  "correspondence to email. KYC refresh due next cycle."),
            (150, "Spring check-in postponed by client - Rose to call back with "
                  "new dates after their trip. To rebook."),
        ],
        "calls": [
            (930, "Dominic - statement access", "Walked through portal login after address change.", 8, 1),
            (560, "Rose - meeting reschedule", "Moved review out two weeks; calendar updated.", 6, 1),
            (135, "Rose - mailing address update", "Updated mailing address after the move to Aberdeen Ave.", 7, 1),
        ],
    },
    {
        "name": "Whitfield Family", "hero": False,
        "addr": ("52 Moss St", "Victoria", "BC", "V8V 4M2", "(555) 010-7811"),
        "contacts": [("Graham", "Whitfield", 61, "graham.whitfield@mail.test", "(555) 010-7812")],
        "segmentation": "3",     # C
        "kyc_offset": 140,       # current - quiet flag only
        "last_contact": 100,
        "appointments": [(470, "Whitfield annual review", "Annual review meeting.")],
        "notes": [(470, "Annual review completed. KYC refreshed, no changes. "
                        "Graham prefers phone over email.")],
        "calls": [
            (100, "Graham - reschedule request", "Asked to move the summer check-in; no new date set.", 5, 1),
        ],
    },
    {
        "name": "Bianchi Family", "hero": False,
        "addr": ("3390 Havenwood Dr", "Mississauga", "ON", "L4X 2M2", "(555) 010-7821"),
        "contacts": [("Carla", "Bianchi", 48, "carla.bianchi@mail.test", "(555) 010-7822")],
        "segmentation": "2",     # B
        "kyc_offset": -42,       # overdue 6 weeks - overdue flag only
        "last_contact": 31,      # contact is recent
        "appointments": [(400, "Bianchi annual review", "Annual review meeting.")],
        "notes": [(400, "Annual review completed. KYC refresh flagged for follow-up - "
                        "documents not returned at meeting.")],
        "calls": [
            (31, "Carla - callback on paperwork", "Reminded re: outstanding KYC forms; she will drop them off.", 9, 2),
        ],
    },
    {
        "name": "Grewal Family", "hero": False,
        "addr": ("7788 152nd St", "Surrey", "BC", "V3S 3M4", "(555) 010-7831"),
        "contacts": [("Harjit", "Grewal", 52, "harjit.grewal@mail.test", "(555) 010-7832"),
                     ("Simran", "Grewal", 50, "simran.grewal@mail.test", "(555) 010-7833")],
        "segmentation": "2",     # B
        "kyc_offset": -14,       # overdue 2 weeks
        "last_contact": 120,     # AND quiet ~4 months
        "appointments": [(485, "Grewal household annual review", "Annual review meeting.")],
        "notes": [(485, "Annual review completed. KYC refreshed. Discussed meeting "
                        "cadence; Harjit travelling for work much of this year.")],
        "calls": [
            (120, "Harjit - brief check-in", "Short call before his travel; review to be booked on return.", 4, 2),
        ],
    },
    {
        "name": "Fortin Family", "hero": False,
        "addr": ("19 rue Garneau", "Gatineau", "QC", "J8X 2V5", "(555) 010-7841"),
        "contacts": [("Marc-Andre", "Fortin", 44, "marcandre.fortin@mail.test", "(555) 010-7842")],
        "segmentation": "3",     # C
        "kyc_offset": 200,       # current - borderline quiet flag only
        "last_contact": 95,
        "appointments": [(430, "Fortin annual review", "Annual review meeting.")],
        "notes": [(430, "Annual review completed. KYC refreshed, no changes.")],
        "calls": [
            (95, "Marc-Andre - quick question", "Confirmed statement mailing frequency; no follow-up needed.", 3, 1),
        ],
    },
]


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true")
    args = ap.parse_args()

    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only). Load .env from the repo root.")

    if args.cleanup:
        cleanup()
        return

    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). Run --cleanup first.")

    manifest = {"story": "see-your-whole-book", "created": TODAY.isoformat()}

    print("1) Interaction type id ...")
    phone = interaction_type_key("phone")
    print(f"  phone type={phone}")

    households_created = []
    all_parents = []

    for i, hh_def in enumerate(HOUSEHOLDS, 1):
        addr1, city, prov, postal, hh_phone = hh_def["addr"]
        print(f"\n{i + 1}) {hh_def['name']} "
              f"({'HERO - step 5 click-in' if hh_def['hero'] else 'flag texture'}) ...")
        hh = create_household(manifest, hh_def["name"], addr1, city, prov, postal, hh_phone)
        if not hh:
            _save(manifest)
            sys.exit(f"Household creation failed on {hh_def['name']} - paste this output back.")
        households_created.append((hh_def["name"], hh))
        all_parents.append(hh)

        contact_keys = []
        for first, last, age, email, cphone in hh_def["contacts"]:
            ck = create_contact(manifest, hh, first, last, age, email, cphone)
            if ck:
                contact_keys.append(ck)
                all_parents.append(ck)

        # profiles: household + contacts share the same flag dates
        for k, label in [(hh, f"{hh_def['name']} household")] + \
                        [(ck, "contact") for ck in contact_keys]:
            set_profile(k, label, hh_def["segmentation"],
                        hh_def["kyc_offset"], hh_def["last_contact"])

        for days_ago, subject, desc in hh_def["appointments"]:
            create_appointment(manifest, contact_keys or [hh], subject, desc, days_ago)
        for days_ago, text in hh_def["notes"]:
            create_note(manifest, hh, text, days_ago)
        if phone:
            for days_ago, subject, desc, dur, direction in hh_def["calls"]:
                create_call_log(manifest, hh, phone, subject, desc, days_ago, dur, direction)
        else:
            print("  !! phone type id not found - calls skipped, tell Claude")

    print("\n7) Sweeping audit notes ...")
    sweep_audit_notes(manifest, all_parents)

    print("\n8) Verifying flags with read-backs ...")
    verify_flags(households_created)

    _save(manifest)
    n = len(manifest.get("records", []))
    print(f"\nDone: {n} records created. Manifest: {MANIFEST}")
    print("\nEyeball checklist (Maximizer UI):")
    print("  - Address Book: 5 new households (Okafor, Whitfield, Bianchi, Grewal, Fortin)")
    print("  - Okafor Family: history spans ~3 years and visibly STOPS ~4.5 months ago;")
    print("    NO upcoming appointment; KYC overdue ~3 weeks. This is the step-5 click-in.")
    print("  - a book-wide view/search on Next KYC Review < today finds 3 households")
    print("  - a book-wide view on Date Last Contacted > 90 days finds 3 households")
    print("  - no same-day 'changed from X to Y' audit notes remain")
    print("\nCapture notes (scope decision 2026-07-20):")
    print("  - frame step 4 on the overdue-review and gone-quiet flags ONLY;")
    print("    cut the account-movement flag (dealer feed not populated)")
    print("  - step 5's assets/GIC beats are investment data - avoid those panels")
    print(f"\nRemove the whole story:  python3 seed-see-your-whole-book.py --cleanup")


if __name__ == "__main__":
    main()
