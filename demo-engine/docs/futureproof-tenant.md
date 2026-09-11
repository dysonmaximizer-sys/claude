# Futureproof demo tenant

Env: `futureproof.env` at repo root (gitignored via root `*.env`). Source it in
the SAME command as every run: `set -a; source futureproof.env; set +a`.
Manifests: `manifests/futureproof/`. Stories: `stories/futureproof/`.

Everything below was validated against THIS tenant on 2026-09-09. Do not assume
anything in the root CLAUDE.md applies here without checking, and read the
first section before writing anything at all.

## 1. This tenant is a CLONE of FSE and SHARES RECORD KEYS

CLAUDE.md says "record keys are tenant-specific". **That is false for this
pair.** Futureproof was cloned from FSE after 2026-07-15. 22 Company records
and 20 Individual records carry byte-identical keys in both books. A manifest
built in one resolves cleanly in the other, so a mis-sourced seeder, refresher
or cleanup edits real records and reports success. Nothing 404s.

The books diverge only on the Camerons:

| Record | FSE | Futureproof |
|---|---|---|
| `Cameron` (Calgary) | present | absent |
| `Peter and Mary Cameron Family` (Coalmont) | absent | present |
| `Michael and Jennifer Cameron Family` (Vancouver) | absent | present |
| `James and Margaret Dutton Family` (Princeton) | absent | present |

`engine/tenant_guard.py` fingerprints on those names, not on keys, and fails
closed. Call `assert_tenant("futureproof", call)` before the first write in
every seeder. Verified 2026-09-09 that it refuses to run under `.env`.

## 2. Households are Individual-typed here, NOT Company-typed

This is the single most important difference from FSE and it contradicts
CLAUDE.md's validated create shape.

- CLAUDE.md's `{"Type": "Household", "CompanyName": "<name>"}` produces a
  **Company**-typed record (Sokolov Family and the rest of the engine cast).
- All 23 original Futureproof households are **Individual**-typed with the name
  in `LastName` and `CompanyName` empty.
- The MCP connector the stage demo runs through maps `entryType: "households"`
  to **Individual**. Company-typed households are invisible to it.

So a household created with the CLAUDE.md shape does not appear in the demo's
own query. Create households here as:

```json
{"AbEntry": {"Data": {"Key": null, "Type": "Individual",
  "LastName": "<household name>",
  "Address": {"City": "...", "StateProvince": "..", "Country": "Canada", "ZipCode": "..."}}},
 "Compatibility": {"AbEntryKey": "2.0"}}
```

Validated on create 2026-09-09 (FP001-FP003). Contacts are unchanged from FSE:
`{"Type": "Contact", "ParentKey": <household key>, ...}`.

## 3. Validated fields (all writable, all read back clean on households)

| Field | Path | Notes |
|---|---|---|
| Segmentation | `Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)` | 1=A, 2=B, 3=C, 4=D, 5=Gold. Write plain string, reads back as a list |
| Record Type | `Udf/$NAME(WM_Client Info\Record Type - Mandatory)` | 1=Client, 2=Prospect, 3=Referral Source, 4=Other Professional, 7=Corporate, 8=Leads |
| Next KYC Review | `Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)` | "YYYY-MM-DD" |
| Date Last Contacted | `Udf/$TYPEID(60059)` | writable |
| Days Since Last Contacted | `Udf/$TYPEID(838)` | FORMULA, never write |
| Birthdate | `Udf/$TYPEID(124)` | on contacts |
| Last Estate Planning Review | `Udf/$TYPEID(841)` | in Review Schedule, NOT the Estate Planning folder |
| Days Since Last Estate Planning Review | `Udf/$TYPEID(1002)` | FORMULA, never write |

Estate Planning folder has 26 fields, all writable, including Is your Will
prepared and signed? (952), When was your Will last updated? (953), Have you
named your Executor and an alternate? (970), Name and Address of Executor
(1023), Do you have a named beneficiary for your Registered Accounts? (956).

Insurance review IDs match FSE exactly: Next 550, Last 842, Days Since 1003.

## 4. Gotchas specific to this tenant

- **An unknown field in a Scope returns 0 rows, not an error.** A read asking
  for a field called `Name` on AbEntry returned an empty set while the records
  existed. Never read a 0-row result as "no such record" without checking the
  field names first. The guard treats 0 rows as a broken probe.
- **Addresses:** write nested on create; verify only via an Address-object read
  by `ParentKey`. AbEntry-scope address reads are unreliable (same as FSE).
- **No sales processes configured** (`[]`). Opportunity creates are untested
  here and should be treated as off-limits until probed.
- **Investments (DataHub) IS installed** (`@DataHubAccount` UDO) but is not an
  Octopus schema root and cannot be written through the API. Accounts data goes
  through Diego's JSON import.
- `Vincent Household` was stored with a **double space** until 2026-09-11,
  when it was renamed to a single space. Historic scripts that match it
  exactly may still carry the two-space literal. Normalise whitespace before
  matching household names rather than trusting either spelling.
- **Filtered reads through the MCP connector fail.** Passing `searchQueryJson`
  or `orderByJson` to `abentry_read` returns "An error occurred invoking
  abentry_read" (seen on CompanyName $LIKE, LastName $EQ, a Udf $EQ, and a
  PageKey sort). Unfiltered reads with `top` work. Filter client-side, or use
  the raw Octopus API.
- `Smith Household` (Edmonton) exists **twice**, with different keys and
  different segmentation (2 and 1).
- **Rule 10 applies:** `LDYSON` exists here displaying "Barb Smith" with
  First/Last "Lewis Dyson". Use `MASTER` (`VXNlcglNQVNURVI=`) as owner. `JYIM`
  displays as "David Carter". Non-service users: MASTER, DDENNIS, DJACKSON, JYIM.
- **Bill Graham / Advocis Publishing Inc** exists here with the same key as the
  broken FSE orphan. Assume it rejects UDF writes while returning success.

- **A UDF-only update does NOT generate an audit note here** (validated
  2026-09-09: six Segmentation updates produced zero notes stamped that day).
  CLAUDE.md rule 5 still applies to record/field changes that Maximizer does
  audit, but a segmentation-only sweep is unnecessary. Check before sweeping
  rather than deleting blind.

## 4b. Coverage decay (stage demo, Beat 1)

`engine/fix-futureproof-coverage-decay.py` owns this and is idempotent. It sets
Date Last Contacted relative to the run date on the three target households
(Peter and Mary Cameron 104 days, Hartfield 97, Vincent 91), creates one
back-dated phone call each on first run only (guarded by
`manifests/futureproof/coverage-decay.json`), sweeps audit notes from the last
10 minutes, and verifies that no other household sits at 90+ days.

Re-run it after every rehearsal, because a rehearsal that logs activity will
reset Date Last Contacted and collapse the answer:

    set -a; source futureproof.env; set +a
    python3 engine/fix-futureproof-coverage-decay.py --apply

Validated 2026-09-11: writes land, 838 recomputes immediately (104/97/91), the
next highest household is 80 days, and `User` on InteractionLog accepts the
MASTER key directly.

## 5. Open

- The raw Octopus API returns **0 Individuals** for the FSE tenant under `.env`
  while the FSE MCP connector returns 21. Cause unknown (PAT scope?). It made
  the guard trip on its sanity check rather than its fingerprint, so the
  fingerprint branch is not yet proven against a live wrong tenant.
- Write access confirmed 2026-09-09 (Jin's open question 1 is answered: the PAT
  can create and update).

- **FullName is a display composite, LastName is the match field.** Validated
  2026-09-09 while selecting Part 2 targets: `Thomas, Jameson - Thomas Household`
  is what the UI and the MCP connector show, but the record is FirstName
  "Jameson", LastName "Thomas", CompanyName "Thomas Household". An `$EQ` on the
  displayed string matches nothing. Always resolve a target by reading LastName
  first; never copy a name out of the MCP connector's output into a filter.
