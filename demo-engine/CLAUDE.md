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
7b. **Times are Pacific, converted to UTC before sending.** The API stores
   naive datetimes as UTC and the tenant displays Pacific; unconverted
   times show hours early (validated 2026-07-15: a 10:00 call displayed as
   3am). Always convert via zoneinfo America/Vancouver -> UTC (see `d()`
   in the seeder) — never hardcode an offset: B.C. adopted PERMANENT
   daylight time in 2026 (UTC-7 year-round from Nov 1, 2026; no more
   fall-back), and zoneinfo already knows this.
   WATCH ITEM (first week of Nov 2026): if Maximizer's tenant timezone
   follows US Pacific (which still falls back), all displayed times will
   drift 1h early after Nov 1. Check one appointment time in the UI then.
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
- `cast/` — persistent cast registry: `cast.json`, 77 records with real
  Maximizer IDs and date RULES (canonical since 2026-07; the
  maximizer-demo-data-generator skill bundles a fallback copy — when the
  cast changes, update BOTH and re-upload the skill). Its meta lists
  engine_protected_records the CSV refresh must never touch.
- `docs/` — validation findings and API notes
- `skills/` — source of truth for the two claude.ai skills:
  `maximizer-demo-engine` (stories, API seeding — this repo's front end)
  and `maximizer-demo-data-generator` (bulk cast-refresh CSV only).
  Edit here, commit, then re-upload to claude.ai so they stay in lockstep.

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

- **Date Last Contacted** = assignable UDF `Udf/$TYPEID(60059)` — set it
  directly with a date string ("2026-06-10"). It does NOT populate from
  back-dated interactions (validated 2026-07-15: Marina's stayed blank
  despite her June call), but same-day actions CAN auto-set it (the
  household picked up the seed date, likely from appointment/task
  creation). The refresh script rolls it wherever set. "Days Since Last
  Contacted" ($TYPEID(838)) is a formula off it — never write.
- **Note queries:** link field is `ParentKey` (NOT AbEntryKey); Note has no
  CreationDate property and DateTime rejects $GT — read all notes for the
  parent and filter client-side.
- **Audit notes observed** (auto-logged on the parent entry, stamped now):
  "Hotlist Task Created/Modified: ...", "Opportunity created for: ...".
  Sweep these after every seed/update run (rule 5).
- **PAT user is LDYSON, display name "Barb Smith"** — audit notes say
  "Barb Smith" but keys decode to User\LDYSON; same account.

## Workflow for "set up story X"

1. Read the story spec in `stories/` (or write one from Lewis's tour script).
2. Check no manifest exists for it.
3. Run/adapt the seeder; report in plain language.
4. Tell Lewis exactly what to eyeball in the Maximizer UI before recording.
5. After recording: offer cleanup, or note permanent additions in `cast/`.
