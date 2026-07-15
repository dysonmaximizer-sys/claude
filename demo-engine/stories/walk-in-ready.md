# Story: Walk In Ready (Demo Centre hero tour)

**Persona:** Adam. **Scene:** 2:40pm, the 3:00 review moved to 2:45, last
spoke to the family in spring, no time to ask Bridget.
**Aha:** the complete, current client picture assembles in two clicks.

## Cast (seeded via API, keys in manifest)

| Who | Role in story |
|---|---|
| Sokolov Family (Household) | The record that assembles |
| Viktor Sokolov, 64 | Senior client, asked about bridging to 65 |
| Marina Sokolova | Birthday NEXT WEEK (relative); owns the open RESP question |
| Daria Sokolova, 17 | RESP maturing — the reason the June question exists |

## What must be true in the data on recording day

1. Last conversations dated SPRING (~14 weeks back): review note + follow-up
   call. Nothing between then and June — "the file has been closed since."
2. The OPEN RESP question from June: incoming call + open-item note
   (emails cannot be fabricated on this tenant — see CLAUDE.md).
3. Marina's birthday falls within the next 7 days.
4. Today's calendar: "Sokolov household annual review", 2:45 PM.
5. Open items visible: RESP follow-up task (due next week) + open
   opportunity "RESP maturity transition plan" (~$45k, closes in ~45 days).

## Seeding

- `engine/seed-walk-in-ready.py` — creates household, contacts, timeline.
  Run the morning of the recording (all dates are relative).
- `engine/fix-walk-in-ready.py` — one-time patch for the July 15 seed
  (birthdates, June call replacing blocked email, task). Fold its
  discovered field names back into the seeder when confirmed.
- Cleanup: `seed-walk-in-ready.py --cleanup` (uses the manifest).

## Out of engine scope (flag for the Storylane build)

- "Account up since April" (step 4 of the tour) is dealer-feed portfolio
  data — cannot be fabricated through the CRM API. Needs the demo tenant's
  wealth-data source, or the capture avoids that panel.
- Step 5 talking points: surfaced from record data (open items above feed
  it) — do not imply AI authorship (accuracy gate in the tour script).
