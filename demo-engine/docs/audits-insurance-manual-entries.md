# Sail Through Audits (insurance) — manual entries (2026-07-22)

Two things the API cannot create: policy rows (Accounts module,
API-invisible) and documents (Document create blocked). Both are typed
or dragged into the Maximizer UI by hand, once, on the Chen household.

## Policy rows (5 rows, ~5 minutes)

| Client | Policy type | Amount | Placed | Notes |
|---|---|---|---|---|
| Michael Chen | Term life (T-20) | $750,000 | 2018 | Renewal 2038 |
| Michael Chen | Critical illness | $150,000 | 2020 | — |
| Michael Chen | Key-person life | $500,000 | 2021 | Business: logistics, ~19 staff |
| Grace Chen | Term life (T-20) | $400,000 | 2018 | Renewal 2038 |
| Grace Chen | Segregated fund | $160,000 market value | 2022 | $120K initial + $40K top-up 2025 |

Deliberately NO disability row for Michael: the 2023 notes document a
DECLINE, and the absence matching the paper trail is what makes the
file read as genuinely compliant. Do not add one.

Carrier names: your choice in the UI; spread across 2-3 carriers for
MGA realism. Keep them incidental (the accuracy gate is about feeds,
not names on records).

## Document uploads (drag-and-drop onto the Chen household, ~5 minutes)

The review notes reference signed documents "on file". Upload matching
PDFs so step 3's "notes and documents" is honest:

1. Needs analysis, signed (dated 2018) — referenced by the 2018 note
2. Needs analysis refresh, signed (dated 2024) — referenced by the 2024 note
3. DI decline acknowledgment, signed (dated 2023) — referenced by the 2023 note
4. Risk tolerance questionnaire (dated 2022) — referenced by the seg-fund note

Fictional PDFs are fine (and preferable). Ask Claude to generate the
four as branded, filled-in fakes if you don't want to mock them up —
5-minute job with the pdf skill.

## Also before capture

Compose the compliance-review request email natively in the demo
mailbox (generic regulator wording: "compliance review", "your MGA" —
never CIRO). Same drill as the FA-door version of this tour.
