# FA Intelligence renewal tiles — manual account entry (2026-07-21)

The six "Accounts - Upcoming Renewals" tiles read the FSE Accounts
module, which has NO API surface (probed to closure; see CLAUDE.md).
These entries must be typed into the Maximizer UI by hand, once. They
are supporting-cast only and all dates land inside this fiscal year
(= calendar year) so the This Fiscal Year filter keeps them.

## How to enter (general path)

1. In Maximizer, open **Address Book** and search the client named below.
2. Open their record and find the **Accounts** section (or use Accounts
   in the left menu and add an account linked to the client).
3. Add the account with the type, amount, and date from the table.
4. Repeat for each row. Then check FA Intelligence after its next data
   sync (the page shows the last sync time at top left).

If a field in the table doesn't exist on the account form, skip it; the
tiles key on account TYPE + the renewal/maturity/end DATE.

## The entries (10 rows, ~10 minutes)

| Client | Account type | Amount | Key date | Which tile it feeds |
|---|---|---|---|---|
| Bernie Jones | GIC | $75,000 | Matures 2026-08-11 | GIC – Expiry |
| Bill Burgerson | GIC | $40,000 | Matures 2026-09-04 | GIC – Expiry |
| Bill Church | GIC | $120,000 | Matures 2026-09-29 | GIC – Expiry |
| Bill Diamond | GIC | $25,000 | Matures 2026-11-03 | GIC – Expiry |
| Bernie Jones | Managed Segregated Fund | $180,000 | Renewal 2026-10-15 | Managed Seg Funds |
| Bill Roberts | Managed Segregated Fund | $310,000 | Renewal 2026-12-01 | Managed Seg Funds |
| Carlos Quentin | Managed Mortgage | $385,000 | Renewal 2026-11-20 | Managed Mortgages |
| Bill Church | Managed Insurance Policy | $500,000 coverage | Renewal 2026-10-08 | Managed Insurance |
| Bill Roberts | Annuity | $95,000 | End date 2026-12-10 | Annuities – End Date |
| ABC Business Solutions I | Group Benefits plan | 12 members | Renewal 2026-09-19 | Group Benefits |

Notes:
- GIC dates deliberately MATCH the GIC Expiry Date field already set on
  these clients via API (2026-07-21 run), so the record and the account
  never contradict each other on screen. If the swap script assigned the
  fifth GIC (~2026-12-08) to a different client, add a matching GIC row
  for whoever it picked.
- ABC Business Solutions I renewal matches the company field already set
  via API (2026-09-19). Advocis Publishing Inc has 2026-11-28 on its
  field if a second Group Benefits row is wanted.
- NEVER use Bill Graham (broken record, see CLAUDE.md).
- Amounts are illustrative Canadian-plausible figures; adjust freely.
  Dates should stay inside the current calendar year.

## Refresh reality

These are UI records the engine cannot roll forward. They will age out
of the fiscal-year window over time. Two options when they do: re-date
them by hand before a recording, or (better) ask product whether demo
tenants can get an Accounts data load - this is the same gap as dealer
feeds and the June 2026 insurance pilot.
