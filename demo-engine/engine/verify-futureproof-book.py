#!/usr/bin/env python3
"""Read back what seed-futureproof-book.py created. READ-ONLY."""
import json, os, sys, time
import requests

BASE = os.environ.get("MAXIMIZER_BASE_URL", "https://api.maximizer.com/octopus").rstrip("/")
PAT = os.environ.get("MAXIMIZER_PAT")
COMPAT = {"AbEntryKey": "2.0"}
SEG = "Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)"
KYC = "Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)"
RT  = r"Udf/$NAME(WM_Client Info\Record Type - Mandatory)"
DLC = "Udf/$TYPEID(60059)"
BD  = "Udf/$TYPEID(124)"
SEGLABEL = {"1": "A Client", "2": "B Client", "3": "C Client", "4": "D Client", "5": "Gold Client"}


def call(endpoint, payload):
    for attempt in range(6):
        r = requests.post("%s/%s" % (BASE, endpoint),
                          headers={"Authorization": "Bearer %s" % PAT,
                                   "Content-Type": "application/json"},
                          json=payload, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 0)) or 10 * (attempt + 1)); continue
        r.raise_for_status(); time.sleep(0.35); return r.json()
    raise RuntimeError("rate limited")


def one(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v


m = json.load(open("manifests/futureproof/build-the-book.json"))
for ref, rec in sorted(m["created"].items()):
    hh = rec["household"]
    res = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "Type": 1, "LastName": 1,
                                                         SEG: 1, KYC: 1, RT: 1, DLC: 1}},
                                    "Criteria": {"SearchQuery": {"Key": {"$EQ": hh}}}},
               "Compatibility": COMPAT})
    d = (res.get("AbEntry", {}).get("Data") or [{}])[0]
    seg = one(d.get(SEG))
    print("%s  %s   [Type=%s]" % (ref, d.get("LastName"), d.get("Type")))
    print("   segmentation        : %s (%s)" % (seg, SEGLABEL.get(str(seg), "?")))
    print("   record type         : %s" % one(d.get(RT)))
    print("   next KYC review     : %s" % one(d.get(KYC)))
    print("   date last contacted : %s" % one(d.get(DLC)))

    ares = call("Read", {"Address": {"Scope": {"Fields": {"Key": 1, "City": 1, "StateProvince": 1,
                                                          "ZipCode": 1, "Country": 1, "Default": 1}},
                                     "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": hh}}}},
                "Compatibility": COMPAT})
    addrs = ares.get("Address", {}).get("Data") or []
    if not addrs:
        print("   address             : !! NONE returned by Address-object read")
    for a in addrs:
        print("   address             : %s, %s  %s  (%s, default=%s)" % (
            a.get("City"), a.get("StateProvince"), a.get("ZipCode"),
            a.get("Country"), a.get("Default")))

    cres = call("Read", {"AbEntry": {"Scope": {"Fields": {"Key": 1, "FirstName": 1, "LastName": 1, BD: 1}},
                                     "Criteria": {"SearchQuery": {"ParentKey": {"$EQ": hh}}},
                                     "Options": {"Limit": 20}}, "Compatibility": COMPAT})
    for c in cres.get("AbEntry", {}).get("Data") or []:
        print("   contact             : %s %s  b.%s" % (
            c.get("FirstName"), c.get("LastName"), one(c.get(BD))))
    print("")
