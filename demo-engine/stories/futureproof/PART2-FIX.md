# Claude Code: Part 2 and Part 3, corrected

Part 1 completed cleanly: 52 households and 85 contacts created, all keys in the manifest. Part 2 and Part 3 did not run.

One correction before you run it. The original instructions renamed the two spare Cameron households to Marchetti and Antonelli. Both of those surnames were also used for new households in Part 1, so those targets would collide. Use the surnames below instead.

## Paste this into Claude Code

> Read CLAUDE.md and docs/futureproof-tenant.md. Source the Futureproof env in the same command as every run: `set -a; source futureproof.env; set +a`.
>
> Part 1 is done. Do Part 2 and Part 3 of stories/futureproof/BUILD-INSTRUCTIONS.md now, with the corrections below. Record every change in manifests/futureproof/build-the-book.json under a separate "part2" section so it can be reversed independently.
>
> **Renames.** Do NOT use Marchetti or Antonelli. Those surnames already belong to households created in Part 1.
> - "Cameron Family" (Calgary; Lou, Nancy, Paula, Roberto) becomes "Lou and Nancy Whitfield Family". Change the surname on all four contacts to Whitfield.
> - "Michael and Jennifer Cameron Family" (Vancouver; Michael, Jennifer, Rita) becomes "Michael and Jennifer Sorenson Family". Change the surname on all three contacts to Sorenson.
> - Before you write anything, confirm no household or contact in the tenant already uses Whitfield or Sorenson. If either is taken, stop and tell me.
> - "Peter and Mary Cameron Family" keeps its name. After this, it must be the only Cameron in the tenant. Verify that and report the count.
>
> **Contradiction to clear.** Lou's "Names of Children" field reads "Bill and Monica" while his actual child contacts are Paula and Roberto. Set that field to "Paula and Roberto".
>
> **Segmentation.** Set Segmentation to 1 (A Client) on exactly these three: Peter and Mary Cameron Family, Hartfield Family, Vincent Household. Hartfield is already 1. Cameron is currently 3 and Vincent is currently 2, so both need changing. Read all three back afterwards and show me the values.
>
> **Provinces.** Four households have a province that does not match the city. Set the province to match: Lewis Household is Ottawa ON, "Harris, Household" is Ottawa ON, "Thomas, Jameson - Thomas Household" is Dallas, "Thomas Household" is Dallas.
>
> **Relocate the US households into Canada,** keeping the records rather than deleting them. Give each a matching postal code.
> - Jones Family, currently Seattle WA, becomes Kamloops BC
> - "Myles, Rick and Melissa", currently San Diego CA, becomes Canmore AB
> - "Thomas Household", currently Dallas, becomes Regina SK
> - "Thomas, Jameson - Thomas Household", currently Dallas, becomes Guelph ON
>
> **Graham.** Rename "Graham, Bill - Advocis Publishing Inc" to "Graham Household". Do not attempt any UDF write on that record. If the rename reads back unchanged, leave it and tell me.
>
> **Then verify and report:**
> - Total household count (expect 75) and total contact count
> - The full list of Segmentation 1 households
> - Maximum days since last contact across the whole book, and the name of any household over 90 days other than Peter and Mary Cameron, Hartfield and Vincent
> - Any household with a non-Canadian province (expect none)
> - Confirmation that exactly one household is named Cameron
>
> Finally, sweep the audit notes this run generated, update docs/futureproof-tenant.md, and commit. Do not push. Before committing, confirm futureproof.env is gitignored.
