# Cameron story: the hero household

Tenant: Futureproof. Household: Peter and Mary Cameron Family, Coalmont BC.
Peter b. 1942-04-29 (84), Mary b. 1943-08-19 (83). Investia accounts per the
data handoff: Peter RRIF 620K, Mary RRIF 410K, Peter LIF 185K, joint cash 312K.

## The prompt this has to answer

> Tell me the Camerons' story in under 120 words, then what I should raise
> with them. Use only what is in Maximizer.

## Where the story lives, and why

The MCP connector can only do bare, unfiltered reads. Calls (49 rows) and
Tasks (56 rows) come back in full with Description text. Notes and
Appointments each exceed the 100-row cap, cannot page, and cannot be
filtered, so anything written there may never be seen. The story is carried
in InteractionLog Descriptions and open Tasks only. Structured hooks live on
the household's Estate Planning and Review Schedule fields, which the
household read returns when named.

## The arc (six calls, ~22 months, all owned by MASTER)

1. Annual review (~Oct 2024). Confirmed 2025 RRIF minimums. Peter raised
   selling the Penticton rental. Mary asked to simplify statements.
2. Mary calls (~Mar 2025). Rental sold, closing in May, ~$300K to the joint
   account. Asked what to do with it. Agreed to park it and review.
3. Follow-up (~Jun 2025). Peter wants the proceeds kept liquid, no market
   risk at his age. Revisit in the fall. Flagged that the will has not been
   looked at since 2015.
4. Peter calls (~Nov 2025). RRIF withdrawal timing for tax. Mentioned his
   brother, the named executor, had a health scare.
5. Spring check-in (~Mar 2026). Mary asked who is listed as beneficiary on
   the registered accounts; could not recall. Advisor to confirm with
   Investia. (Ties directly to the account-level beneficiary cleanup.)
6. Portfolio review call (2026-05-30, the existing decay call, Description
   enriched). Joint cash still ~$312K uninvested. Peter still reluctant.
   Agreed to bring their daughter into the fall review to discuss estate
   and executor. No contact since.

## Open tasks on the household (both overdue, assigned MASTER)

- Confirm beneficiary designations on the registered accounts with Investia
  (dated ~Mar 2026)
- Book the fall review and invite the daughter re: estate and executor
  (dated ~Jun 2026)

## Structured fields set on the household

- Is your Will prepared and signed? = Yes
- When was your Will last updated? = 2015-06-12
- Have you named your Executor and an alternate? = Yes
- Do you have a named beneficiary for your Registered Accounts? = No
- Last Estate Planning Review = ~4 years ago (relative)
- Next KYC Review = ~6 weeks ago (relative, overdue)

## What "raise with them" should surface

$312K idle for 16 months. Beneficiaries unconfirmed since March while the
account records are being corrected. Will untouched since 2015, executor an
86-year-old brother with a recent health scare, daughter not yet involved.
KYC review overdue. No contact in 104 days.

## Deliberate fictional details added here (not in the data handoff)

The Penticton rental sale (explains the cash), the brother as executor
(explains the estate urgency), the daughter as intended successor executor
(ties to the adult-child contacts still to be added). Children are NOT
named; those contacts and their names are Lewis's to create.

## Not written

No notes, no appointments (unreadable on stage). No opportunities (no sales
process configured). No children contacts (names not decided).
