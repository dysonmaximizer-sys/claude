# Claude Code: create the Futureproof demo book

Two inputs: this file and `futureproof-new-households.csv` (52 rows). Put the CSV in `stories/futureproof/` before you start.

Read `CLAUDE.md` and `docs/futureproof-tenant.md` in full first.

---

## Prompt to paste into Claude Code

> Read CLAUDE.md and docs/futureproof-tenant.md in full before doing anything.
>
> We are building out the Futureproof demo book. Source data is `stories/futureproof/futureproof-new-households.csv`, 52 rows. Source the Futureproof env in the SAME command as every run: `set -a; source futureproof.env; set +a`.
>
> **Before writing anything**
>
> Confirm against docs/futureproof-tenant.md, not against the FSE tenant, that these exist and are assignable in THIS tenant, and stop and report if any differ:
> - Birthdate
> - Date Last Contacted (writable; "Days Since Last Contacted" is a formula off it, never write that)
> - Segmentation (1=A Client, 2=B, 3=C, 4=D; write the key as a plain string)
> - Next KYC Review
> - Record Type (1=Client)
>
> Write a story spec at `stories/futureproof/build-the-book.md` describing what this run creates, then create `manifests/futureproof/build-the-book.json`. Every created key goes in the manifest as you go, not at the end, so a failed run can still be cleaned up.
>
> **Part 1: create 52 households**
>
> For each CSV row, in `ref` order:
> 1. Create the household. Use the validated household create shape for this tenant, with `household_name` as the name.
> 2. Set on the household: Segmentation, Next KYC Review, Record Type, Date Last Contacted, and the address (city, province, postal code). Address writes go through the nested Address sub-object on update; verify via an Address-object read by ParentKey, never by an AbEntry-scope read, which returns null unreliably.
> 3. Create contact 1 with ParentKey pointing at the household. Set first name, last name, birthdate, email, phone, and the same address.
> 4. Where `contact2_first` is populated, create contact 2 the same way. Set Position to "Husband" or "Wife" to match the existing Calgary Cameron household convention, choosing by given name where it is unambiguous and leaving it blank where it is not.
> 5. Record the household key and both contact keys in the manifest against the `ref`.
>
> Pace at roughly 0.35s per call and honour Retry-After. This is about 350 calls, so budget four to five minutes.
>
> Do NOT create notes, interactions, appointments, tasks or opportunities in this run. Those come later and only on a handful of households.
>
> **Part 2: fix the existing records**
>
> 1. Rename these so only one household in the tenant is called Cameron:
>    - "Cameron Family" (Calgary, Lou and Nancy, two teenagers) becomes "Lou and Nancy Marchetti Family". Update both parents and both children to the surname Marchetti.
>    - "Michael and Jennifer Cameron Family" (Vancouver, with Rita) becomes "Michael and Jennifer Antonelli Family". Update all three contacts.
>    - "Peter and Mary Cameron Family" (Coalmont) keeps its name. It is the hero household.
> 2. Fix the four households where city and province disagree. Set the province to match the city: Lewis Household is Ottawa ON, Harris Household is Ottawa ON, "Thomas, Jameson - Thomas Household" is Dallas, and Thomas Household is Dallas.
> 3. Relocate the four US households to Canada rather than deleting them, so the book reads as Canadian. Assign: Jones Family to Kamloops BC, "Myles, Rick and Melissa" to Canmore AB, Thomas Household to Regina SK, "Thomas, Jameson - Thomas Household" to Guelph ON. Give each a matching postal code. Report the count of remaining non-Canadian addresses when done.
> 4. Set Segmentation to 1 (A Client) on exactly these three households: Peter and Mary Cameron Family, Hartfield Family, Vincent Household. The demo asks about A clients, so this list must be deliberate.
> 5. Rename "Graham, Bill - Advocis Publishing Inc" to "Graham Household". Do not attempt UDF writes on it. In the FSE tenant the equivalent record silently rejects UDF updates while returning success, so if any write to it reads back null, leave it alone and tell me.
>
> **Part 3: verify and report**
>
> Read back and report:
> - Total household count, and total contact count
> - How many households have Date Last Contacted set, and the maximum days since contact across the whole book. Every household except Peter and Mary Cameron, Hartfield and Vincent must be inside 90 days. If any others exceed it, list them.
> - The full list of Segmentation 1 households
> - Any household with a non-Canadian province
> - Any of the 52 whose address failed to store
>
> Then sweep the audit notes this run generated and confirm the sweep. Finally, update `docs/futureproof-tenant.md` with anything new you learned and commit, but do not push.

---

## Notes on the data

Book after this run: 75 households, roughly $49.5M in assets once Diego seeds the accounts, average household about $660,000. That reads as a real mid-market Canadian practice. The existing 23 stay as they are apart from the fixes above.

Names avoid every surname already in the tenant, the Maximizer persona names, and Lewis's own. Emails are @mail.test and phones are 555 numbers, per the engine's fictional-data rule.

Every one of the 52 is contacted inside 90 days and holds under $30,000 in cash. That is deliberate: it keeps the idle-cash answer and the coverage-decay answer to the three households the demo is built around. Adding a household that breaks either rule breaks Beat 1.

Segmentation is now the control for "most valuable households" rather than an AUM quintile. Nine of the new households are A clients, plus the three demo households, so twelve in total. A ranked quintile would shift every time Diego changes an account value; a segmentation list will not.

`target_aum`, `target_cash`, `target_market_value` and `account_count` are not written to Maximizer. They are the plan for Diego's accounts file, carried in the same CSV so there is one source of truth. Do not try to write them.
