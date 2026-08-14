#!/usr/bin/env python3
"""
Webinar McGill Catch — story seeder (creates the NEW Halloran household).

For the Aug 19 Focal AI + Maximizer webinar recording (Fri Aug 14).
The demo beat: in the meeting John captures with Focal, Dan mentions in
passing that Maya got into McGill. IQ Boost connects that line to context
already on the Maximizer record. This seeder creates the household and
that context:

  Cast:  Halloran Family household — Dan (54), Priya (52), Maya (17).
  1. Spring review note (~14 weeks back) for believable recent history.
  2. Thin "before" note (~5 months back): the two-line human note.
  3. RESP allocation note (~2 years back): still growth-allocated,
     glide-path change planned "as Maya approaches university".
  4. Open task (~2 years back, deliberately old and forgotten):
     "Revisit RESP allocation when Maya gets close to university".
  5. Incoming call from Priya (~9 weeks back, mid-June feel): raised
     possibly selling the cottage. (Emails cannot be fabricated on this
     tenant — the cottage moment is a logged CALL.)

Standalone story: its own household, its own manifest, clean removal via
--cleanup without touching walk-in-ready or any other story. Owners set
per CLAUDE.md rule 10 (MASTER).

Run:    cd "$HOME/Claude Code/demo-engine"
        set -a; source .env; set +a
        python3 engine/seed-webinar-mcgill.py
Clean:  python3 engine/seed-webinar-mcgill.py --cleanup
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
    sys.exit("pip3 install requests --break-system-packages")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "manifests", "webinar-mcgill-catch-manifest.json")

MASTER = "VXNlcglNQVNURVI="  # rule 10: explicit owner, displays "Barb Smith"
TODAY = datetime.now()


def d(days_offset: int, hm: str = "10:00") -> str:
    """Intended-Pacific wall clock -> UTC string (CLAUDE.md rule 7b)."""
    from zoneinfo import ZoneInfo
    day = TODAY + timedelta(days=days_offset)
    hour, minute = int(hm[:2]), int(hm[3:5])
    local = day.replace(hour=hour, minute=minute, second=0, microsecond=0,
                        tzinfo=ZoneInfo("America/Vancouver"))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def call(endpoint: str, payload: dict, quiet: bool = False) -> dict:
    time.sleep(0.4)  # 429 pacing per CLAUDE.md
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    if r.status_code == 429:
        time.sleep(float(r.headers.get("Retry-After", "2")))
        r = requests.post(f"{BASE}/{endpoint}",
                          headers={"Authorization": f"Bearer {PAT}",
                                   "Content-Type": "application/json"},
                          json=payload, timeout=30)
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
        _save(manifest)  # incremental: a mid-run crash must not orphan keys (rule 3)
        print(f"  + {kind}: {label}")
    else:
        print(f"  - FAILED {kind}: {label}")


def create_household(manifest: dict) -> Optional[str]:
    # CompanyName shape is the only validated household create (CLAUDE.md).
    data = call("Create", {
        "AbEntry": {"Data": {
            "Key": None, "Type": "Household", "CompanyName": "Halloran Family",
            "Address": {"AddressLine1": "86 Glenview Cres", "City": "Toronto",
                        "StateProvince": "ON", "Country": "Canada", "ZipCode": "M4R 1P7"},
            "Phone1": {"Number": "(555) 010-8830"},
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    })
    key = created_key(data, "AbEntry")
    remember(manifest, "AbEntry", key, "Halloran Family (Household)")
    return key


def create_contact(manifest: dict, parent_key: str, first: str, last: str,
                   birthdate: str, email: str) -> Optional[str]:
    data = call("Create", {
        "AbEntry": {"Data": {
            "Key": None, "Type": "Contact", "ParentKey": parent_key,
            "FirstName": first, "LastName": last,
            "Email": {"Address": email},
            "Phone1": {"Number": "(555) 010-8831"},
            "Udf/$TYPEID(124)": birthdate,  # validated Birthdate UDF
        }},
        "Compatibility": {"AbEntryKey": "2.0"},
    })
    key = created_key(data, "AbEntry")
    remember(manifest, "AbEntry", key, f"{first} {last}")
    return key


def phone_type_key() -> Optional[str]:
    data = call("Read", {
        "InteractionLog": {"FieldOptions": {"Type": [{"Key": 1, "DisplayValue": 1}]}},
        "Compatibility": {"AbEntryKey": "2.0"},
    }, quiet=True)
    for opt in data.get("InteractionLog", {}).get("FieldOptions", {}).get("Type", []) or []:
        if "phone" in str(opt.get("DisplayValue", "")).lower():
            return str(opt.get("Key"))
    return None


def create_note(manifest: dict, parent_key: str, text: str, days_ago: int, hm: str) -> None:
    data = call("Create", {"Note": {"Data": {
        "Key": None, "ParentKey": parent_key,
        "DateTime": d(-days_ago, hm), "Text": text,
    }}})
    remember(manifest, "Note", created_key(data, "Note"), text[:50])


def sweep_audit_notes(hh: str) -> None:
    """Delete same-day auto-logged audit notes on the household (rule 5)."""
    data = call("Read", {"Note": {
        "Scope": {"Fields": {"Key": 1, "Text": 1, "DateTime": 1}},
        "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": hh}}},
    }}, quiet=True)
    today = TODAY.strftime("%Y-%m-%d")
    swept = 0
    for note in data.get("Note", {}).get("Data", []) or []:
        text = str(note.get("Text", ""))
        dt = str(note.get("DateTime", ""))
        if dt.startswith(today) and ("Hotlist Task" in text or "Opportunity created" in text):
            call("Delete", {"Note": {"Data": {"Key": note["Key"]}}}, quiet=True)
            swept += 1
    print(f"  audit notes swept: {swept}")


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
    print("Manifest removed. (No other story was touched.)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true")
    args = ap.parse_args()

    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (source .env — demo tenant only).")
    if args.cleanup:
        cleanup()
        return
    if os.path.exists(MANIFEST):
        sys.exit(f"Manifest already exists ({MANIFEST}). Run --cleanup first.")

    manifest = {"story": "webinar-mcgill-catch", "created": TODAY.isoformat()}

    print("1) Creating the Halloran household ...")
    hh = create_household(manifest)
    if not hh:
        _save(manifest)
        sys.exit("Household creation failed - paste this output back.")

    print("2) Creating household members ...")
    create_contact(manifest, hh, "Dan", "Halloran",
                   (TODAY - timedelta(days=54 * 365 + 140)).strftime("%Y-%m-%d"),
                   "dan.halloran@mail.test")
    create_contact(manifest, hh, "Priya", "Halloran",
                   (TODAY - timedelta(days=52 * 365 + 60)).strftime("%Y-%m-%d"),
                   "priya.halloran@mail.test")
    create_contact(manifest, hh, "Maya", "Halloran",
                   (TODAY - timedelta(days=17 * 365 + 210)).strftime("%Y-%m-%d"),
                   "maya.halloran@mail.test")

    print("3) Building the record context ...")
    # Spring review (~14 weeks back): believable recent history.
    create_note(manifest, hh,
                "Spring review with Dan and Priya (in person). Portfolio rebalanced; "
                "discussed education planning for Maya and travel budget for next year. "
                "All actions closed.", 98, "14:30")
    # Thin "before" note (~5 months back): the two-line contrast.
    create_note(manifest, hh,
                "Portfolio review w/ Dan + Priya. Discussed RESP.", 150, "19:05")
    # RESP allocation note (~2 years back).
    create_note(manifest, hh,
                "RESP annual check: allocation remains growth-focused (approx. 80/20 "
                "equities). Plan agreed with Dan and Priya: move to a preservation "
                "glide path as Maya approaches university.", 730, "14:30")

    print("4) The forgotten task (~2 years back, still open) ...")
    data = call("Create", {"Task": {"Data": {
        "Key": None,
        "Activity": "Revisit RESP allocation when Maya gets close to university",
        "DateTime": d(-730, "17:00"),
        "AbEntryKey": hh,
        "AssignedTo": MASTER,
    }}, "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "Task", created_key(data, "Task"), "Forgotten RESP task (2 yrs back)")

    print("5) Priya's June cottage call (~9 weeks back) ...")
    phone = phone_type_key()
    if phone:
        data = call("Create", {"InteractionLog": {"Data": {
            "Key": None,
            "Subject": "Call from Priya - thinking about selling the cottage",
            "Description": ("Priya raised possibly selling the cottage in the next year "
                            "or two; wants to discuss timing and what to do with proceeds "
                            "at an upcoming review. No decision yet."),
            "Type": phone,
            "StartDate": d(-63, "11:10"),
            "EndDate": d(-63, "11:22"),
            "User": MASTER,
            "AbEntryKey": hh,
            "Direction": 1,
        }}, "Compatibility": {"AbEntryKey": "2.0"}})
        remember(manifest, "InteractionLog", created_key(data, "InteractionLog"),
                 "Priya cottage call (June feel)")
    else:
        print("  - FAILED: phone interaction type not found")

    print("6) Sweeping audit notes ...")
    sweep_audit_notes(hh)

    _save(manifest)
    n = len(manifest.get("records", []))
    print(f"\nDone: {n} records created. Manifest: {MANIFEST}")
    print("\nEyeball in Maximizer (Halloran Family household) before recording:")
    print("  - Dan, Priya, Maya (17) all on the household")
    print("  - spring review note ~14 weeks back; thin two-line note ~5 months back")
    print("  - RESP allocation note dated ~2 years back")
    print("  - OPEN task 'Revisit RESP allocation when Maya gets close to university',")
    print("    dated ~2 years back (deliberately old — the forgotten promise)")
    print("  - incoming call from Priya ~9 weeks back about selling the cottage")
    print("  - no same-day audit notes; no 'Lewis Dyson' visible anywhere")
    print("\nThen dry-run the two IQ Boost questions:")
    print("  1. What should I follow up on from today's meeting with the Hallorans?")
    print("  2. Where do the Hallorans stand on selling the cottage?")
    print(f"\nRemove: python3 engine/seed-webinar-mcgill.py --cleanup")


def _save(manifest: dict) -> None:
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()
