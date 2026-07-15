---
name: maximizer-demo-data-generator
description: Generate the bulk cast-refresh CSV for Maximizer's demo Address Book — roll dates forward on the persistent 77-contact cast (matched on IDentification) so demos never expose real customer data and milestone stories (turning 65, KYC overdue) stay true. Use this skill ONLY when Lewis asks for a bulk refresh of the whole cast or a CSV to re-import into the Address Book, e.g. "refresh the cast", "roll the demo dates forward", "update the dummy contacts", "regenerate the demo CSV". Do NOT use for seeding demo stories, creating records, opportunities, notes, calls, tasks, appointments, households, or any back-dated history — that is the maximizer-demo-engine skill's job (API-first; live testing in July 2026 proved the CSV import wizard corrupts on everything except this cast refresh).
---

# Maximizer Demo Data Generator

## Scope check first (validated July 2026)

This skill produces ONE thing: the bulk Address Book cast-refresh CSV,
imported as update matched on IDentification. Live testing proved the CSV
import wizard corrupts on everything else — it creates orphan Individual
records and fails on re-import for opportunities, notes, activities, and
interactions. So before doing anything:

- Request involves creating records, story history, opportunities, notes,
  calls, tasks, appointments, or households ("seed a story", "client with
  an open RESP question", "set up the tenant for a recording")? STOP —
  that is the **maximizer-demo-engine** skill (API-first, repo at
  `/Users/lewisdyson/Claude Code/demo-engine/`). Do not build it as CSV.
- Request needs both a fresh cast AND a seeded story? Do this skill's CSV
  refresh first, then hand off to maximizer-demo-engine to seed on top.
- Request is purely "roll the cast's dates forward" / "regenerate the demo
  CSV"? You're in the right place — continue below.

Produce an upload-ready CSV that refreshes the Maximizer demo Address Book.
The database is a fictional Canadian financial advisory practice. The same
cast of contacts persists across every demo so product stories stay
consistent between videos; only dates roll forward and only story-relevant
records change.

Two inputs, one output:
- **Cast registry** (`assets/cast.json`) — the permanent roster: 77 records
  with real Maximizer IDs, static fields, and *date rules* instead of stored
  dates for story-critical contacts.
- **Story overlay** (written fresh per request) — only the records this
  story changes.
- **Output** — a validated CSV plus a short "who changed and why" summary
  Lewis can use as demo notes.

## Why dates are rules, not values

"Jameson turns 65 in three weeks" must stay true whether the demo is
recorded today or next March. So the cast stores `{"rule": "turns",
"age": 65, "in_days": 21}` and the generator recomputes the actual
birthdate from the run date. Same for KYC review dates (overdue / due-soon
states) and last-modified recency. Never hardcode a date for a
story-critical contact — add or adjust a rule instead.

## Built-in story slots

The cast already covers the recurring Maximizer FA stories. Check these
before inventing new records — reusing the cast keeps demos consistent:

| Contact | Tag | Always true at generation time |
|---|---|---|
| Jameson Thomas | milestone-65, kyc-current | Turns 65 in 21 days; KYC done 12 days ago |
| Lou Harris | milestone-65 | Turns 65 in 45 days |
| Celene Smith | milestone-71 | Turns 71 in 35 days (RRSP→RRIF story) |
| Lou Cameron | kyc-overdue | KYC review 55 days overdue |
| Nancy Cameron | kyc-due-soon | KYC due in 14 days |
| Wilson Poulin | birthday-this-week | 77th birthday in 5 days (birthday automation) |
| Melissa Myles | estate-planning | Oldest client, b. 1941 |
| Paula/Roberto Cameron, Tasha Graham | minor-child | Household children |
| 12 more contacts | background-client | Rolling KYC dates spread over the year |

Everything else is background: stable names, addresses, static birthdates,
refreshed last-modified dates.

## Workflow

1. **Confirm this is a cast refresh.** If the request is "refresh the
   cast" / "roll dates forward", proceed with no overlay. If it names
   Address-Book-field states the refresh should include ("make Nancy's KYC
   overdue too"), that's a legitimate overlay. Anything beyond Address
   Book fields belongs to maximizer-demo-engine (see Scope check).

2. **Map changes to records.** Prefer existing cast members (table above)
   over new ones. Only write an overlay for genuine changes — a new
   Position, an extra overdue KYC, a throwaway prospect. Read
   `references/field-schema.md` before touching any field you haven't used
   yet; it lists formula fields that must stay blank, ID rules, and the
   UDFs available for richer stories. Write the overlay JSON to a temp
   file (format documented at the top of `scripts/generate_demo_data.py`).

3. **Generate.**
   ```bash
   python3 scripts/generate_demo_data.py \
     --cast assets/cast.json \
     [--story /tmp/story.json] \
     [--date YYYY-MM-DD] \
     --out "<output folder>/maximizer_demo_data_YYYY-MM-DD.csv" \
     --summary /tmp/summary.md
   ```
   Rolling dates anchor to the run date. If Lewis mentions when the demo
   happens ("recording next Thursday"), pass that day via `--date` so
   "turns 65 in 21 days" is true on camera, not just today. Save the CSV
   to the folder that owns this work — Lewis's PMM folder by default, or
   wherever he says the demo assets live.

   Cast source of truth, in order of preference:
   1. `/Users/lewisdyson/Claude Code/demo-engine/cast/cast.json` — the
      git-versioned registry (canonical since July 2026).
   2. A `demo-data-cast.json` working copy in Lewis's folders (legacy
      override; if found, suggest committing it into the repo cast).
   3. The bundled `assets/cast.json` — last resort; it may be stale.

4. **Check the result.** The script validates (ID integrity, KYC date
   consistency, plausible ages, formula fields blank) and exits non-zero on
   failure — never deliver a CSV from a failed run. Read the summary it
   prints and sanity-check it against the story: are the right people in
   the right states?

5. **Deliver.** Give Lewis the CSV and the change summary. Remind him:
   import as update matched on IDentification, Address Book entries ONLY —
   never feed the wizard opportunities, notes, activities, or interactions
   (it creates orphan Individuals and fails on re-import). A quick
   spot-check of one changed record after import catches mapping drift.

## Permanent cast changes

If Lewis asks for a change that should survive future refreshes (a new
permanent household, a renamed company, a new story slot), edit
`/Users/lewisdyson/Claude Code/demo-engine/cast/cast.json` and commit it —
that repo file is the source of truth. Overlays are for one-off demo
states; the cast is for the world itself. Records the Demo Engine keeps
permanently (e.g. the Sokolov household) also belong in the cast registry
so a bulk refresh never collides with them.

## Hard rules

- Never invent or alter an IDentification value. Replace-import matches on
  it; a wrong ID corrupts a different record. New throwaway records get an
  empty ID.
- Never write values into formula fields (Days Since..., Current Age,
  Insurance Age) — Maximizer computes them.
- Never use real customer names or data. The whole point of this skill is
  keeping real customers out of demos. If a story request names what looks
  like a real client or firm, swap in a fictional stand-in and say so.
- Keep the Canadian-realism guardrails from `references/field-schema.md`.
