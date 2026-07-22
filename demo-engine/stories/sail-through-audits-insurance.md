# Story: Sail Through Audits — INSURANCE door (gated tour 3)

Distinct from the FA-door story of the same name (Renaud household,
CIRO, Bridget). This is Ingrid's regime: MGA and provincial, regulator
kept GENERIC in every record — no CIRO anywhere in this data.

**Persona:** Ingrid (third person on the surface). **Scene:** a
compliance review lands with two weeks notice; the full file on a
household served for years. **Aha:** the file assembles clean because it
was logged along the way.

## Cast (per Lewis 2026-07-22: the Chen family)

| Who | Role in story |
|---|---|
| Chen Family (Household, Guelph ON — Ingrid's town) | The audited file |
| Michael Chen, 52 | Business owner (logistics, ~19 staff): term $750K, CI $150K, key-person $500K, documented DI DECLINE |
| Grace Chen, 50 | Term $400K, seg fund $160K, CI quote pending |

## What must be true in the data on recording day

1. Eight years of annual reviews (2018-2025), each an appointment PLUS a
   suitability note: needs analysis signed (2018, refreshed 2024), CI
   added 2020, key-person 2021, seg fund 2022 (+top-up 2025), and the
   compliance-gold detail — DI discussed 2023, DECLINED, rationale
   documented and acknowledged.
2. Correspondence: seven calls across the years, the latest 3 days ago
   about the MGA compliance review notice itself.
3. Today's moment: open task "Compile compliance file - Chen household
   (MGA review)" due +5 days, owned per rule 10.
4. Profiles: household Segmentation A, last contacted 3 days ago; both
   adults Life Insurance = Yes, beneficiaries named, last insurance
   review ~1 year back, next in ~2 months.

## Seeding

- `engine/seed-sail-through-audits-insurance.py` (seed / --cleanup).
  27 records; manifest `sail-through-audits-insurance-manifest.json`.
- Refresh: `refresh-story.py --story sail-through-audits-insurance`
  rolls the whole trail forward (gaps preserved). UDF review dates do
  not roll; re-dress if stale by months.

## Out of engine scope (manual, before capture)

- **Policy rows + document uploads:** see
  `docs/audits-insurance-manual-entries.md`. Step 3 shows "notes and
  documents" and step 4 assembles "policies, suitability notes, and
  documents" — documents cannot be created via API (blocked, CLAUDE.md)
  and policies live in the API-invisible Accounts module.
- **Step 2's inbox** (the compliance request email): emails cannot be
  fabricated. Compose the reviewer's request natively in the demo
  mailbox before capture, as the FA-door version does.
- **Steps 4-6** (assemble/preview/export): confirm with product exactly
  what compliance output Insurance Suite produces (the tour's own
  accuracy gate). The data trail is ready either way.
