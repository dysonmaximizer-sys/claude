# Find the Coverage Gaps — manual policy entry (2026-07-22)

The Accounts/policy module has NO API surface (probed to closure
2026-07-21, see CLAUDE.md), so the policy rows the tour shows on screen
must be typed into the Maximizer UI by hand, once. Same drill as
docs/fa-intelligence-manual-accounts.md.

These rows make the Tremblay screens and the step-3 gap list honest:
the life policies exist, the CI/DI absence is real, and one term is
inside its conversion window.

## The entries (7 rows, ~7 minutes)

| Client | Account/policy type | Amount | Key date | Why it exists |
|---|---|---|---|---|
| Marc Tremblay | Term life (T-20) | $500,000 | Renewal 2027-03-01 | The "strong life coverage" on the flagged household |
| Sophie Tremblay | Term life (T-20) | $350,000 | Renewal 2027-09-01 | Same |
| Simon McKinney | Term life (T-10) | $250,000 | Conversion window closes 2026-10-30 | Step 3's "terms nearing conversion" row |
| Bill Diamond | Term life (T-10) | $150,000 | Conversion window closes 2026-11-15 | Second conversion row (Bill Diamond also carries a GIC row from the FA set) |
| Mary Gratton | Whole life | $100,000 | — | Life-only household: the "life but no living benefits" row |
| Jennifer Poulin | Term life (T-20) | $400,000 | Renewal 2028-02-01 | Life-only household, ditto |
| Joey Poulin | Term life (T-20) | $300,000 | Renewal 2028-02-01 | Life-only household, ditto |

Notes:
- Deliberately NO critical illness, disability, or living-benefit rows
  for any of these clients — the absence IS the coverage gap the tour
  filters for. Do not "complete" their coverage.
- Keep carrier names generic or omit them (accuracy gate: never imply a
  live carrier feed; these were "imported").
- Conversion-window dates stay inside the current calendar year so
  date-filtered views keep them.
- NEVER use Bill Graham (broken record, see CLAUDE.md).
- The five non-Tremblay names above are the exact clients the seeder
  dressed on 2026-07-22 (Life Insurance = Yes + review dates). If the
  story is ever cleaned up and reseeded, re-check which five it picked
  (printed by the seeder, captured in the manifest).

## Refresh reality

Same as the FA tiles: the engine cannot roll these forward. Re-date by
hand before a recording, or fold into the product conversation about a
proper Accounts data load for demo tenants (dealer-feed gap, June 2026
insurance pilot).
