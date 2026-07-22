# Story: See Your Whole Book (Demo Centre gated tour 3)

**Persona:** Adam. **Scene:** month-end; a quiet household left for an
online brokerage and Adam wants to know who else has gone quiet without
building a report. **Aha:** the whole book on one screen with the
between-meetings problems already flagged (step 4 must show flags
actually tripping).

## Scope decision (Lewis, 2026-07-20)

**Investment and insurance data skipped.** The tour's "accounts that
moved this quarter" flag, step 5's "assets up since spring" and "GIC
maturing next month" are dealer-feed / policy data the engine cannot and
should not fabricate (CLAUDE.md; tour build notes 2026-07-06 already say
cut the account-movement flag rather than fake it). This story seeds the
two flags the CRM owns outright:

- **Overdue KYC review** (Next KYC Review in the past)
- **Gone quiet** (Date Last Contacted > 90 days)

The tour's step 4/5 capture should frame on these two flag types. Note
history deliberately avoids account values, products, and policies.

## Why NEW households (not flags on the cast)

The 75-record cast got fresh future KYC dates and profiles on 2026-07-16,
so nothing in the book trips a flag today. Writing overdue dates onto
cast records would fight the CSV refresh date rules (next bulk refresh
un-flags them silently). Instead this story creates five manifest-tracked
households that carry the flags, cleanable without touching the cast.

## Cast (all fictional, milestone-age-free on purpose — no birthday flags)

| Household | City | Flags tripped | Texture |
|---|---|---|---|
| Okafor Family (HERO, step 5 click-in) | Hamilton, ON | KYC overdue ~3 wks + quiet ~4.5 mos | 3 years of reviews/calls, cadence visibly stops; spring check-in postponed, never rebooked; NO upcoming appointment |
| Whitfield Family | Victoria, BC | Quiet ~100 days | KYC current; last touch a reschedule call |
| Bianchi Family | Mississauga, ON | KYC overdue ~6 wks | Contact recent (~1 mo) — overdue flag only |
| Grewal Family | Surrey, BC | KYC overdue ~2 wks + quiet ~4 mos | Second drifting household |
| Fortin Family | Gatineau, QC | Quiet ~95 days | Borderline case — just past the 90-day line |

## What must be true in the data on recording day

1. Five households + contacts exist with full profiles (segmentation
   B/C spread — quiet households are not A-list; addresses; phones).
2. **Date Last Contacted equals each household's newest real interaction**
   (the Marina lesson: never a bare UDF date with no matching record).
3. KYC overdue dates are relative to seed day; quiet gaps are relative.
4. Hero household has believable multi-year history that visibly stops,
   and no future appointment anywhere.
5. Audit notes swept; flags verified by read-back (script prints which
   flag each household trips).

## Known limits (flagged to Lewis)

- Book size stays 82+5 entries vs the tour script's "~300 households";
  bulk expansion is a separate decision (open since 2026-07-16).
- "Accounts that moved this quarter" flag: cut from the capture, per
  tour build note, unless the dealer feed is populated for real.
- refresh-story.py rolls interactions and Date Last Contacted (gaps
  preserved) but not KYC dates — after several months of refreshes the
  overdue-by drifts longer; harmless, reads as "really overdue".

## Seeding

- `engine/seed-see-your-whole-book.py` (~36 records, ~1.5 min at pace).
- Manifest: `manifests/see-your-whole-book-manifest.json`.
- Cleanup: `--cleanup` (reverse order, manifest removed).
- Refresh: `refresh-story.py --story see-your-whole-book`.
