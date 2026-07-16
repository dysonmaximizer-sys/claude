# Story: Busy Calendar (supporting scenery, all tours)

**Persona:** Adam. **Role:** not a tour of its own — the believable weekly
calendar behind every tour's calendar shots, especially Walk In Ready
step 2 (the moved-up 2:45 sits inside a real week, not an empty grid).

## What must be true in the data on recording day

1. The current business week (Mon-Fri) shows 3-4 entries per day: client
   reviews and calls linked to real cast members, plus unlinked working
   blocks (prep, compliance, dealer reconciliation, a referral lunch).
2. Early next week has a couple of entries so the calendar does not fall
   off a cliff after Friday.
3. The Sokolov annual review (2:45 PM today) comes from the walk-in-ready
   story, NOT from this one — never double-book it here.
4. Client-linked entries use persistent cast members whose story slots
   they reinforce (Jameson Thomas retirement planning, Marina's birthday
   call on her actual stored birthday week).

## Seeding

- `engine/seed-busy-calendar.py` — seeds ~16 appointments for the current
  week; manifest `manifests/busy-calendar-manifest.json`.
- Cleanup: `seed-busy-calendar.py --cleanup`.

## Refresh limitation (deliberate)

`refresh-story.py --story busy-calendar` shifts by calendar days, so a
non-multiple-of-7 refresh lands weekday entries on weekends. For a new
recording week, prefer cleanup + reseed (30 seconds) over a partial-week
refresh; or refresh in exact 7-day steps.
