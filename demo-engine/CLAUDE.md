# Maximizer Demo Engine

This folder generates and maintains demo data for Maximizer's demo tenant via
the Octopus API. Lewis is a PMM, not a developer: explain in plain language,
report results, don't make him read code.

## Hard rules

1. **Demo tenant only.** If anything suggests production (real customer
   names, unexpected volumes), STOP and say so.
2. **API-first.** All creation/updates via Octopus API by key. Never use the
   CSV import wizard for opportunities, notes, activities, or interactions —
   validated July 2026: the wizard creates orphan Individual records and
   fails on re-import. CSV import is acceptable only for bulk refreshes of
   the persistent cast, match-on-IDentification.
3. **Manifest discipline.** Every created key goes in `manifests/`. Never
   seed a story whose manifest exists. Cleanup deletes in reverse order.
4. **Never invent keys or IDentification values.**
5. **Sweep audit notes.** Maximizer auto-logs field changes as notes stamped
   "now". After update runs, delete the audit notes the run generated
   (search Notes by creator + time window) or the tenant fills with
   same-day "changed from X to Y" entries.
6. **Fictional data only.** @mail.test / @demo.test emails, 555 phones,
   Canadian realism (two-letter provinces, A1A 1A1 postal codes, milestone
   ages 65/71/18).
7. **Dates are relative, never hardcoded.** Stories are seeded the morning
   of a recording and must be true that day.
8. **Python 3.9 on Lewis's Mac:** `Optional[str]`, never `str | None`.

## Auth

PAT in `.env` at the REPO ROOT (gitignored) as MAXIMIZER_PAT. Load with
`set -a; source .env; set +a`. Optional MAXIMIZER_BASE_URL (default
https://api.maximizer.com/octopus). Never ask Lewis to paste the token into
chat; never commit it.

## Layout

- `engine/` — seeders and validation scripts
- `stories/` — one spec per story slot (aha moments, not screen detail)
- `manifests/` — created-record keys per seeded story (gitignored)
- `cast/` — persistent cast registry (real Maximizer IDs; source of truth)
- `docs/` — validation findings and API notes

## Validated tenant knowledge (tested July 2026)

Works:
- Opportunity CRUD by key. Tenant-mandatory: AbEntryKey, Leader, SalesTeam
  (Leader/SalesTeam default to PAT user). Sales processes: "Default
  Accounts Process", "Group Benefits", "Individual Insurance".
- Note create with back-dated DateTime (stored AND displayed).
- Appointment create with back-dated StartDate (verified on calendar).
- InteractionLog create for PHONE CALLS (type 60001), back-dated, with
  Direction and Duration.
- Household create: `{"Type": "Household", "CompanyName": "<name>"}`.
- Contact create with ParentKey linking to household.
- Opportunity on a Contact: household in AbEntryKey, contact in ContactKey —
  search both when counting.

- **Birthdate** = UDF `Udf/$TYPEID(124)` ("WM_KYC etc.\Personal\Birthdate"),
  validated on update. $NAME notation requires the FULL folder path
  (`Udf/$NAME(WM_KYC etc.\Personal\Birthdate)`), not the bare field name.
  DOB Month / 65th / 71st Birthday Date are formula UDFs (Assignable=False)
  — never write them. Discover any UDF via Schema read: $TREE /AbEntry.
- **Task create shape:** `Activity` + `DateTime` + `AbEntryKey`.
  Subject, DueDate, and Description are NOT Task properties.
  Other assignable Task fields: AssignedTo, Priority, Completed, Alarm.
  Full validated payload (this is the single source of truth — do not
  re-specify it elsewhere):
  `{"Task": {"Data": {"Key": null, "Activity": "<text>", "DateTime":
  "<ISO datetime>", "AbEntryKey": "<key>"}}, "Compatibility":
  {"AbEntryKey": "2.0"}}` posted to /Create.

Blocked:
- **Emails cannot be fabricated.** InteractionLog rejects types 60002
  (email), 60003 (appointment), 60004 (task) on create/update. Email
  history only enters via real Outlook capture. Design stories around
  calls + notes, or send real emails between demo mailboxes.

Open:
- **"Last contacted" date:** assumed derived from interactions; verify.

## Workflow for "set up story X"

1. Read the story spec in `stories/` (or write one from Lewis's tour script).
2. Check no manifest exists for it.
3. Run/adapt the seeder; report in plain language.
4. Tell Lewis exactly what to eyeball in the Maximizer UI before recording.
5. After recording: offer cleanup, or note permanent additions in `cast/`.
