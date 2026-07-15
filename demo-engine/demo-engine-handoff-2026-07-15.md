# Maximizer Demo Engine — Handoff
Updated: 2026-07-15 · Session: Cowork

## Context
Internal tool ("Demo Engine") that generates and refreshes demo data in
Maximizer's demo tenant so sales demos, Demo Centre recordings, and
enablement sandboxes never need manual data prep. Owner: Lewis (PMM).
Sponsor context: Meena (Lewis's manager) confirmed automated demo creation
is a recurring need (meeting 2026-07-07). Everything lives in this repo
under `demo-engine/` — read `demo-engine/CLAUDE.md` FIRST; it contains the
hard rules and all validated tenant knowledge. First story (Sokolov
household, "Walk In Ready" Demo Centre hero tour) is seeded in the tenant
and ~95% complete.

## Decisions
- **API-first, by key** — all record creation/updates via Octopus API.
  Rejected: CSV import wizard for opportunities/notes/activities, because
  live testing showed it creates orphan Individual entries and fails on
  re-import ("AbEntry object not found"). CSV remains only for bulk cast
  refreshes matched on IDentification.
- **Interface = this repo + Claude Code** — Lewis requests stories
  conversationally; Claude Code writes/runs seeders. Rejected: terminal
  scripts as the ongoing UX (Lewis is a non-developer).
- **Manifest per story** (`manifests/`, gitignored) so cleanup is exact and
  double-seeding is blocked. Manifest for the seeded story is currently at
  `~/Desktop/walk-in-ready-manifest.json` — moving it into `manifests/` is
  a next step.
- **June "open RESP question" is a phone call + note, not an email** —
  tenant blocks fabricating email interactions (see gotchas).
- **Sokolov household kept in tenant** (not cleaned up) — it's the Phase 1
  dogfood data for the Walk In Ready Storylane capture.
- **Phased rollout agreed with Lewis:** P1 engine core (Lewis only) → P2
  nightly refresh + story library → P3 enablement (Mark) → P4 sales
  self-serve (gated on demand) → P5 recording-analysis loop.

## Open items & blockers
- GitHub push blocked: stored credential for github.com expired
  (remote: dysonmaximizer-sys/claude, https). Two local commits waiting.
  Lewis must mint a new GitHub token/credential; Claude cannot handle it.
- Lewis UI-verified 2026-07-15: story looks right. Two issues he found
  (Marina's blank Date Last Contacted; times displaying non-Pacific) were
  BOTH FIXED same day — see CLAUDE.md for the tz rule (7b) and the
  LastContactDate finding. All 6 record times shifted +7h and verified;
  audit notes swept.
- Marina's birthday UDF was set via API — visually confirm it shows in UI.
- "Account up since April" (tour step 4) is dealer-feed data, NOT
  fabricable via CRM API — needs product conversation before Storylane
  capture, or the capture avoids that panel.
- Wizard-test orphan Individuals (fake Jameson Thomas, poss. Lou Cameron /
  Bill Graham) may still need deleting from the tenant — verify.
- `.env` not yet created at repo root; nothing committed yet this session.

## Next steps (in order)
~~1-3 DONE 2026-07-15 (later session):~~ RESP task created & verified
(key VGFzawk0Nzg=, due +7d, in manifest); manifest moved to `manifests/`
and both scripts updated (Desktop copy is a stale spare — delete after
UI check); `.env` created at repo root with PAT, confirmed gitignored.
Commit/push still pending Lewis's go-ahead.
4. Have Lewis eyeball Sokolov household vs `stories/walk-in-ready.md`
   checklist, then record the Storylane capture.
5. Build the refresh script (roll dates on manifest records + sweep audit
   notes) — this is the Phase 2 core.
6. Draft Meena one-pager from `docs/` + validation results (Lewis will ask).

## Tool knowledge & gotchas
- All Octopus API knowledge is in `demo-engine/CLAUDE.md` — tenant field
  requirements, working payload shapes, blocked operations. Do not re-test
  what's recorded there.
- Birthdate UDF: `Udf/$TYPEID(124)`. Task shape: Activity + DateTime.
  Emails/appointments/tasks CANNOT be created as InteractionLog types.
- Maximizer auto-logs field changes as notes stamped "now" — refresh runs
  must sweep them (rule 5 in CLAUDE.md).
- Sokolov story keys are in `~/Desktop/walk-in-ready-manifest.json` — 10
  records incl. household `Q29tcGFueQkyNjA3MTUyNTIxNDAwMTE5MDAwMDNDCTA=`.
  Household displays correctly as Household despite Company-style key.
- Lewis's Mac runs Python 3.9 (verified: the only interpreter installed):
  `Optional[str]`, never `str | None`. urllib3 LibreSSL warning is noise —
  ignore. (The cpython-310 files in `engine/__pycache__/` came from the
  Cowork sandbox, not this Mac — don't let them mislead you.)
- Repo lives at `~/Claude Code/demo-engine` — NOT `~/Desktop/Claude Code`,
  which is a different folder with no demo-engine in it.
- PAT is demo-tenant only, lives in `.env`, never in chat or commits.

## Session preferences
- Lewis wants step-by-step, zero-knowledge instructions for anything
  terminal- or UI-related, and wants failures pasted back verbatim.
- Report script results in plain language; keep code invisible unless asked.
