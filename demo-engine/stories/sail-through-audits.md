# Story: Sail Through Audits (Demo Centre gated tour 2) — SEEDED 2026-07-17

**Persona:** Bridget the BDA. **Scene:** a CIRO audit request lands; Adam
forwards it with "can you help?" The Renaud household, nine years, normally
her weekend.
**Aha:** the complete, time-stamped trail assembles in a couple of clicks
because everything was captured as it happened. She hands it back clean.

## Tenant constraint that shapes this story (CLAUDE.md, validated)

**Emails cannot be fabricated.** InteractionLog rejects email types on
create. Back-dated history must be built from notes, phone-call
interaction logs, and appointments. Real emails enter only via actual
Outlook capture between demo mailboxes, which means email entries can
only carry near-recording-day dates.

Consequence for the tour's step 3 ("Every client email is already in the
record"): on screen, the nine-year trail will read as calls, meetings, and
advice notes, with real captured emails only in the recent window. Two
honest options, Lewis to pick:
- (a) Soften step 3 to "every client conversation" / "every email you've
  sent since the add-in went in" — trail shows mixed types, all true.
- (b) Keep the email-centric tooltip but frame the capture shot on the
  recent window where real captured emails exist, letting the deep
  history carry the nine-years claim through notes and calls.

## Cast (seeded via API, keys in manifest)

| Who | Role in story |
|---|---|
| Renaud Family (Household) | The audited record |
| Philippe Renaud, 61 | Client since ~9 years back; RRIF conversion looming |
| Céline Renaud, 59 | Co-client; owns the insurance-review thread |

(Seeded 2026-07-17: Philippe 68, Céline 65 — her OAS/65th-birthday thread
is live story material. 31 records in the manifest + 1 patch call.)

## What must be true in the data on recording day

1. Household + both contacts exist, profile complete (segmentation A,
   Next KYC Review current, Date Last Contacted recent, addresses set).
2. **Nine years of ordered history** (~30 entries, relative dates):
   annual review appointment + advice note each year, phone calls
   scattered between (InteractionLog, direction + duration), KYC review
   notes at realistic intervals. Oldest entry ≈ 108 months back. Subjects
   in advisor language (RESP top-up, rebalance confirmation, beneficiary
   change, RRIF planning), no lorem-ipsum.
3. **Recent captured emails (manual, not engine):** 2–3 real emails sent
   between the demo mailboxes in the days before capture, plus the CIRO
   forward itself (asset already written:
   `Demo Centre/sail-through-audits-adam-email.md`, composed natively in
   the demo Outlook mailbox — never via Resend).
4. Open task for the story day: "Compile CIRO audit file — Renaud
   household", due end of week (Task shape per CLAUDE.md).
5. Audit notes swept after seeding; verify with read-backs.

## Resolved (2026-07-17)

- **Step 3 wording:** option (a) chosen — tooltip softened to "every
  client conversation" in the tour drafts file, build note added.
- **Documents:** probe FAILED (DocumentObject rejects AbEntryKey/DocData;
  see CLAUDE.md). Documents scoped out; notes carry the trail. Revisit
  via Schema $TREE /Document only if a story needs real files.
- **Date Last Contacted consistency:** seeder set it 9 days back but the
  yearly cadence left the newest interaction ~11 months old. Patched with
  `engine/fix-sail-through-audits.py` (one incoming call, 9 days back,
  Céline's OAS question). Fold a years_ago=0 call into the seeder before
  the next fresh seed.

## Still open (pre-capture, not blocking data)

- **Compliance report / export beat (steps 5–6):** UI feature — confirm
  the demo tenant actually has the report before capture day.
- **Outlook auto-log wording (step 3):** product gate still unconfirmed
  (what logs hands-free vs what takes a click).
- **Voice decision:** Walk In Ready moved to third person (Adam the
  star); this tour is still second-person Bridget. Decide before capture.

## Seeding

- Adapt `engine/seed-walk-in-ready.py` → `engine/seed-sail-through-audits.py`
  (same validated shapes; ~35 calls ≈ 1 min at rate-limit pace).
- Run the morning of the recording; all dates relative.
- Cleanup: `--cleanup` off the manifest. Household is story-scoped, not
  cast-protected — safe to clean unless Lewis promotes it to `cast/`.
