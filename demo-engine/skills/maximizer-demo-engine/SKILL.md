---
name: maximizer-demo-engine
description: Seed, refresh, and clean up demo stories in Maximizer's demo tenant via the Octopus API, so sales demos, Demo Centre recordings, and Storylane captures always have believable, current data. Use this skill whenever Lewis asks to "seed a story", "set up the tenant for a demo/recording", "refresh the demo data for my call", "create a household/client with history", "clean up a story", mentions the Demo Engine, a named story (e.g. "Walk In Ready", the Sokolov household), or describes any demo scenario needing records CREATED in the tenant (opportunities, notes, calls, appointments, tasks, households, or back-dated history). Trigger even if he only names a feature and a recording date. NOT for the bulk cast-refresh CSV (77-contact Address Book roll-forward); that stays with maximizer-demo-data-generator.
---

# Maximizer Demo Engine

Conversational front end for the Demo Engine: deterministic Python seeders
that create and maintain story data in Maximizer's demo tenant through the
Octopus API. Lewis (PMM, non-developer) describes the story he needs; you
run the engine and report back in plain language.

## Where everything lives

The engine is a git repo folder: `/Users/lewisdyson/Claude Code/demo-engine/`
(note: NOT `~/Desktop/Claude Code`, which is a different folder).

**Read `demo-engine/CLAUDE.md` before touching the tenant. Always.** It is
the single source of truth for hard rules, validated API payload shapes,
blocked operations, and tenant field IDs. Knowledge lives there, not here.
If you learn something new about the tenant, record it there, never in this
skill. Do not re-test what CLAUDE.md already records; the entries were paid
for with live-tenant debugging.

Layout: `engine/` (seeders), `stories/` (one spec per story), `manifests/`
(created-record keys, gitignored), `cast/` (persistent cast), `docs/`.
Auth: PAT in `.env` at the repo root; load it, never read or print it.

## Safety rules that bear repeating

CLAUDE.md is authoritative, but these are the ones that protect a live
shared tenant, so they are worth holding in mind before it is open:

1. Demo tenant only. Real customer names or unexpected volumes = STOP.
2. API by key, never the CSV import wizard (it corrupts on anything except
   bulk cast refreshes; validated July 2026).
3. Every created key goes in a manifest; never seed over an existing
   manifest; cleanup deletes in reverse order.
4. Times are intended-Pacific, converted to UTC before sending (see `d()`
   in the seeder). Dates are relative to the demo day, never hardcoded.
5. After any run that writes, sweep the auto-logged audit notes and verify
   changes with API read-backs before telling Lewis it worked.

## The four requests this skill serves

**Seed a story** ("set up X for Tuesday's recording")
1. Read the spec in `stories/`, or draft one from Lewis's description
   first (aha moments and what must be true in the data, not screen detail)
   and confirm it with him before writing anything to the tenant.
2. Check no manifest exists for the story.
3. Run or adapt a seeder. New object types: check CLAUDE.md's validated
   shapes first, and add whatever you learn back into CLAUDE.md.
4. Verify with read-backs, sweep audit notes, then give Lewis a short
   eyeball checklist for the Maximizer UI before he records.

**Refresh on demand** ("refresh the demo data", "get it ready for my 10am")
Refresh is deliberately on-demand, not scheduled, because stories only need to be
true the day they're shown. Roll the dates on manifest records forward so
the story is true today (relative gaps preserved: "the June call" stays
~5 weeks back, the annual review lands today, open tasks land next week),
sweep audit notes, verify, report.

**Clean up a story** ("remove the Sokolov story")
Delete manifest records in reverse creation order, confirm each deletion,
then delete the manifest. Permanent additions belong in `cast/`, not
deleted. The Sokolov household is currently KEPT. It is the Phase 1
dogfood data; do not clean it up without Lewis explicitly asking.

**Add to the story library** ("new story: advisor spots an insurance gap")
Write the spec in `stories/<slug>.md` around the persona's aha moments
(load maximizer-personas if the persona is unclear), then treat as a seed.

## How to work with Lewis

- Plain language, results first, code invisible unless he asks.
- Anything he must do in a terminal or the Maximizer UI: numbered,
  zero-knowledge steps, one action per step. Ask him to paste failures
  back verbatim.
- After every session that changes the tenant or the engine, update the
  handoff doc in the repo (session-handoff skill) and commit. Push only
  with his go-ahead.
- Rollout is currently Phase 1: Lewis only. If anyone else appears to be
  driving, check before writing to the tenant.

## What this skill does NOT do

Bulk refresh of the persistent 77-contact Address Book cast (the
date-rules CSV matched on IDentification). That is
maximizer-demo-data-generator's job. If a request needs both (fresh cast
AND a seeded story), do the CSV refresh first, then seed on top.
