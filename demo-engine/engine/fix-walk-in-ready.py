#!/usr/bin/env python3
"""
Patch for the seeded Walk In Ready story — fixes the three failures from the
first run (July 15, 2026):

  A. Birthdates were rejected as Udf/$NAME(Birthdate).
     -> Reads the AbEntry schema, finds every birth-related field, tries each
        shape on Marina until one sticks, then applies the winner to Viktor
        and Daria too. Prints the winning field path for CLAUDE.md.

  B. Email interactions are blocked by the tenant (type 60002 not allowed).
     -> Replaces the June "open RESP question" email with what IS allowed:
        an incoming phone call (type 60001) + a note documenting the open
        question, both dated mid-June.

  C. Task creation failed ("Subject" unsupported; "Activity" unreported).
     -> Reads the Task schema, prints the real field names, and tries
        sensible shapes loudly so the error tells us the answer.

Reads the manifest the seeder wrote (Desktop) to find the record keys, and
appends anything it creates to the same manifest so --cleanup still removes
the whole story.

Run:  set -a; source .env; set +a   (or export MAXIMIZER_PAT=...)
      python3 fix-walk-in-ready.py
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("pip3 install requests --break-system-packages")

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifests", "walk-in-ready-manifest.json")

TODAY = datetime.now()


def pac(day: datetime, hm: str) -> str:
    """Intended Pacific wall-clock time -> UTC string for the API.
    The API stores naive datetimes as UTC; the tenant displays Pacific
    (validated 2026-07-15: unconverted times displayed 7h early)."""
    from zoneinfo import ZoneInfo
    hour, minute = int(hm[:2]), int(hm[3:5])
    local = day.replace(hour=hour, minute=minute, second=0, microsecond=0,
                        tzinfo=ZoneInfo("America/Vancouver"))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S")


def call(endpoint: str, payload: dict, quiet: bool = False) -> dict:
    r = requests.post(
        f"{BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("Code", 0) != 0 and not quiet:
        print(f"  !! Code={data.get('Code')}: {json.dumps(data)[:500]}")
    return data


def load_manifest() -> dict:
    if not os.path.exists(MANIFEST):
        sys.exit(f"Manifest not found at {MANIFEST} - was the story seeded on this machine?")
    with open(MANIFEST) as f:
        return json.load(f)


def key_for(manifest: dict, label_contains: str) -> Optional[str]:
    for rec in manifest.get("records", []):
        if label_contains.lower() in rec["label"].lower():
            return rec["key"]
    return None


def remember(manifest: dict, kind: str, key: Optional[str], label: str) -> None:
    if key:
        manifest["records"].append({"kind": kind, "key": key, "label": label})
        print(f"  + {kind}: {label}")


def save(manifest: dict) -> None:
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)


# ---------------------------------------------------------------- A. birthdates

def find_birth_fields() -> list:
    data = call("Read", {
        "Schema": {
            "Scope": {"Fields": {"Key": 1, "Alias": 1, "Name": 1, "Type": 1, "Assignable": 1}},
            "Criteria": {"SearchQuery": {"Key": {"$TREE": "/AbEntry"}}},
        },
        "Compatibility": {"SchemaObject": "1.0"},
    }, quiet=True)
    fields = data.get("Schema", {}).get("Data", [])
    hits = [f for f in fields if "birth" in json.dumps(f).lower()]
    print(f"  schema returned {len(fields)} AbEntry fields, {len(hits)} birth-related:")
    for h in hits:
        print(f"    Key={h.get('Key')} | Alias={h.get('Alias')} | Name={h.get('Name')} | Assignable={h.get('Assignable')}")
    return hits


def candidate_paths(hits: list) -> list:
    out = []
    for h in hits:
        for c in (h.get("Alias"), h.get("Key"), h.get("Name")):
            if c and c not in out:
                # schema keys come back like /AbEntry/SomeField - strip the prefix
                out.append(str(c).replace("/AbEntry/", "").lstrip("/"))
    return out


def set_birthdate(contact_key: str, iso_date: str, paths: list) -> Optional[str]:
    for path in paths:
        data = call("Update", {
            "AbEntry": {"Data": {"Key": contact_key, path: iso_date}},
            "Compatibility": {"AbEntryKey": "2.0"},
        }, quiet=True)
        if data.get("Code", 0) == 0:
            return path
    return None


# ---------------------------------------------------------------- main

def main() -> None:
    if not PAT:
        sys.exit("Set MAXIMIZER_PAT first (demo tenant only).")
    manifest = load_manifest()

    hh = key_for(manifest, "Household")
    viktor = key_for(manifest, "Viktor")
    marina = key_for(manifest, "Marina")
    daria = key_for(manifest, "Daria")
    if not all([hh, viktor, marina, daria]):
        sys.exit("Couldn't find all Sokolov keys in the manifest.")

    print("A) Birthdates - discovering the real field ...")
    hits = find_birth_fields()
    paths = candidate_paths(hits)
    if not paths:
        print("  no birth-related field in schema - birthdate may be UI-only. Set manually; tell Claude.")
    else:
        marina_bday = (TODAY + timedelta(days=6)).replace(year=TODAY.year - 61).strftime("%Y-%m-%d")
        winner = set_birthdate(marina, marina_bday, paths)
        if winner:
            print(f"  WINNER: '{winner}' - record this in demo-engine/CLAUDE.md")
            set_birthdate(viktor, (TODAY - timedelta(days=64 * 365 + 120)).strftime("%Y-%m-%d"), [winner])
            set_birthdate(daria, (TODAY - timedelta(days=17 * 365 + 200)).strftime("%Y-%m-%d"), [winner])
            print("  Viktor and Daria set with the same field.")
        else:
            print("  none of the candidate paths accepted an update. Set birthdates manually in the UI;")
            print("  paste this output to Claude so the schema hits above can be interpreted.")

    print("B) June open RESP question - as phone call + note (emails can't be fabricated) ...")
    june_ago = max((TODAY - TODAY.replace(month=6, day=10)).days, 20) if TODAY.month >= 6 else 30
    when = (TODAY - timedelta(days=june_ago))
    data = call("Create", {"InteractionLog": {"Data": {
        "Key": None,
        "Subject": "Call from Marina - RESP maturity question (open)",
        "Description": "Marina called asking whether to convert Daria's RESP to instalments for "
                       "first-year tuition or take the lump sum. Not yet answered - open item for the review.",
        "Type": "60001",
        "StartDate": pac(when, "11:15"),
        "EndDate": pac(when, "11:27"),
        "User": "$CURRENTUSER()",
        "AbEntryKey": hh,
        "Direction": 1,
    }}, "Compatibility": {"AbEntryKey": "2.0"}})
    remember(manifest, "InteractionLog", data.get("InteractionLog", {}).get("Data", {}).get("Key"),
             "June call - open RESP question")
    data = call("Create", {"Note": {"Data": {
        "Key": None, "ParentKey": hh,
        "DateTime": pac(when, "11:30"),
        "Text": "OPEN ITEM: Marina asked (call) - RESP maturity: instalments vs lump sum for Daria's "
                "first year. Promised options at the annual review.",
    }}})
    remember(manifest, "Note", data.get("Note", {}).get("Data", {}).get("Key"), "June open-item note")

    print("C) Task - discovering the real field names ...")
    data = call("Read", {
        "Schema": {
            "Scope": {"Fields": {"Key": 1, "Alias": 1, "Name": 1, "Mandatory": 1, "Assignable": 1}},
            "Criteria": {"SearchQuery": {"Key": {"$TREE": "/Task"}}},
        },
        "Compatibility": {"SchemaObject": "1.0"},
    }, quiet=True)
    tfields = data.get("Schema", {}).get("Data", [])
    print(f"  Task schema fields ({len(tfields)}):")
    for f in tfields[:25]:
        print(f"    Key={f.get('Key')} | Alias={f.get('Alias')} | Mandatory={f.get('Mandatory')} | Assignable={f.get('Assignable')}")
    # best-guess attempts, loud so failures teach us:
    due = (TODAY + timedelta(days=7)).strftime("%Y-%m-%dT17:00:00")
    for shape in (
        {"Key": None, "Activity": "Answer Marina's RESP question (instalments vs lump sum)",
         "DueDate": due, "AbEntryKey": hh},
        {"Key": None, "Description": "Answer Marina's RESP question (instalments vs lump sum)",
         "DueDate": due, "AbEntryKey": hh},
    ):
        data = call("Create", {"Task": {"Data": shape}, "Compatibility": {"AbEntryKey": "2.0"}})
        key = data.get("Task", {}).get("Data", {}).get("Key")
        if key:
            print(f"  WINNER shape: {[k for k in shape if k != 'Key']} - record in CLAUDE.md")
            remember(manifest, "Task", key, "RESP follow-up task")
            break

    save(manifest)
    print(f"\nManifest updated: {MANIFEST}")
    print("Re-check the Sokolov household in Maximizer, then paste this output to Claude")
    print("so the discovered field names get recorded in the engine's knowledge base.")


if __name__ == "__main__":
    main()
