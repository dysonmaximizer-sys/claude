# Futureproof demo: investment accounts seed

For Diego. Companion file: `futureproof-accounts-for-diego.json`.

## Why JSON rather than CSV

Positions are children of accounts, and an account's key does not exist until the account is created. CSV cannot carry that parent-child reference without a second lookup pass. The JSON mirrors the object shapes you already use, so each block can go straight into a create call.

## What is in the file

Five operations, numbered. Run them in that order. Step 2 must run before step 3, because step 3 sets absolute cash values that must not then be doubled.

1. **`1_delete_accounts`** — two accounts on Peter and Mary Cameron Family. Both are currently typed CAD LIRA and categorised joint. A LIRA is locked in from an individual pension and cannot be held jointly, and Peter and Mary are 84 and 83, so that money would have been converted long ago. Two Canadian advisors in the audience will spot it. These are replaced in step 3.

2. **`2_scale_existing_accounts`** — a bulk multiply of 2.0 on market value and cash for every remaining account whose ID starts ACC-DH-. Without this the 19 households nobody is rebuilding sit an order of magnitude below everything else and read as stale data. One query, one loop. See the note below about positions.

3. **`3_update_accounts`** — three absolute cash balances on existing accounts, applied after the scaling. Account keys and IDs are in the file. Nothing else on those accounts changes.

4. **`4_create_accounts`** — 104 new accounts. 100 across the 52 households the demo engine created this week, plus 4 rebuilt accounts for Peter and Mary Cameron.

5. **`5_create_positions`** — 520 holdings. Each carries `ParentKey` as a placeholder in the form `{{FP012-A034}}`. Resolve it to the key returned when the account with that `account_ref` was created in step 3. `WithKey` is already the household AbEntry key and needs no substitution.

## Four things to know before you start

**Step 2 leaves the old positions un-rescaled.** Positions under the pre-existing ACC-DH accounts are not being touched, so after the multiply their totals will no longer add up to their account's market value. Nothing in the demo reads those positions, so this is acceptable, but say so if it bothers you and Lewis will decide whether to rescale them as well.

**Parent keys are AbEntry-prefixed.** Every `ParentKey` in the file decodes to `AbEntry\t...`, which is how the existing DataHub accounts in this tenant are parented. The demo engine's manifest stores the same records with an `Individual\t` prefix. Those will not work here, so use the keys in this file rather than the manifest.

**Account IDs are ACC-FP-001 upward.** The existing set runs ACC-DH-001 to ACC-DH-046. Keeping the new set on its own prefix means you can find or roll back everything this file created with one query.

**Mary Cameron's RRIF has a deliberately empty beneficiary.** That is the point of one part of the demo, not an oversight. Please leave it blank.

## Sanity figures to check against when you finish

- 104 accounts created, 520 positions created
- New accounts total about $81.8M in market value and $2.1M in cash
- Whole book after seeding: about $100.5M across 75 households
- Positions on each NEW account sum exactly to that account's total market value. This was verified before the file was written, so a mismatch afterwards means something dropped in transit. Pre-existing accounts are exempt, per the note above.
- Only four households hold more than $200,000 in cash: Peter and Mary Cameron about $660,000, Hartfield about $377,000, Poulin about $311,000, Vincent about $240,000. The next highest is about $51,000. If a fifth household appears above $200,000, something went in twice.

## On the data itself

Everything is fictional. Fund descriptions and symbols follow the format a Canadian statement uses and will look right to an advisor, but they are not verified against any real fund database and some may not correspond to a real product. No figure in this file represents real product performance, and nothing here should be reused in marketing material that implies it does.
