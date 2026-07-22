# Story: Find the Coverage Gaps (Insurance door, gated tour 2)

**Persona:** Ingrid (third person on the surface, per the 2026-07-21
re-voicing). **Scene:** growing multi-line revenue from the existing book;
the gaps are invisible without the admin trawling the spreadsheet.
**Aha:** the book filtered in one view shows which households are a line
short — a list of names instead of a hunch.

## Cast

| Who | Role in story |
|---|---|
| Tremblay Family (Household, Burnaby BC) | Step 4's flagged household |
| Marc Tremblay, 42 | Term life $500K; self-employed since Jan; NO DI — the money gap |
| Sophie Tremblay, 39 | Term life $350K; asked "what if Marc can't work" 5 weeks ago |
| Leo (9), Chloe (6) | The two kids; RESP $38K on the household |
| 5 dressed cast clients | Step 3's filtered-list rows (Life=Yes, reviews due/overdue) |

## What must be true in the data on recording day

1. Tremblay adults: Life Insurance = Yes, named beneficiaries = Yes,
   insurance objective 4/5, Last Insurance Needs Review ~14 months back,
   Next review ~3 weeks out. Household: Segmentation B, RESP $38,000.
2. The RECORDED gap: last year's review note says CI/DI was discussed and
   deferred; Sophie's call 5 weeks ago asks the DI question directly.
   (No CI/DI field exists on the record — the gap IS the absence, and the
   history proves the advisor knows it. This matches the tour's accuracy
   gate: visibility, not AI discovery.)
3. Working artifacts: task "Prepare CI and DI options" due +10 days; open
   opportunity "Family protection review - CI and DI" (~$3,600, Individual
   Insurance-appropriate, closes +45 days).
4. At least 5 more clients filterable as due/overdue for insurance review
   with life coverage on record (the step-3 list has rows beyond Tremblay).

## Seeding

- `engine/seed-find-the-coverage-gaps.py` (seed / --cleanup). Cleanup also
  RESTORES the five dressed cast clients' prior UDF values (captured in
  the manifest under "modified").
- Refresh: `refresh-story.py --story find-the-coverage-gaps` rolls the
  note/call/task/opportunity dates. The UDF review dates do NOT roll
  (refresh-story only shifts record datetimes + Date Last Contacted) —
  reseed, or re-dress by hand, if the story goes stale by months.

## Out of engine scope (flag for the Storylane build)

- **Actual policy rows** (term amounts, renewal/conversion windows, seg
  funds) live in the Accounts module, which is API-invisible. Manual UI
  entry: see `docs/coverage-gaps-manual-policies.md`. Without them, any
  screen showing a policy LIST cannot be staged; the record-level fields
  above are what the API can honestly stage.
- **Step 3's filter view**: confirm with product what Insurance Suite
  filtering natively surfaces (the tour's own accuracy gate). The data
  supports filtering by Life Insurance = Yes + Next/Last Insurance Needs
  Review; do not imply auto-discovery.
- **Step 5's "review campaign"**: a UI action during capture, not data.
- **Book size**: ~90 entries vs the modal's "hundreds of households" —
  same expansion question as See Your Whole Book, still awaiting Lewis's
  go (see handoff).
- Tour copy says the Tremblay name is a placeholder "to swap for cleared
  demo data" — these ARE the cleared demo records now; the tour can keep
  the name.
