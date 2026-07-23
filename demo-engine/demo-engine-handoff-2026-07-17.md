# Maximizer Demo Engine — Handoff
Updated: 2026-07-22 · Session: Claude Code

## 2026-07-23 session (Sales Intelligence backfill + re-check)
- RE-CHECK of Lewis's admin fixes: STILL incomplete (FSE + Business+
  LDYSON First/Last remain Lewis Dyson; Business+ opportunity delete
  still denied). Fix steps re-issued; verify again on his word.
- Sales Intelligence dashboard populated (Business+): root cause of
  empty tiles = deals defaulting to *Single User team. 36 historical
  deals seeded (2025 full year ~$560K won; 2026 YTD 14 won $617K
  actual, growth story, Amanda tops leaderboard; 8 lost for win-rate).
  12 live pipeline deals dressed (real teams, RevenueType, Product,
  Category, StartDate; priors in manifest). All rule-10 owners.
- Dashboard knowledge in docs/bizplus-tenant.md incl. the Process
  filter caveat (no process catalog in tenant).

## 2026-07-22 session, part 7 (verification of Lewis's admin changes)
- VERIFIED, all three incomplete: (1) FSE LDYSON rename did not take
  (First/Last still Lewis Dyson); (2) Business+ LDYSON display is now
  "Sam Suzuki" but First/Last still Lewis Dyson - the leaking fields;
  (3) Business+ Opportunity-delete still Access Denied for the PAT
  user (grant likely applied to the wrong user/checkbox). Fix steps
  given to Lewis; re-verify on his word. Delete-test stray neutralized
  ("Archived - duplicate entry", Status 5, backdated).

## 2026-07-22 session, part 6 (zombie pipeline cleanup, Lewis-approved)
- All 61 open 2023-dated sample opportunities in the Business+ tenant
  marked Status 5 Abandoned (deletes blocked; update was the tool).
  Prior states captured in
  manifests/bizplus/pipeline-hygiene-2026-07-22.json - reversible by
  updating each key back to prior_status. Verified after: EXACTLY the
  12 Monday-Pipeline-Review deals remain open. No capture-time filter
  needed anymore.

## 2026-07-22 session, part 5 (Business+ first story: Monday Pipeline Review)
- Seeded on the Business+ tenant: 12 open opportunities across 5 owners
  (Michelle Boone = VP persona per Lewis; Amanda/Douglas/Jane/David as
  reps), 8 calls, 5 notes, 5 team tasks. Review moments: hot deal
  closing Friday (Walley World 85K), slipped close date (Cyberdyne 60K),
  3 stale deals quiet 4-6 weeks. Manifest:
  manifests/bizplus/monday-pipeline-review-manifest.json.
- TENANT LIMITS discovered (docs/bizplus-tenant.md): Opportunity DELETE
  Access-Denied for the PAT (creates permanent; stray probe repurposed
  into the Alpha Beta deal); stages are per-deal instances (assign in
  UI); email create blocked like FSE; no auto audit notes observed.
- Lewis actions for this tenant: grant Opportunity-delete to the API
  user; rename LDYSON (displays "Lewis Dyson" here); decide on the
  zombie-pipeline hygiene pass (61 open 2022-2023 sample deals).

## 2026-07-22 session, part 4 (Business+ tenant scaffolding)
- Second demo environment added: Business+ edition tenant. `bizplus.env`
  at repo root (gitignored, placeholder awaiting Lewis's PAT);
  `manifests/bizplus/` + `stories/bizplus/`; CLAUDE.md Auth section now
  covers both tenants and the cross-tenant safety rule.
- `engine/probe-bizplus-tenant.py`: read-only recon (users incl. rule-10
  name check, book size with rule-1 volume guard, schema roots, UDF
  folders, sales processes, interaction types). RUN THIS FIRST; findings
  go to docs/bizplus-tenant.md. No Business+ stories exist yet - design
  them after recon (different edition, likely no wealth UDFs; audience
  is probably VP Sales, not advisors).

## 2026-07-22 session, part 3 (Sail Through Audits — insurance door)
- **Story seeded: sail-through-audits-insurance** (distinct slug; the
  FA-door Renaud/CIRO story of the same tour name is untouched). Per
  Lewis: the CHEN family — Michael (52, logistics owner) + Grace (50),
  Guelph ON. 27 records: 8 years of review appointments + suitability
  notes (needs analyses signed, CI 2020, key-person 2021, seg fund 2022,
  documented DI DECLINE 2023 — compliance-gold), 7 calls (latest: MGA
  review notice, 3 days ago), task "Compile compliance file" due +5d.
  Owners = MASTER per rule 10. No CIRO anywhere in this data. Verified
  by read-backs; 1 audit note swept.
- Manual before capture: policy rows + 4 document uploads
  (docs/audits-insurance-manual-entries.md; Claude can generate the
  fake PDFs on request) + the reviewer's email composed natively in the
  demo mailbox.

## 2026-07-22 session, part 2 (Lewis feedback: no Lewis in demo data)
- **NEW HARD RULE 10 in CLAUDE.md:** owner-type fields (Opportunity
  Leader, Task AssignedTo, InteractionLog User) are set explicitly in
  every seeder — persona users per door (Adam = wealth, Ingrid =
  insurance, per Notion Personas and ICPs), MASTER "Barb Smith" until
  those user accounts exist. Root cause: PAT user LDYSON has
  First/Last = Lewis Dyson; defaults leak his name on First+Last
  surfaces.
- **All existing story records reassigned to Barb Smith** (25 fields
  across walk-in-ready, find-the-coverage-gaps, sail-through-audits,
  see-your-whole-book), verified by read-back; reassignment audit notes
  swept (3).
- **Seeder retrofit:** coverage-gaps seeder now sets OWNER_USER
  (env-overridable). REMAINING RETROFIT: walk-in-ready,
  sail-through-audits, see-your-whole-book, busy-calendar seeders still
  default owners — fix before any re-seed.
- **Lewis's two account-level actions (Claude cannot create accounts):**
  1. Create demo users for the personas in Administrator: "Adam" +
     surname of his choice (wealth door), "Ingrid" + surname (insurance
     door). Then tell Claude to re-own the stories per door.
  2. Decide the recording login: appointments/calendar and record
     Creator stamps follow the logged-in user. If he records as LDYSON,
     consider renaming that account's First/Last (e.g. to the persona)
     in Administrator so no surface shows "Lewis Dyson".

## 2026-07-22 session (Find the Coverage Gaps — insurance door)
- **Story seeded: Find the Coverage Gaps** (insurance door, gated tour 2).
  Tremblay Family household (Burnaby BC): Marc (42, self-employed, term
  life $500K on record) + Sophie (39, $350K) + Leo (9) + Chloe (6).
  RESP $38K, Segmentation B, Life Insurance = Yes + named beneficiaries
  on both adults, insurance objective 4/5, Last Insurance Needs Review
  -14mo / Next +3wk (on the ADULTS — person-level UDFs no-op on
  households, new CLAUDE.md entry). The gap is RECORDED, not implied:
  last year's review note says CI/DI discussed and deferred; Sophie's
  call 5 weeks ago asks the DI question. Task +10d, opportunity
  "Family protection review - CI and DI" $3,600 close +45d.
  9 records in manifests/find-the-coverage-gaps-manifest.json.
- **5 cast clients dressed as step-3 gap-list rows** (Simon McKinney,
  Bill Diamond, Mary Gratton, Jennifer Poulin, Joey Poulin): Life = Yes,
  reviews due/overdue. PRIOR VALUES captured in the manifest under
  "modified"; cleanup restores them.
- **Manual policy rows required** (Accounts module API-invisible):
  docs/coverage-gaps-manual-policies.md — 7 rows, ~7 min, incl. two
  term-conversion windows closing Oct/Nov 2026. Without them any screen
  showing a policy LIST cannot be staged.
- New CLAUDE.md knowledge: Life Insurance enum + RESP currency +
  beneficiary/objective UDFs; person-level vs household UDF behavior;
  household create REQUIRES CompanyName (LastName shape fails -10010).
- NOTE: walk-in-ready + busy-calendar stories are now ~6 days stale
  (seeded Jul 15/16; busy-calendar week was Jul 13-17). Refresh
  walk-in-ready via refresh-story.py; RESEED busy-calendar (weekday
  drift) before any FA-door capture.
- Committed the stranded 2026-07-21 session files (probes, FA
  Intelligence work, see-your-whole-book) that were sitting uncommitted.

## 2026-07-17 session (Sail Through Audits seed)
- **Story 2 seeded: Sail Through Audits** (Demo Centre gated tour 2).
  Renaud Family household (Ottawa) + Philippe (68) + Céline (65), NINE
  years of history: 9 annual-review appointments + matching advice notes
  (oldest 2017-07), 9 phone calls with direction/duration, profiles set
  (Segmentation A, Next KYC +6mo, Date Last Contacted -9d). Open task
  "Compile CIRO audit file" due +4d. 31 records + 1 patch call, manifest
  `manifests/sail-through-audits-manifest.json`. Spec:
  `stories/sail-through-audits.md`. Audit sweep ran (1 note); read-back
  verified.
- **NEW BLOCKED FINDING (in CLAUDE.md): Document create.** DocumentObject
  rejects AbEntryKey/DocData/ParentKey shapes (ErrorCode -1023). Trails
  carry documents via notes. Next avenue if needed: Schema $TREE /Document.
- **Patch script** `engine/fix-sail-through-audits.py`: adds one incoming
  call 9 days back (Céline OAS question) so Date Last Contacted matches a
  real interaction — APPLIED 2026-07-17 (32 records now in manifest; the
  script refuses to run twice). Fold a years_ago=0 call into the seeder
  before any fresh re-seed.
- **Git note:** repo ROOT is `~/Claude Code`, not `demo-engine/` — never
  `git add -A` from inside demo-engine (it stages the whole parent repo;
  swept in unrelated files once, fixed with reset --soft + restore).
  Scope adds to `demo-engine/`. Check `resources/hubspot_upload.py` for
  hardcoded keys before it is ever committed/pushed.
- **Tour script step 3 softened** (Demo Centre/maximizer-demo-centre-tour-
  drafts.md): "every client conversation" replaces "every client email"
  because email history can't be fabricated; build note added there.
- **.env went missing from repo root** (created 2026-07-15 per this
  handoff, absent 2026-07-17) — Lewis recreated it. If it vanishes again,
  suspect a cleanup tool; consider documenting PAT storage location.
- **Sandbox cannot reach api.maximizer.com** (Cowork network allowlist).
  Engine runs stay on Lewis's Mac via pasted one-liners.
- Pre-capture checklist for this story: Lewis eyeballs Renaud household
  (9-year span, no >18mo gaps, task visible, no audit notes); runs the
  patch script; sends 2-3 real emails between demo mailboxes; composes
  Adam's CIRO forward natively in demo Outlook (asset in Demo Centre;
  never Resend). Voice decision pending: this tour is second-person
  Bridget while Walk In Ready moved to third-person Adam.

## 2026-07-16 session (tour-prep pass)
- **Profiles complete book-wide:** all 82 entries have full default
  addresses (street/city/prov/postal/Canada), every client has
  Segmentation (A/B/C/D/Gold spread; Sokolovs = Gold) and Next KYC Review
  (spread 1-11 months; Sokolovs = 2027-04-15; pre-existing story-slot
  values untouched). Verified via the reliable Address-by-ParentKey read.
- **Bozik orphans deleted** (malformed May-29 wizard-test remnants:
  first-nameless Individual + Galena Bozik Contact) — removed from tenant
  AND from both cast.json copies (75 cast records remain).
- **Busy calendar seeded:** 16 appointments Mon Jul 13 - Tue Jul 21, 7
  linked to cast members (incl. Marina birthday call Jul 21). Own story
  (stories/busy-calendar.md), seeder (engine/seed-busy-calendar.py),
  manifest. Reseed per recording week; don't partial-week refresh.
- **Walk In Ready tour beats now data-true:** 2:45 review today, spring
  history, June RESP call+note+task+opportunity, Marina's birthday Jul 21
  (next week). STILL BLOCKED: "account up since April" (dealer feed).
- New tenant knowledge in CLAUDE.md: address sub-object read/write,
  Segmentation/KYC UDF tags, 429 pacing, partial-read flakiness.
- Open question for Lewis: book is 82 entries; See Your Whole Book needs
  ~300 households (its own tour script says so) — bulk expansion is a
  separate job awaiting his go.

## Context
Internal tool ("Demo Engine") that generates and refreshes demo data in
Maximizer's demo tenant so sales demos, Demo Centre recordings, and
enablement sandboxes never need manual data prep. Owner: Lewis (PMM).
Sponsor context: Meena (Lewis's manager) confirmed automated demo creation
is a recurring need (meeting 2026-07-07). Everything lives in this repo
under `demo-engine/` — read `demo-engine/CLAUDE.md` FIRST; it contains the
hard rules and all validated tenant knowledge. First story (Sokolov
household, "Walk In Ready" Demo Centre hero tour) is seeded in the tenant
and ~95% complete.

## Decisions
- **API-first, by key** — all record creation/updates via Octopus API.
  Rejected: CSV import wizard for opportunities/notes/activities, because
  live testing showed it creates orphan Individual entries and fails on
  re-import ("AbEntry object not found"). CSV remains only for bulk cast
  refreshes matched on IDentification.
- **Interface = this repo + Claude Code** — Lewis requests stories
  conversationally; Claude Code writes/runs seeders. Rejected: terminal
  scripts as the ongoing UX (Lewis is a non-developer).
- **Manifest per story** (`manifests/`, gitignored) so cleanup is exact and
  double-seeding is blocked. Manifest for the seeded story is currently at
  `~/Desktop/walk-in-ready-manifest.json` — moving it into `manifests/` is
  a next step.
- **June "open RESP question" is a phone call + note, not an email** —
  tenant blocks fabricating email interactions (see gotchas).
- **Sokolov household kept in tenant** (not cleaned up) — it's the Phase 1
  dogfood data for the Walk In Ready Storylane capture.
- **Phased rollout agreed with Lewis:** P1 engine core (Lewis only) → P2
  nightly refresh + story library → P3 enablement (Mark) → P4 sales
  self-serve (gated on demand) → P5 recording-analysis loop.

## Open items & blockers
- ~~GitHub push blocked~~ RESOLVED 2026-07-15: Lewis minted a new PAT,
  keychain updated, both commits verified on origin/main.
- Lewis UI-verified 2026-07-15: story looks right. Two issues he found
  (Marina's blank Date Last Contacted; times displaying non-Pacific) were
  BOTH FIXED same day — see CLAUDE.md for the tz rule (7b) and the
  LastContactDate finding. All 6 record times shifted +7h and verified;
  audit notes swept.
- Marina's birthday UDF was set via API — visually confirm it shows in UI.
- "Account up since April" (tour step 4) is dealer-feed data, NOT
  fabricable via CRM API — needs product conversation before Storylane
  capture, or the capture avoids that panel.
- Wizard-test orphan Individuals (fake Jameson Thomas, poss. Lou Cameron /
  Bill Graham) may still need deleting from the tenant — verify.
- `.env` not yet created at repo root; nothing committed yet this session.

## Next steps (in order)
~~1-3 DONE 2026-07-15 (later session):~~ RESP task created & verified
(key VGFzawk0Nzg=, due +7d, in manifest); manifest moved to `manifests/`
and both scripts updated (Desktop copy is a stale spare — delete after
UI check); `.env` created at repo root with PAT, confirmed gitignored.
Commit/push still pending Lewis's go-ahead.
4. Have Lewis eyeball Sokolov household vs `stories/walk-in-ready.md`
   checklist, then record the Storylane capture.
5. ~~Build the refresh script~~ DONE 2026-07-16: `engine/refresh-story.py`
   (generic, manifest-driven, --dry-run and --as-of for testing, Pacific
   day-math via zoneinfo, rolls Date Last Contacted, sweeps audit notes,
   read-back verified). Live-tested: rolled the story +1 day on 2026-07-16.
   Manifest now carries a "refreshed" anchor date. Skills uploaded to
   claude.ai (maximizer-demo-engine new; demo-data-generator corrected);
   sources in `skills/`, keep in lockstep per CLAUDE.md.
6. Draft Meena one-pager from `docs/` + validation results (Lewis will ask).

## Tool knowledge & gotchas
- All Octopus API knowledge is in `demo-engine/CLAUDE.md` — tenant field
  requirements, working payload shapes, blocked operations. Do not re-test
  what's recorded there.
- Birthdate UDF: `Udf/$TYPEID(124)`. Task shape: Activity + DateTime.
  Emails/appointments/tasks CANNOT be created as InteractionLog types.
- Maximizer auto-logs field changes as notes stamped "now" — refresh runs
  must sweep them (rule 5 in CLAUDE.md).
- Sokolov story keys are in `~/Desktop/walk-in-ready-manifest.json` — 10
  records incl. household `Q29tcGFueQkyNjA3MTUyNTIxNDAwMTE5MDAwMDNDCTA=`.
  Household displays correctly as Household despite Company-style key.
- Lewis's Mac runs Python 3.9 (verified: the only interpreter installed):
  `Optional[str]`, never `str | None`. urllib3 LibreSSL warning is noise —
  ignore. (The cpython-310 files in `engine/__pycache__/` came from the
  Cowork sandbox, not this Mac — don't let them mislead you.)
- Repo lives at `~/Claude Code/demo-engine` — NOT `~/Desktop/Claude Code`,
  which is a different folder with no demo-engine in it.
- PAT is demo-tenant only, lives in `.env`, never in chat or commits.

## Session preferences
- Lewis wants step-by-step, zero-knowledge instructions for anything
  terminal- or UI-related, and wants failures pasted back verbatim.
- Report script results in plain language; keep code invisible unless asked.
