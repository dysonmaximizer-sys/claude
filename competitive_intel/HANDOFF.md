# Competitive Intelligence System — Handoff Doc
**Last updated:** 2026-09-24
**Repo:** https://github.com/dysonmaximizer-sys/claude
**Project path:** `/Users/lewisdyson/Claude Code/competitive_intel/`

---

## What this system does

Automated competitive intelligence pipeline that:
1. **Business days (15:00 UTC):** Polls changedetection.io for competitor page changes, logs to Notion, scores each change inline, then groups high-score changes by underlying insight and sends one Teams alert per insight. 15:00 UTC lands at 08:00 Pacific (PDT) / 07:00 (PST) — a weekday morning alert, no weekend sends. Because 08:00 is before the day's cd.io crawl, each morning's alert covers the PRIOR day's detections. Lookback is 76h to bridge the weekend (Friday's crawl is alerted Monday).
2. **Monthly (first business day, 16:00 UTC):** Queries Notion for the previous month's changes, generates a newsletter via Claude, and auto-broadcasts it to the Resend Audience "CI Newsletter" via Resend `/broadcasts` — no draft/review step (removed 2026-06-01). The cron fires on the 1st–3rd; a business-day gate in `newsletter-broadcast.yml` lets only the first business day on/after the 1st send (the 1st if it's a weekday, otherwise the following Monday). No Teams card.
3. **Manual re-send (ad hoc):** Lewis can trigger the broadcast workflow via `workflow_dispatch` with `confirm = "SEND"` (the business-day gate does not apply to manual runs).

Runs on **GitHub Actions** (workflow YAMLs at the repo root in `.github/workflows/`). Local runs via `scheduler.py` (APScheduler) are an alternative if hosted on a VPS. Local CLI runs are for testing only.

---

## Architecture

```
jobs/
  daily_poll.py          # Daily: preflight -> rescue sweep -> changedetection.io -> Notion -> score -> summarise -> alert
  healthcheck.py         # Daily: shouts in Teams if the pipeline has stopped working
  rescore.py             # Shared engine: scores rows stuck at Status = Unscored
  backfill_rescore.py    # One-off: drains the whole Unscored backlog (uses rescore.py)
  monthly_newsletter.py  # Monthly: Notion -> newsletter -> Resend (--mode draft|broadcast)

agents/
  scoring_agent.py       # Scores each change 1-10 with reasoning
  summariser_agent.py    # Writes AI summary for high-score changes
  newsletter_agent.py    # Generates the newsletter + send_draft_email() and send_broadcast()
  dedup_agent.py         # Groups one competitor's alert-worthy changes by insight
  awareness_agent.py     # Keeps Maximizer-party news (joint webinars, partner integrations) out of Teams

integrations/
  changedetection_client.py  # Polls changedetection.io API, builds the diff
  notion_client.py           # All Notion reads/writes (Changes DB)
  teams_client.py            # Builds Adaptive Cards, posts via Teams Workflows webhook
  anthropic_preflight.py     # 1-token key check; jobs abort before any fetch or write if it fails
  anthropic_retry.py         # backoff on 429/5xx/connection errors; never retries a 400

resources/
  newsletter_system_prompt.txt  # Prompt loaded by newsletter_agent.py (edit here, not in code)

scripts/
  drop_battlecard_column.py    # One-shot: removed legacy 'Battlecard Updated' Notion column
  archive_battlecard_pages.py  # One-shot: archived 11 legacy battlecard pages in Notion
  archive_competitors_database.py  # One-shot: archives the defunct Competitors database
  test_teams_alert.py          # Smoke test: fires a sample alert card to Teams
  check_api_key.py             # Standalone: is the Anthropic key funded? (auth vs billing)
  sync_notion_competitor_options.py  # Adds missing Competitor select options to Notion
  test_dedupe_recovery.py      # Offline regression test: dedupe fix, clustering, Maximizer-party filter
  add_suppression_properties.py  # One-shot: added Teams Suppressed + Suppression Reason to Notion (applied 2026-09-24)
```

Battlecards have been removed from scope. The 11 legacy battlecard pages and the `Battlecard Updated` Notion column have been archived. No code touches battlecard pages.

---

## Competitors tracked

| Competitor  | Tier        | changedetection.io monitored? |
|-------------|-------------|----------------------|
| Equisoft    | Tier 1      | Yes                  |
| Cloven      | Tier 1      | Yes                  |
| HubSpot     | Tier 1      | Yes                  |
| Laylah      | Tier 2      | Yes                  |
| Salesforce  | Tier 2      | Yes                  |
| Wealthbox   | Tier 2      | Yes                  |
| Zoho        | Tier 2      | Yes                  |
| Redtail     | Tier 2      | Yes (added 2026-08-18) |
| AdvisorEngine | Tier 2    | Yes (added 2026-08-18) |
| Microsoft Dynamics | Tier 2 | Yes (added 2026-08-18) |
| Act!        | Tier 2      | Yes (added 2026-08-18) |
| Focal AI    | Frenemies   | **No — watch not created yet** |
| Continuum   | Frenemies   | **No — watch not created yet** |
| Zocks       | Frenemies   | **No — watch not created yet** |
| Fireflies   | Frenemies   | **No — watch not created yet** |
| Onevest     | Ankle Biter | Yes                  |
| Pipedrive   | Ankle Biter | Yes                  |
| Advora      | Ankle Biter | Yes                  |

Monday was removed from the registry on 2026-08-31: it had been listed as Tier 2 since April with **no changedetection.io watch**, so it produced zero rows in the entire history of the database. The Notion `Competitor` select still carries the option (removing a select option would strip the value from any page that used it; keeping it costs nothing).

Valid tier values: `Tier 1`, `Tier 2`, `Ankle Biter`, and `Frenemies` (added 2026-08-31; assigned to Focal AI, Continuum, Zocks and Fireflies — AI meeting-notes and client-intelligence assistants that integrate with CRMs while absorbing workflows a CRM would otherwise own). The scoring prompt now explains the tier vocabulary (added 2026-08-31), so the label does steer scoring: Tier 1 carries the most weight, Frenemies less than Tier 1 but not dismissed — there is substantial product-feature and ICP overlap — and Ankle Biters need a genuinely consequential change to reach the upper bands. The glossary also states that tier adjusts weight but never overrides the rubric, so cosmetic changes stay 1-2 regardless of source.

cd.io scan schedule: business days at 9am PST, but the crawl spreads detections across ~09:00–15:00 Pacific (watches are scanned sequentially). The GitHub Actions poll runs business days at 15:00 UTC (08:00 PDT / 07:00 PST) — a weekday morning alert that runs before that day's crawl, so it reports the prior day's detections. The lookback is **76h** so Monday's run reaches back across the weekend to catch Friday's crawl (~72h); Friday's changes are alerted Monday 08:00. Re-fetched changes already **scored** in Notion are skipped by `find_existing_change()`; a re-fetched change whose row is still `Unscored` is re-scored in place instead of being skipped (see the 2026-08-18 entry).

To add a new competitor: (1) add the watch in the cd.io dashboard; (2) add an entry to `COMPETITORS` in `config.py` with `url_patterns` (host + optional path) — that is the precise match and does not depend on how the watch is titled; (3) run `python3 -m scripts.sync_notion_competitor_options --apply` so the Notion **Competitor** select has the option. Setting the watch **Title** to include the slug still works as a fallback for the original 11 competitors, but `url_patterns` is the reliable route. A watch matching nothing is skipped with a WARNING naming the URL — grep the run log for "no competitor match" to catch a missing registry entry.

---

## Teams integration

- Uses the Teams **Workflows** app (Power Automate flow created from the "Send webhook alerts to [chat]" template). Office 365 Connectors / classic MessageCard format is deprecated by Microsoft and no longer used.
- Destination: the **Competitive Intel** group chat in Teams. Flow posts as **Flow bot**.
- Payload: Adaptive Card 1.5 JSON in the POST body. The flow forwards it directly to Teams.
- The alert card uses container styling: `attention` (red) for score 8+, `warning` (yellow) for 6-7, default for below.
- Alert card includes one action button: "Open Source" (links to the cd.io-detected URL). The "View in Notion" button was removed because the link points to the broader Hub, not the specific change.
- The monthly newsletter path posts **nothing** to Teams. The announcement card was removed from `jobs/monthly_newsletter.py`; distribution is email via Resend only. (This line previously described the card as live — corrected 2026-08-31.)
- Webhook URL is stored in `.env` as `TEAMS_GENERAL_WEBHOOK` and in GitHub Actions secrets under the same name.
- Per-competitor webhook routing was removed on 2026-08-18. All 11 per-competitor secrets were null, so every alert already went to the general webhook; the code, workflow YAML and docs now match that reality. Every alert goes to `TEAMS_GENERAL_WEBHOOK` with the competitor name as the card headline.

---

## Environment variables

All set in `.env` (local) and GitHub Actions secrets (CI). Both must be kept in sync.

| Variable | Status | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Set | |
| `NOTION_TOKEN` | Set | |
| `CHANGEDETECTION_API_KEY` | Set | Found in cd.io dashboard, Settings, API |
| `CHANGEDETECTION_BASE_URL` | Set | e.g. `https://lewisdyson.changedetection.io` (no trailing slash) |
| `NOTION_PARENT_PAGE_ID` | Set | `34474af315fe809883bce99ab29a31ff` |
| `NOTION_CHANGES_DB_ID` | Set | `34474af3-15fe-8182-963e-ef6e0ba93594` |
| `RESEND_API_KEY` | Set | Domain `maximizer.com` verified in Resend |
| `SMTP_FROM` | Set | `competitive-intel@maximizer.com` |
| `NEWSLETTER_RECIPIENTS` | Set | `lewisdyson@maximizer.com` (expand when ready) |
| `TEAMS_GENERAL_WEBHOOK` | Set | Points at the Competitive Intel chat via Power Automate flow |

---

## What's working

- Daily poll runs end-to-end: changedetection.io, Notion log, inline score, summarise (high-score only), insight de-dup, Teams alert (one card per distinct insight).
- Teams alerts post as Adaptive Cards via the Workflows webhook (confirmed by smoke test on 2026-05-22).
- Teams newsletter announcement card posts correctly with accent styling (confirmed by smoke test on 2026-05-22).
- changedetection.io history correctly parsed (newest-first ordering fixed).
- Notion deduplication prevents double-logging.
- Email delivery via Resend (maximizer.com domain verified).
- Monthly newsletter: pulls real Notion data, generates via Claude, emails HTML version.
- HTML newsletter: proper H1/H2 headings, `<ul><li>` bullet points, no markdown artefacts (`**`, `*`, `---`).
- Newsletter prompt loaded from `resources/newsletter_system_prompt.txt` (edit there, not in code).

---

## Status as of 2026-09-24

### Where this stands right now

**Everything from the August-September rebuild is merged. No open PRs.** Thirteen PRs, #1 to #13. (#6 merged into the wrong base and was re-landed as #7.)

**Three weeks of clean unattended operation, 2026-09-02 to 09-24:**

| | |
|---|---|
| Daily polls | **17/17 succeeded** |
| Health checks | **23/23 succeeded**, all five checks green |
| Unscored backlog | **0** |
| Rows scored | 412, none failed |
| Alert-worthy (6+) | 53 = **13%** |
| cd.io watches | 89, all matching a competitor |
| Registry | 18 competitors: 3 Tier 1, 8 Tier 2, 4 Frenemies, 3 Ankle Biter |
| Cost | ~$2-3/month |

**The Frenemies tier is earning its place.** 94 rows in three weeks (Zocks 35, Fireflies 30, Focal AI 18, Continuum 11), and they produced the highest-scoring intel of the period: **Continuum shipped a live direct Maximizer integration (8/10)** and Zocks became a launch partner for Claude for Financial Advisors (7/10). None of that was visible before 2026-08-31.

**The Sonnet 5 alert-suppression worry did not materialise.** The pre-swap sample predicted roughly half of alerts falling below threshold; the actual September rate is **13% against a 7% August baseline**. Confounded by the new frenemy watches, which are high-signal, so do not read it as proof the model scores identically. The practical conclusion: **`ALERT_SCORE_THRESHOLD` does not need lowering to 4.** Leave it at 5.

**The autonomous broadcast has not actually run yet.** The 2026-09-01 scheduled run crashed (ThinkingBlock), August went out manually the same day, and the 09-02 and 09-03 runs were correctly skipped by the business-day gate, not by the idempotency guard. **2026-10-01 (a Thursday) is the first genuinely unattended broadcast**, and the first live exercise of the duplicate guard in CI.

**Decisions made this session** (with what was rejected, so they are not relitigated):

- **Backlog is scored silently.** `RESCUE_SWEEP_ALERTS = False`; backfill takes `--alerts` as opt-in. Rejected: alerting on backlog, because two-week-old news buries fresh signal. It reaches the team via the monthly newsletter.
- **`Frenemies` is a fourth `Tier` value.** Rejected: a separate `Relationship` property that would have allowed "Tier 1 frenemy". Lewis chose the simpler overload knowing those four lose a threat ranking.
- **Model switched to `claude-sonnet-5`, with the tradeoff on the record.** Measured: 12% cheaper, but 6 of 33 sampled rows dropped below the alert threshold. Lewis chose it after seeing that. **Outcome (2026-09-24): the suppression did not happen.** September ran at 13% alert-worthy against a 7% August baseline, so `ALERT_SCORE_THRESHOLD` stays at 5. If volume ever does thin, that threshold is still the lever, not reverting the model.
- **Redtail, AdvisorEngine, Microsoft Dynamics, Act! are all Tier 2.** Rejected: Redtail as Tier 1.
- **One Teams webhook for everything.** Per-competitor routing deleted entirely; all 11 secrets were null.
- **Rejected: Batch API.** 50% off scoring, but up to 24h alert delay and submit/poll complexity for ~$0.60/month.
- **Broadcasts send without human review** (Lewis, 2026-09-01). The `confirm=SEND` prompt was never a content review. It only ever gated accidental duplicate manual sends. Replaced by a Resend-backed duplicate guard rather than removed outright. Rejected: marking the month's rows `Status = Distributed` in Notion, which would mean up to 400 writes per broadcast to restate what Resend already knows.
- **Monday dropped from the registry** (2026-08-31). Tier 2 since April with no watch and 0 rows ever. The Notion `Competitor` select keeps the option, because deleting a select option strips the value from any page that used it.
- **Maximizer-party news is kept out of Teams but kept in the newsletter** (2026-09-24). Filter is separate from scoring and fails open. Rejected: a plain "mentions Maximizer" keyword filter, which would also mute comparison pages and switch offers, the highest-value alerts. Also rejected: a curated partner list, which goes stale and would suppress a partner turning hostile.
- **Declined: measuring the tier glossary's effect on scoring** (A/B on 33 rows, ~10c). Asked and declined 2026-08-31, so two scoring changes (Sonnet 5 and the glossary) landed unmeasured within a day of each other. If scores look off, that is where to look first.

**Who receives the broadcast** (verified against Resend 2026-09-24): the `CI Newsletter` audience `082d3537-5ee3-4a6b-81c5-a732a738eae8` holds exactly three subscribed addresses, `sales@maximizer.com`, `customersuccess@maximizer.com`, `pm@maximizer.com`. These are internal aliases, not individuals. Every unattended broadcast goes to them.

**Open items and blockers:**

- **Nothing is blocked.** The pipeline runs unattended and green.
- **Confirm the newsletter audience is the intended distribution.** It is three internal aliases (above) and has not been reviewed since the May 2026 test. Broadcasts are now unattended, so nobody checks the recipient list at send time.
- **The Competitive Intel Teams chat may still hold test participants only.** Flagged 2026-06-01 and never confirmed; the real sales team was to be added. Not checkable from the API, needs a look in Teams.
- **`NEWSLETTER_RECIPIENTS` is dead code** in `config.py`. No GitHub secret exists for it and nothing imports it. Safe to delete.
- **Undecided since 2026-06-01:** whether `TEAMS_GENERAL_WEBHOOK` stays a repo-level secret (the daily flow needs it) or moves to environment-scoped secrets for that workflow only.
- **2 noise watches remain** in cd.io, both deliberately kept: `developers.hubspot.com/changelog` (9 rows, never above 2/10, more likely a bad CSS selector than a worthless source, so check the selector before deleting) and `advisorengine.com/newsroom` (4 rows, too few to judge). Six others were dropped 2026-08-31, removing ~20% of scoring calls.
- **Prompt caching still inert.** The scoring system prompt is 806 tokens against a 1,024-token minimum on Sonnet 5, proven by 66 live calls returning `cache_read_input_tokens: 0`. Crossing 1,024 with genuinely useful content (a "what cosmetic noise looks like" section) would make the prefix cacheable at 0.1x across each run's ~25 back-to-back calls. Worth roughly $1/month, more than every other cost lever combined, and it should sharpen scoring on the ~67% of rows that are cosmetic.
- **`requirements.txt` allows `anthropic>=0.40.0`.** CI installed 1.3.0 while this Mac runs 0.96.0. Pinning needs a local upgrade first.
- **Nothing logs `response.usage`**, so spend is measured by `count_tokens` arithmetic rather than observed.
- **GitHub disables scheduled workflows after 60 days of repository inactivity.** Any commit resets the clock.

**Next steps, in order:**

0. **Merge the Maximizer-party filter PR** (branch `ci-maximizer-party-filter`). It is inert until it reaches `main`.
1. **Watch the 2026-10-01 broadcast.** First unattended send, first CI exercise of the duplicate guard. If it fails, the `if: failure()` Teams card fires and the health check flags it from the 4th.
2. Consider pushing the scoring prompt past 1,024 tokens (see caching above). Largest remaining cost lever and a quality improvement.
3. Check the `developers.hubspot.com/changelog` watch selector, then keep or drop it.
4. Optional: raise `get_monthly_changes(min_score=...)` from 1 to 3 so the newsletter generator stops receiving the ~67% of rows that are cosmetic. Largest single input-token cost in the system.

Related Cowork handoffs, for the frenemy context: `/Users/lewisdyson/PMM/Cowork/focal-partnership-handoff-2026-08-21.md` and `/Users/lewisdyson/PMM/Cowork/continuum-integration-handoff-2026-08-11.md`.


### Latest update — 2026-09-24 (later): Maximizer-party filter on Teams alerts

Feedback: intel where Maximizer is itself a party (a joint webinar, a partner's Maximizer integration) is noise in the Teams chat because we already know. It is still logged, scored and summarised, and it stays in the newsletter (Lewis, 2026-09-24). Only the Teams card is dropped.

**How it works** (`agents/awareness_agent.py`, called per insight cluster in `daily_poll.py` after summarising, and in `rescore.py` only when alerting is on):
1. **Keyword gate.** Only clusters whose URL or diff contains "Maximizer" go further. Every other insight costs nothing extra.
2. **Separate classifier call** returns `PARTY` or `ALERT`. PARTY means integrations with Maximizer (even when only the partner announces them), joint webinars, co-marketing, partner listings, and joint customer stories. ALERT means comparisons, switch or migration offers, an integration removed or paywalled, claims about Maximizer, Maximizer mentioned only in passing, **or a Maximizer integration bundled with other real news** (e.g. new integrations with other CRMs as well). In that last case the other news still earns the alert.
3. **Fails open.** An API error, unparseable output or uncertainty all send the alert.
4. **Auditable.** Suppressed rows get `Teams Suppressed` ticked and a `Suppression Reason` in Notion (properties added live 2026-09-24). `Teams Alert Sent` stays unticked. The run summary logs a `suppressed` count.

**Not touched:** the significance score and the scoring prompt. Rejected: adding a field to the scoring call, because that changes the scoring prompt, and two scoring changes have already landed unmeasured.

**Bug caught during the live eval:** the classifier first read only the first 1,500 characters of each diff. On LinkedIn pages the Maximizer post sits below follower counts and employee lists, so it judged the noise. It now reads the opening lines plus a window around every Maximizer mention (`_excerpt`).

**Evidence:** 9/9 synthetic cases correct (switch offers, comparison pages, a removed integration, a paywalled integration and bundled news all alert; webinars, integration launches and customer stories are suppressed). Against the only 3 alert-worthy historical rows that mention Maximizer (all Continuum LinkedIn), 2 are suppressed, including the 8/10 "live direct Maximizer integration". The third alerts. Its diff is truncated in Notion, where the classifier only sees follower-count noise. The full diff at poll time would likely be judged differently. Offline regression suite extended with scenarios 6-8.

**Known limits:**
- An integration a partner builds **without** Maximizer's knowledge is treated as PARTY and suppressed, by design (per the feedback). If that ever matters, the fix is a known-partners allowlist gating the integration case, not loosening the prompt.
- Maximizer-mentioning rows are rare (5 in the whole database), so expect this to fire a few times a month at most. If `Teams Suppressed` never ticks, the likelier cause is that nothing qualified, not that the filter is broken.
- A Maximizer mention that appears only in an image or logo is invisible to the gate, so that change alerts. That is the safe direction.

### Earlier — 2026-09-01 (later): unattended broadcasts, guarded

Lewis authorised sending the monthly newsletter broadcast **without human review** from now on (recorded in Claude's memory). Two things had to change for that to be safe, because the `confirm=SEND` prompt was never a content review — it was the only thing preventing a duplicate send.

- **Duplicate guard.** `--mode broadcast` now asks Resend whether a broadcast named `CI Newsletter YYYY-MM` already exists, and refuses if it does, unless `--force` is passed. Resend is the source of truth — it is the system that actually sent. Rejected: flipping the month's rows to `Status = Distributed`, which would mean up to 400 Notion writes per broadcast to restate something Resend already knows. The check runs **before** generation, so a refusal costs 0.4s rather than 50 seconds and a wasted generation.
- **Fifth health check.** `check_newsletter()` verifies last month's broadcast reached Resend. Nothing watched this before: a failed broadcast surfaced only as an `if: failure()` Teams card, so a missed card meant a silent month. Quiet until the 4th. Needs `RESEND_API_KEY`, now passed in `healthcheck.yml`.

`agents.newsletter_agent.broadcast_name()` is the single source of that name string — the send, the guard and the health check all use it, and if they ever disagreed the guard would stop guarding and the health check would cry wolf monthly.

Verified live: with `CI Newsletter 2026-08` already sent, a real `run(mode="broadcast")` refused in 0.4s having called neither the generator nor the sender. `scripts/test_broadcast_guard.py` covers the rest offline, including the January → December year-boundary rollback.

### Earlier — 2026-09-01: Sonnet 5's adaptive thinking broke response parsing

The August newsletter failed at 19:09 UTC with `'ThinkingBlock' object has no attribute 'text'`. The API call returned **200 OK**; the crash was ours.

All four agents read `message.content[0].text`, which assumes the first content block is text. **Sonnet 5 runs adaptive thinking by default and Sonnet 4.6 did not**, so the model now decides per request whether to think — and when it does, `content[0]` is a ThinkingBlock. Verified live: a short scoring call returns `['text']`, a long synthesis call returns `['thinking', 'text']`. That is why scoring kept working while the newsletter died: one latent bug, hidden by workload shape, for a full day.

Fixes:
- `integrations/anthropic_retry.response_text()` concatenates every text block and ignores the rest. It also raises explicitly on `stop_reason == "max_tokens"` and on a response with no text, because both otherwise surface as confusing downstream failures (bad JSON, or an empty summary silently written to Notion).
- Scoring, summariser and dedup now pass `thinking={"type": "disabled"}`. Their budgets are 256-300 tokens and adaptive thinking spends the *same* budget, so a thinking burst would truncate the JSON. Sonnet 4.6 never thought on these calls, and the comparison that justified the model swap was measured with thinking effectively off, so this keeps behaviour aligned with what was validated.
- The newsletter keeps adaptive thinking (long-form synthesis is where it earns its keep) with `max_tokens` raised 1500 → 4000 so reasoning cannot crowd out the newsletter itself.
- `scripts/test_response_parsing.py` covers all six response shapes offline.

**Unresolved risk:** `requirements.txt` pins `anthropic>=0.40.0`, so CI installed **anthropic 1.3.0** while this Mac runs **0.96.0** — a silent major-version divergence between CI and local. Not the cause of this failure, but "works in CI, breaks locally" (or the reverse) is waiting to happen. Pinning needs a local upgrade first.

### Earlier — 2026-08-31 (later): credit-usage assessment, Sonnet 5, cluster-first summarising, Frenemies tier

**Measured cost profile** (via `count_tokens` plus real `response.usage` from 66 live calls; 7 run-days, 179 scored rows):

| | per call | calls/month |
|---|---|---|
| Scoring | 740 in / 61 out | 563 |
| Summarising | 645 in / 110 out | 41 |
| Clustering | ~1,100 in / ~120 out | 24 |

**~469k input + 42k output tokens/month, about $1.85.** Score distribution: 77% scored 1-2, 16% scored 3-5, 7% scored 6+. So the August credit outage was **not** a consumption problem — at under $2/month a small prepaid balance simply ran out. Auto-reload and the preflight are the fixes, not token efficiency.

**Model switched to `claude-sonnet-5`.** Measured on 33 real rows, both models, identical prompts: $1.85 → $1.62/month (12%). Not the 33% the sticker prices imply ($2/$10 vs $3/$15) — Sonnet 5's newer tokenizer turns the same text into ~1.39× more tokens, eating most of the rate cut. It also scores ~0.5 points harsher near the alert boundary: 7 of the 33 rows crossed the >5 line, 6 downward (Wealthbox integrations 6→4, wealthbox.com 6→4, pricing 6→5, webinars 6→5, Redtail support 6→5; Redtail corporate 4→6 the other way). **If alert volume drops noticeably, adjust `ALERT_SCORE_THRESHOLD` rather than reverting the model.** All four agents switch, the monthly newsletter included, so newsletter tone may shift.

**Summarising is now per insight, not per row.** Clustering used to run *after* summarising and then discard the duplicates, so one announcement across four of a competitor's pages bought four summaries and used one. Clustering now runs on the scoring agent's one-line reasoning — cleaner input than a raw diff — and only the cluster representative is summarised. Suppressed rows keep score and reasoning but get no AI Summary; `newsletter_agent` already falls back to Raw Change for those, and the insight itself is summarised on the representative row.

**The scoring prompt gained a tier glossary**, which is what makes the tier label do anything. Cost of that: the scoring system prompt went 324 → 806 tokens, **+$0.54/month** — more than the Sonnet 5 swap saved. Net position is roughly $2.16/month, up from $1.85 before the optimisation work. Worth knowing, and see the caching note below: at 806 tokens the prompt is now only ~218 tokens short of the 1,024-token cache minimum, and crossing that line would make the prefix cacheable and save roughly $1/month — more than every other lever combined.

**Frenemies** is a fourth valid tier value, present in the Notion Tier select, and now carries Focal AI (`meetwithfocal.com`), Continuum (`oncontinuum.com`), Zocks (`zocks.io`) and Fireflies (`fireflies.ai`) — domains verified against each vendor's own site on 2026-08-31. **Their changedetection.io watches do not exist yet**, so the registry entries are inert until someone creates them. `scripts/sync_notion_competitor_options.py` now syncs Tier as well as Competitor, so a tier in `config.py` that Notion doesn't know can't cause a rejected write and a dropped change.

**Known and measured, NOT yet fixed:**
- **Prompt caching has never worked.** System prompts measure 324 (scoring), 169 (summariser), 205 (dedup) tokens against a 1,024-token minimum on Sonnet 4.6 and Sonnet 5 (512 even on Opus 5). Proven empirically: 66 live calls returned `cache_read_input_tokens: 0` and `cache_creation_input_tokens: 0`. The `cache_control` markers and their "cache system prompt across batch" comments are inert.
- **8 watches have never scored above 2/10** across 860 rows since 2026-07-01 and account for **22% of all scoring calls**: three YouTube channels (Equisoft, Wealthbox, Laylah), `ir.hubspot.com`, `x.com/Equisoft`, `zoho.com/blog/crm`, `developers.hubspot.com/changelog`, `advisorengine.com/newsroom`. Deleting the first six in cd.io is the only lever that cuts cost *and* raises signal density. The HubSpot changelog scoring ≤2 nine times looks more like a bad CSS selector than a worthless source.
- **12% of scored rows are digit-only diffs** (stock ticks, follower counts) that a deterministic pre-filter could skip with no API call and no quality risk.
- **Nothing logs `response.usage`**, so cache hits and real spend can only be estimated, never observed.

### Earlier — 2026-08-31: alert noise killed, transient failures retried

**What went wrong.** On 2026-08-28 the poll ran well — 37 matched changes, 27 logged, 26 scored — and then one row (Zoho pricing) hit a transient Anthropic **HTTP 500**. That single failure out of 27 exited the job 1, so the run went red and fired a "daily poll FAILED" card. Worse, every health check run after it reported "the last daily poll run ended in failure", exited 1 by design, and that non-zero exit tripped the `if: failure()` step, which posted **"HEALTH CHECK CRASHED"**. The check had not crashed; it was working perfectly. Two alarming cards a day, one of them false, for a fault that lasted one request. Nothing could clear it until a poll succeeded, and the poll is weekday-only, so it ran all weekend.

**Three fixes.**

1. **Health check exit codes are now load-bearing.** `0` healthy, `2` problems found *and* reported to Teams, `1` crashed or could not deliver. The workflow maps `2` to success with a warning annotation, so the crash card only fires when the watchdog genuinely has no voice. Before, "reported problems" and "died" were both exit 1 and indistinguishable to `if: failure()`.
2. **Transient Anthropic errors are retried** (`integrations/anthropic_retry.py`): 4 attempts, exponential backoff, on 429/5xx/connection/timeout. A 400 `invalid_request_error` — the credit-balance failure — is **never** retried, since it is a standing condition and retrying hides the diagnosis. Applied to all four agents. And the daily poll no longer fails over a small number of scoring blips: a failed row stays Unscored and the next run's rescue sweep re-scores it, so it is self-healing. A run is called systemic only if failures exceed `SCORING_FAILURE_TOLERANCE` (3) **or** more than half the attempts failed. A real outage still surfaces within a day via the health check's backlog test.
3. **`learn.microsoft.com/dynamics365` added** to the Microsoft Dynamics patterns. A Dynamics release-notes watch on that host was being discarded every run ("no competitor match" in the 2026-08-28 log) because the existing patterns only covered `microsoft.com/dynamics-365` and the LinkedIn showcase.

**Verified:** retry predicate against 6 exception types including a real 400 and a real 500; retry recovering on the third attempt with 2s/4s backoff and raising immediately on a 400; all three health check exit codes; the workflow's shell mapping for exit 0/1/2/3; and the regression suite extended to 17 checks with a new scenario covering one blip (tolerated, row left for the sweep) versus 8 of 10 failing (fails the run).

**Aug 20-28 for the record:** six successful polls, backlog held at 0, and all four new competitors scoring in production.

### Earlier — 2026-08-18 (later): failsafe monitoring + backlog alerting policy

**Backlog is now scored silently.** `RESCUE_SWEEP_ALERTS = False` in `config.py`, and `jobs/backfill_rescore.py` takes `--alerts` as opt-in rather than `--no-alerts` as opt-out. Rationale: a backlog row is days or weeks old by the time it is scored, so alerting on it notifies people about stale news and buries the fresh signal. Backlog reaches the team through the monthly newsletter. Only changes detected in the current run alert.

**The pipeline now reports its own failure** (`jobs/healthcheck.py` + `.github/workflows/healthcheck.yml`, daily at 16:00 UTC). Four checks, silent when healthy, Teams card the moment any fails:

| Check | Fires when |
|---|---|
| Anthropic key | the key cannot run billed inference — the exact August failure, caught *before* it breaks a run |
| Scoring backlog | more than 5 rows have been Unscored for over a day, i.e. scoring is failing even if runs look green |
| Detection freshness | nothing detected for 4 days — cd.io stopped crawling, or its key expired |
| Newsletter | last month's broadcast never reached Resend (quiet until the 4th, since the cron fires on the 1st-3rd) |
| Workflow runs | the last daily poll failed, or none has run for 3 days (disabled schedule) |

Both scheduled workflows also gained an `if: failure()` step that posts to Teams with a link to the run log, and the health check has one for itself, since a watchdog that dies silently is no better than the thing it watches.

**Known gap:** GitHub disables scheduled workflows after 60 days of repository inactivity. If nobody commits for two months, both the poll and its watchdog stop, and no alert fires because nothing runs. Any commit resets that clock.

### Earlier — 2026-08-18: credit-outage fallout fixed (preflight, dedupe, backfill, 4 new competitors)

**What broke.** Scoring failed mid-run on 2026-08-04 (14 rows scored, then 5 unscored the same day) and on every run after it, with `400 invalid_request_error: credit balance too low`. Because the poll wrote each row to Notion *before* scoring it, and dedupe only asked "is this URL already in Notion?", every row written before a failure was treated as a duplicate forever and could never be scored. Result: **183 rows stranded at Status = Unscored between 2026-08-03 and 2026-08-18** (Wealthbox 41, Equisoft 34, Zoho 33, HubSpot 21, Salesforce 17, Cloven 15, Laylah 13, Pipedrive 9).

**Billing diagnosis.** `scripts/check_api_key.py` splits the check in two: `GET /v1/models` (unbilled) and `POST /v1/messages` (billed, 1 token). On 2026-08-18 stage 1 returned **200** and stage 2 returned **400 credit balance too low** for org `992ef0c4-0504-45dd-92dc-21b5173499f2`. The key is valid and live — this is a billing scope problem, not a bad key. An Anthropic key belongs to one workspace inside one org, and credit/spend limits are per workspace, so credits topped up on a different org or a $0 workspace spend limit produce exactly this split. **Still unresolved as of 2026-08-18** — the backfill cannot run until it is.

**Fixes.**
- **Preflight** (`integrations/anthropic_preflight.py`): both scoring jobs make one 1-token call before anything is fetched or written, and exit non-zero on failure. `--dry-run` downgrades it to a warning (a dry run makes no billed calls).
- **Status-aware dedupe** (`notion_client.find_existing_change()`, replaces `change_already_logged()`): Scored/Distributed → skip; Unscored → re-score that row in place, never create a duplicate.
- **Rescue sweep** (`jobs/rescore.py`, called at the top of every daily poll, `RESCUE_SWEEP_LIMIT` = 20 rows): dedupe alone is not enough, because a row stranded on day 1 of an outage falls outside the 76h lookback by day 4 and is never re-fetched. The sweep reads the database instead of the poll feed, so nothing stays stuck regardless of age.
- **Backfill** (`jobs/backfill_rescore.py`): unbounded pass over the Unscored backlog. Idempotent, rate-limited, aborts on an Anthropic API error rather than burning the backlog, and batches alert-worthy rows into Teams **digest** cards (a two-week backlog would otherwise fire dozens of individual cards). Alert threshold is unchanged: score > `ALERT_SCORE_THRESHOLD`.
- **Teams routing flattened**: per-competitor webhooks removed entirely (all 11 secrets were null). Competitor name is now the card headline.
- **4 competitors added**: Redtail, AdvisorEngine, Microsoft Dynamics, Act! — all Tier 2. Their cd.io watches already existed but `_match_competitor()` silently discarded them every run. Matching is now `url_patterns` → `title_patterns` → legacy slug substring, in that order. Slug matching is OFF for these four: "act" as a substring matches contact, interact, practifi.
- **Empty-diff rows drain**: a row with no Raw Change is scored 1 and flipped to Scored rather than left Unscored, so a sweep can't retry it forever.

**Verification done offline** (`python3 -m scripts.test_dedupe_recovery`, 13 checks, all passing): a run whose scoring breaks part-way leaves rows Unscored; the next healthy run scores all of them with **no duplicate rows**; and a row stranded 5 days ago — outside the lookback entirely — is still rescued and alerted.

### Earlier — 2026-08-04 (later): "RECOMMENDED ACTION" removed from Teams alerts
Follow-on to the newsletter change below, same rationale.
- **Summariser prompt no longer produces it:** `agents/summariser_agent.py` SYSTEM_PROMPT now asks for WHAT and WHY IT MATTERS only. Summaries written to Notion (`AI Summary`) going forward have two sections, not three. Historical Notion summaries keep their RECOMMENDED ACTION lines (not migrated — they only feed the newsletter as input context, and the newsletter prompt no longer asks for response guidance).
- **Defensive strip in the card builder:** `_build_alert_card()` in `integrations/teams_client.py` drops any `RECOMMENDED ACTION:` line from the summary before rendering, so a stray emission can never reach the chat. Verified with a functional card test (label + body stripped, WHAT/WHY intact); `py_compile` clean.
- Takes effect on the next daily poll run after this lands on `main`.

### Earlier — 2026-08-04: newsletter moved to business days; "How we should respond" removed
Two changes, effective from the September 2026 cycle onward.
- **Broadcast cron `0 16 1 * *` → `0 16 1-3 * *`** in `.github/workflows/newsletter-broadcast.yml`, plus a new "Business-day gate" step. Scheduled runs on the 2nd/3rd (and a weekend 1st) exit early with `send=false`; only the first business day on/after the 1st broadcasts — the 1st if it's a weekday, otherwise the following Monday. Verified by simulation across all seven weekday cases: exactly one send per month, never two. Skipped runs show green in Actions with all steps after the gate skipped. Manual `workflow_dispatch` runs bypass the gate (still require `confirm=SEND`). A run on the 2nd/3rd still defaults to the previous calendar month, so content is unaffected.
- **"How we should respond" removed from the newsletter.** Deleted from `resources/newsletter_system_prompt.txt` (both the content instruction and the required formatting label). Stories now carry only "What happened:" and "Why it matters:". Defensively, `_render_news_stories()` in `agents/newsletter_agent.py` keeps the label in its parse regex but drops the part at render time, so a stray emission can't be misparsed as a story headline. Verified with a functional test (label + body dropped, adjacent stories intact); `py_compile` clean.
- **`scheduler.py` (unused VPS path) not updated** — its monthly trigger was already stale (day=1, 09:00 UTC) and now also lacks the business-day logic. Fix only if the VPS path is ever used.

### Earlier history (2026-06-01 to 2026-07-22)

Archived to [`HANDOFF_HISTORY.md`](HANDOFF_HISTORY.md) on 2026-09-24 to keep this doc readable. It covers the original build and launch: the first broadcast, the `segment_id` investigation, the poll moving to business days and to 08:00 Pacific, the duplicate-alert fix, and the July Resend key rotation. Nothing in it is an open item. Everything still live was promoted into the sections above before archiving.

---

## How to run locally (testing only)

```bash
cd "/Users/lewisdyson/Claude Code/competitive_intel"

# Run the daily poll manually
python3 -m jobs.daily_poll

# Run the newsletter as a DRAFT (emails Lewis only)
python3 -m jobs.monthly_newsletter --mode draft --year 2026 --month 5

# Run the newsletter as a BROADCAST (sends to Resend Audience "CI Newsletter")
python3 -m jobs.monthly_newsletter --mode broadcast --year 2026 --month 5

# Smoke-test the Teams alert webhook (daily flow only)
python3 -m scripts.test_teams_alert

# Is the Anthropic key funded? (prints request id + org id + verbatim error)
python3 -m scripts.check_api_key

# Daily poll without writing anything (preflight + fetch + report)
python3 -m jobs.daily_poll --dry-run

# Drain the Unscored backlog: inspect, then a small live test, then all of it
# (scores silently by default; add --alerts to send Teams digests)
python3 -m jobs.backfill_rescore --dry-run
python3 -m jobs.backfill_rescore --yes --limit 5
python3 -m jobs.backfill_rescore --yes

# Check whether the pipeline is healthy (silent unless something is wrong)
# exit 0 = healthy, 2 = problems reported to Teams, 1 = crashed or undelivered
python3 -m jobs.healthcheck
python3 -m jobs.healthcheck --always-notify   # force a card, for testing

# Offline regression test for the dedupe-poisoning fix (no API keys needed)
python3 -m scripts.test_dedupe_recovery

# Add missing Competitor select options to the Notion Changes DB
python3 -m scripts.sync_notion_competitor_options --apply
```

**Important:** Always use `python3 -m jobs.<name>` (module syntax) from the `competitive_intel/` directory, not `python3 jobs/daily_poll.py`. The latter breaks relative imports.

---

## Key technical notes

- `config.py` uses `load_dotenv(..., override=True)`. Shell env vars are always overridden by `.env`.
- `notion_client.py` loads dotenv at module level (before module-level vars are set), important because it captures `NOTION_TOKEN` at import time.
- changedetection.io history array is **newest-first** (index 0 = most recent). The client diffs `history[i]` against `history[i+1]`.
- Alert threshold is set in `config.py` as `ALERT_SCORE_THRESHOLD`. Only changes scoring above this get summarised and alerted.
- Newsletter system prompt is loaded from `resources/newsletter_system_prompt.txt` at agent startup. Editing that file is all that's needed to change newsletter structure or tone, no code changes required.
- Teams webhook is the Power Automate Workflows flow, not a classic Office 365 Connector. The flow validates incoming JSON as Adaptive Card 1.5 and rejects anything else with 400 `InvalidBotAdaptiveCard`. Don't go back to MessageCard.
- The Notion Changes DB schema matches the code. The legacy `Battlecard Updated` column was removed via `scripts/drop_battlecard_column.py`. The 11 legacy battlecard pages and the defunct `Competitors` database were archived via `scripts/archive_battlecard_pages.py` and `scripts/archive_competitors_database.py`.
- `scripts/` holds one-shot maintenance scripts. They are not part of the scheduled pipeline.
- **Secret stores are separate copies that must stay in sync.** `RESEND_API_KEY` (and every other secret) exists both in local `competitive_intel/.env` (used only by local/manual runs) and in GitHub Actions secrets (used by the scheduled CI). Rotating a key means updating **both**; updating only one leaves the other stale.
- **GitHub retargets a stacked PR only when its base branch is DELETED.** Merging #5 (the lower PR) without deleting its branch left #6 pointing at that branch, so #6 merged into the branch and never reached `main`. Fixed by cherry-picking onto `main` as #7. When stacking: delete the base branch on merge, or retarget the upper PR first.
- **The PAT gained `workflow` scope on 2026-08-18.** Before that, pushes and Contents-API writes touching `.github/workflows/` failed — and the API returns **404**, not 403, which reads as "missing file" rather than "missing scope". Editing workflow YAML in the GitHub web editor is error-prone (pasted blocks inherit the editor's auto-indent; it took three attempts). Push the file instead.
- **The Teams webhook `sig` parameter IS the credential**, and `requests` puts the full URL into its `HTTPError` text — so any `logger.error("...: %s", e)` published it. Use `teams_client.redact()` on anything derived from a failed post.
- **Notion select options must exist before a write.** Do not rely on auto-creation; `scripts/sync_notion_competitor_options.py --apply` syncs both Competitor and Tier from `config.py`.
- **The repo is at `/Users/lewisdyson/Claude Code/`, not `~/Desktop/Claude Code/`.** The Desktop path appears in some sandbox views and in older briefs, but the real git checkout is the home-folder one. Sessions get launched with the Desktop path as the working directory, so check before assuming.
- **Resend broadcast field is `segment_id`** (canonical); `audience_id` is a legacy alias. If a future API change rejects `segment_id`, the fallback is a one-line swap in `send_broadcast()`. The HTML body must carry the `{{{RESEND_UNSUBSCRIBE_URL}}}` merge tag for bulk-sender compliance; `send_broadcast()` auto-injects it when absent.
- **Sonnet 5 runs adaptive thinking by default; Sonnet 4.6 did not.** Never read `message.content[0].text` — use `anthropic_retry.response_text()`. Thinking tokens are drawn from the same `max_tokens` budget, so a small budget plus thinking equals a truncated response.
- **Sonnet 5's tokenizer produces ~1.39x more tokens than Sonnet 4.6 for the same text** (measured: 24,000 → 33,240 on 33 identical prompts). Never estimate a model-swap saving from sticker prices alone.
- **Minimum cacheable prefix: 1,024 tokens on Sonnet 4.6 and Sonnet 5** (512 on Opus 5). The scoring prompt is 806 tokens, so its `cache_control` marker is inert — proven by 66 live calls returning `cache_read_input_tokens: 0`.
- **Power Automate reveals a flow's webhook URL only after the flow is saved**, and a flow cannot be saved with only a trigger. Deleting a flow makes every post return `400 WorkflowTriggerIsNotEnabled` with `state: 'Deleted'` — that error means the URL points at a deleted flow, not a malformed card.
- **cd.io timed out from Lewis's Mac on 2026-08-18 and was reachable again on 2026-08-31.** A connect timeout there is transient/network, not a bad API key — GitHub runners reached it throughout.
- **`Date Detected` always lags about a day** (the poll runs before that day's crawl), so a run's own output never carries today's date. A `Created time` property was added to the Changes DB on 2026-08-31 — sort on that to see what the latest run brought in.
- **Local python is 3.9** (no 3.11/3.12 on the Mac, no Homebrew); repo code stays 3.9-compatible while CI runs 3.12.
- **Lewis's Mac (Apple Silicon / arm64) has neither Homebrew nor the `gh` CLI installed** (checked 2026-07-22). Setting a GitHub Actions secret from Terminal therefore requires installing Homebrew → `brew install gh` → `gh auth login` first. The zero-install path is the GitHub web UI: repo → Settings → Secrets and variables → Actions. GitHub never displays a secret value; the "Updated" timestamp is the only confirmation it took.
