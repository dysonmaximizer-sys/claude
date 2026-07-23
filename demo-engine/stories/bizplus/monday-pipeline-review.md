# Story: Monday Pipeline Review (Business+ tenant, first story)

**Persona:** Michelle Boone, VP Sales (Lewis's pick, 2026-07-22) reviewing
the TEAM pipeline. Reps: Amanda Brown, Douglas Ceron, Jane Smith, David
Canter. **Aha:** the review finds what the pipeline view surfaces - the
hot deal to protect, the slipped close date, and the three deals nobody
has touched in a month.

## The 12 deals (all Status open, owners per rule 10)

| Deal | $ | Owner | Review moment |
|---|---|---|---|
| Walley World - Fleet equipment order | 85K | Michelle | HOT: closes Friday, verbal yes, task today |
| Cyberdyne Systems - Service renewal | 60K | Douglas | SLIPPED: close date last week, still open |
| Magna Gases - Cylinder tracking pilot | 24K | Jane | STALE: quiet 5 weeks |
| Rhodes Furniture - Showroom POS | 18K | David | STALE: quiet 4 weeks |
| Bell Markets - Store expansion fit-out | 32K | Amanda | STALE: quiet 6 weeks |
| Webcom - Managed IT services | 45K | Amanda | active, call 3d ago |
| Delta Bike - Wholesale program | 28K | Jane | active |
| Gart Sports - Team equipment | 52K | Douglas | active, proposal revised 2d ago |
| Quality Merchant Services - Payments | 38K | Michelle | active |
| Konsili - Discovery | 15K | David | early |
| Excella - Pilot order | 12K | Jane | early |
| Alpha Beta - Office refit supply | 21K | Amanda | mid (repurposed probe record) |

Texture: 8 calls (owners' voices), 5 notes, 5 tasks due this week
assigned across the team. The three stale deals are quiet ON PURPOSE.

## Manual before capture (~5 min)

1. **Assign stages in the UI** (deals are created stage-less; stages are
   per-deal instances here): Walley World -> Negotiation/late; Cyberdyne,
   Gart, Webcom, Quality Merchant, Alpha Beta, Delta Bike -> mid;
   Magna, Rhodes, Bell -> mid-early; Konsili, Excella -> first stage.
2. **The zombie pipeline:** 61 sample opportunities from 2022-2023 are
   still open in this tenant. Filter the capture view to close dates in
   2026 (or current quarter), OR ask Claude for a bulk hygiene pass
   (mark the old ones lost/abandoned - permanent, so decide once).

## Cleanup caveat (unusual - read before reseeding)

Opportunity DELETE is Access-Denied for this PAT. Cleanup = rename +
mark Status 4, not deletion, until Lewis grants Opportunity-delete to
the API user in this tenant's Administrator. The seeder refuses to run
if the manifest exists. Calls/notes/tasks delete normally.

## Refresh

`set -a; source bizplus.env; set +a` then
`python3 demo-engine/engine/refresh-story.py --story bizplus/monday-pipeline-review`
rolls calls/notes/tasks. Opportunity CloseDates do NOT roll (not in the
refresh script's field map yet) - flag when this story is next used.
