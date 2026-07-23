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
9. No absolutist claims in value props: no every, all, never, zero. Claims must be plausible to a skeptical buyer. Punchy school.
10. **Lewis's name must not appear in demo data** (rule added on his
   feedback, 2026-07-22). Owner-type fields left to default fall back to
   the PAT user LDYSON, whose First/Last name is Lewis Dyson — and some
   surfaces render First+Last, not the display name. So every seeder
   sets these EXPLICITLY on create: Opportunity `Leader`, Task
   `AssignedTo`, InteractionLog `User`. Correct owner = the persona of
   the door: **Adam the Advisor** (wealth/FA stories) or **Ingrid the
   Insurance Advisor** (insurance stories) — per the Notion persona
   pages (Personas and ICPs). Until Adam/Ingrid user accounts exist in
   the tenant, use **MASTER** (`VXNlcglNQVNURVI=`, displays "Barb
   Smith"). Note creators and record Creator stamps cannot be reassigned
   — mitigate via the LDYSON account rename (Lewis's call) and audit
   sweeps. Appointments stay owned by whichever login records the demo
   (they must appear on that calendar).

## Auth & environments

TWO demo tenants, one env file each at the REPO ROOT (both gitignored,
both hold MAXIMIZER_PAT + optional MAXIMIZER_BASE_URL). Never ask Lewis
to paste a token into chat; never commit one.

- **FSE tenant** (default): `.env` — `set -a; source .env; set +a`.
  Everything under "Validated tenant knowledge" below is THIS tenant.
- **Business+ tenant**: `bizplus.env` — `set -a; source bizplus.env;
  set +a`. Its knowledge lives in `docs/bizplus-tenant.md`, NOT here —
  do not assume any FSE field ID, pick-list value, user, or module
  exists there. First contact is always the read-only probe
  (`engine/probe-bizplus-tenant.py`).

Cross-tenant safety: record keys are tenant-specific. Business+ work
uses `manifests/bizplus/` and `stories/bizplus/`; never point an FSE
seeder, refresher, or cleanup at the Business+ env (or vice versa) —
whichever env file was sourced last decides where writes land, so
source the right one in the SAME command as the run.

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
- **Addresses (validated 2026-07-16):** AbEntry address fields are a
  sub-object. READS of `Address/City` etc. through AbEntry Scope are
  UNRELIABLE (return null even when set) — the only trustworthy read is
  the Address object itself: Read `{"Address": {..., "Criteria":
  {"SearchQuery": {"ParentKey": {"$EQ": <abentry key>}}}}}`. Entries can
  hold several address variants (Description "*Main Address" Default=true
  plus household copies); the UI shows the default. WRITES work via
  AbEntry Update with nested `"Address": {"Key": <address key>, ...fields}`
  (Code 0 means stored even though an immediate AbEntry-scope read may
  show null — verify via the Address-object read).
- **Segmentation** = enum UDF `Udf/$TAG(WME_CLIENTINFO_SEGMENTATION)`,
  values 1=A Client, 2=B, 3=C, 4=D, 5=Gold. Write the key as a plain
  string ("2"); reads return a list (["2"]).
- **Next KYC Review** = date UDF `Udf/$TAG(WME_CLIENTINFO_REV_NEXTKYC)`,
  accepts "YYYY-MM-DD".
- **Type queries:** searching Type=Household returns ALL entries (the
  tenant's ~82 dedupe to Individual/Contact/Company); households are
  Company-typed internally (Sokolov Family). Count by deduped keys, never
  by summing type queries.
- **Insurance/coverage surface on AbEntry (validated 2026-07-22):**
  **Life Insurance** = enum `Udf/$NAME(WM_Client Info\Additional
  Info\Life Insurance)` (2=Yes, 1=No). **RESP balance** = currency
  `Udf/$NAME(WM_KYC etc.\Balance Sheet\Liquid\RESP)`. **Named
  beneficiary for life policies** = enum (Estate Planning folder, 2=Yes).
  **Evaluate/initiate insurance plan** = enum 1-5 (Financial Planning
  objectives). There is NO critical-illness or disability UDF — a CI/DI
  "gap" is shown by absence plus recorded history (notes). Policy rows
  (amounts, terms, conversion windows) remain the API-invisible Accounts
  module: manual UI entry only.
- **Person-level vs household UDFs:** Next/Last Insurance Needs Review
  ($TYPEID(550)/$TYPEID(842)) write Code 0 on a household but store
  NOTHING; they only persist on Individuals/Contacts (validated
  2026-07-22). Segmentation, RESP balance, Date Last Contacted DO store
  on households. When a household UDF write matters, always read back.
- **Household create requires `CompanyName`** — `LastName` shapes fail
  with "mandatory field" (ErrorCode -10010); the CLAUDE.md shape is the
  only validated one.
- **Rate limit:** the API returns 429 on fast loops. Pace bulk runs at
  ~0.35s per call and honor Retry-After (see call() in
  seed-busy-calendar.py). Budget ~1 min per 100 calls.
- **Partial reads lie.** Address/City, Address/Default, and other
  sub-object fields can return null/false on one read and the real value
  on the next depending on the Scope requested. NEVER conclude data is
  missing from a single AbEntry-scope read; confirm via the sub-object
  read (Address by ParentKey) before writing "fixes".
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
- **Document create: shape unknown (probed 2026-07-17).** DocumentObject
  rejects properties `AbEntryKey`, `DocData` (ErrorCode -1023,
  "doesn't support property"); `ParentKey`+`DocData` also rejected.
  Three shapes tried in seed-sail-through-audits.py's probe_documents().
  Next step if documents become story-critical: Schema read $TREE
  /Document to discover assignable properties before trying again.
  Until then, story trails carry "documents" via notes.

- **FA Intelligence renewal tiles (probed 2026-07-21):** NO Account /
  Policy / Holding / Asset / Investment / InsurancePolicy /
  FinancialAccount schema roots exist — the "Accounts - Upcoming
  Renewals" tiles read AbEntry UDFs where they read anything writable.
  Writable: **GIC Expiry Date** = `Udf/$TYPEID(575)` ("WM_Client
  Info\GIC Expiry Date", date). **Group Benefits renewal** =
  `Udf/$TYPEID(1082)` ("WME_Group Benefits - Companies\If yes, when is
  their renewal date?", date, lives on Company entries). **Next / Last
  Insurance Needs Review** = `Udf/$TYPEID(550)` / `Udf/$TYPEID(842)`
  (dates, assignable). Formula, never write: Insurance Age $TYPEID(837),
  Days Since Last Insurance Review $TYPEID(1003). Managed Segregated
  Funds / Managed Mortgages / Annuities: no matching AbEntry UDFs —
  likely the FSE Accounts module with no exposed API surface. CLOSED
  2026-07-21: full schema enumeration (84 roots) has no Accounts-style
  object, and /Custom, /CustomChild, /UdoDefinition are empty shells
  (0 rows). The Accounts module is API-invisible, period. Feeding the
  renewal tiles = manual UI entry only (see
  docs/fa-intelligence-manual-accounts.md). Do not probe this again.
  The report's "This Fiscal Year" filter: fiscal year = CALENDAR year
  (inferred 2026-07-21 from KYC chart bucketing ending in December).
  Keep seeded renewal/review dates inside the current calendar year or
  the tiles drop them.
- **Bill Graham is a broken record (2026-07-21):** AbEntry Update on him
  returns Code 0 but UDF values read back null (confirmed twice, two
  runs). He was already a suspected May-2026 wizard-test orphan (see
  handoff). Never target him for stories or report seeding; candidate
  for deletion after Lewis verifies nothing real hangs off him.
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
- **PAT user is LDYSON: DisplayName "Barb Smith", but FirstName/LastName
  are Lewis Dyson** — which is why his real name leaks on surfaces that
  render First+Last (validated 2026-07-22, user-list read). Tenant users
  (enabled): MASTER "Barb Smith" (the clean demo identity), DDENNIS
  "David Dennis", DJACKSON "Deb Jackson", JYIM "David Carter", plus
  service accounts. NO Adam or Ingrid users yet (see rule 10). User list
  read: `{"User": {..., "Criteria": {"SearchQuery": {"LastName":
  {"$LIKE": "%"}}}}}` — Key $NE null and Disabled filters are rejected.

## Workflow for "set up story X"

1. Read the story spec in `stories/` (or write one from Lewis's tour script).
2. Check no manifest exists for it.
3. Run/adapt the seeder; report in plain language.
4. Tell Lewis exactly what to eyeball in the Maximizer UI before recording.
5. After recording: offer cleanup, or note permanent additions in `cast/`.
