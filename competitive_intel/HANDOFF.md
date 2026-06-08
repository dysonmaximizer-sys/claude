# Competitive Intelligence System — Handoff Doc
**Last updated:** 2026-06-08
**Repo:** https://github.com/dysonmaximizer-sys/claude
**Project path:** `/Users/lewisdyson/Claude Code/competitive_intel/`

---

## What this system does

Automated competitive intelligence pipeline that:
1. **Daily (23:00 UTC):** Polls changedetection.io for competitor page changes, logs to Notion, scores each change inline, then groups high-score changes by underlying insight and sends one Teams alert per insight. 23:00 UTC lands at 16:00 PDT / 15:00 PST — inside business hours and after the cd.io crawl finishes.
2. **Monthly (1st, 09:00 UTC):** Queries Notion for the previous month's changes, generates a newsletter via Claude, emails a DRAFT to `DRAFT_REVIEWER` (Lewis) via Resend `/emails` for review.
3. **Monthly broadcast (manual):** Once the draft is approved, Lewis triggers the `Newsletter Broadcast (Manual)` GitHub Actions workflow with `confirm = "SEND"`. That re-generates the newsletter and POSTs it to the Resend Audience "CI Newsletter" via Resend `/broadcasts`. No Teams card.

Runs on **GitHub Actions** (workflow YAMLs at the repo root in `.github/workflows/`). Local runs via `scheduler.py` (APScheduler) are an alternative if hosted on a VPS. Local CLI runs are for testing only.

---

## Architecture

```
jobs/
  daily_poll.py          # Daily: changedetection.io -> Notion -> score -> summarise -> alert
  monthly_newsletter.py  # Monthly: Notion -> newsletter -> Resend (--mode draft|broadcast)

agents/
  scoring_agent.py       # Scores each change 1-10 with reasoning
  summariser_agent.py    # Writes AI summary for high-score changes
  newsletter_agent.py    # Generates the newsletter + send_draft_email() and send_broadcast()

integrations/
  changedetection_client.py  # Polls changedetection.io API, builds the diff
  notion_client.py           # All Notion reads/writes (Changes DB)
  teams_client.py            # Builds Adaptive Cards, posts via Teams Workflows webhook

resources/
  newsletter_system_prompt.txt  # Prompt loaded by newsletter_agent.py (edit here, not in code)

scripts/
  drop_battlecard_column.py    # One-shot: removed legacy 'Battlecard Updated' Notion column
  archive_battlecard_pages.py  # One-shot: archived 11 legacy battlecard pages in Notion
  archive_competitors_database.py  # One-shot: archives the defunct Competitors database
  test_teams_alert.py          # Smoke test: fires a sample alert card to Teams
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
| Monday      | Tier 2      | Yes                  |
| Zoho        | Tier 2      | Yes                  |
| Onevest     | Ankle Biter | Yes                  |
| Pipedrive   | Ankle Biter | Yes                  |
| Advora      | Ankle Biter | Yes                  |

cd.io scan schedule: business days at 9am PST, but the crawl spreads detections across ~09:00–15:00 Pacific (watches are scanned sequentially). The daily GitHub Actions poll runs at 23:00 UTC daily (16:00 PDT / 15:00 PST) — after the crawl completes and inside business hours — with a 25h lookback window wide enough to catch all changes regardless of weekend gaps.

To add a new competitor to changedetection.io: log into the cd.io dashboard, click "Add a new change detection", paste the URL, and set the **Title** to include the competitor slug (e.g. "salesforce pricing") so `_match_competitor()` picks it up.

---

## Teams integration

- Uses the Teams **Workflows** app (Power Automate flow created from the "Send webhook alerts to [chat]" template). Office 365 Connectors / classic MessageCard format is deprecated by Microsoft and no longer used.
- Destination: the **Competitive Intel** group chat in Teams. Flow posts as **Flow bot**.
- Payload: Adaptive Card 1.5 JSON in the POST body. The flow forwards it directly to Teams.
- The alert card uses container styling: `attention` (red) for score 8+, `warning` (yellow) for 6-7, default for below.
- Alert card includes one action button: "Open Source" (links to the cd.io-detected URL). The "View in Notion" button was removed because the link points to the broader Hub, not the specific change.
- Newsletter announcement card uses `accent` styling and includes a "Read Full Newsletter" button linking to the newsletter's Notion page.
- Webhook URL is stored in `.env` as `TEAMS_GENERAL_WEBHOOK` and in GitHub Actions secrets under the same name.
- Per-competitor webhooks (`TEAMS_WEBHOOK_EQUISOFT`, etc.) are supported by the code but not configured. All competitors route to the general webhook for now.

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
| `TEAMS_WEBHOOK_<COMPETITOR>` | Empty | Per-competitor overrides (optional, not currently used) |

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

## Status as of 2026-06-08

### Latest update — 2026-06-08: daily alert timing + duplicate-alert fix
Triggered by Saturday's alert batch: it fired at ~1:37am local (the 06:00 UTC poll, overnight in North America) and sent **4 separate cards for one event** — Wealthbox's "Custom Objects" launch, which surfaced on the homepage, pricing, blog, and webinars pages (4 separate cd.io watches, 4 distinct URLs). The per-URL dedup (`change_already_logged`) correctly treated them as 4 changes; it just has no concept of "one announcement across many pages."

- **Daily poll rescheduled `0 6 * * *` → `0 23 * * *`** in `.github/workflows/daily-poll.yml`. 23:00 UTC = 16:00 PDT / 15:00 PST. Chosen to run AFTER the cd.io crawl (detections spread ~09:00–15:00 Pacific) so each poll still captures that day's changes, while firing inside business hours. Not set to a 9am-equivalent slot on purpose — that would run mid-crawl and pick up half the day's changes a day late.
- **Insight de-dup added.** New `agents/dedup_agent.py` (`cluster_changes_by_insight`) makes one Claude call per competitor-with-multiple-alert-worthy-changes and clusters them by underlying announcement. `jobs/daily_poll.py` now defers all Teams alerts until after the log/score/summarise loop (new Step 5), groups alert-worthy changes by competitor, clusters by insight, and sends **one alert per cluster** (representative = highest score, then longest summary, then earliest).
  - **Alert appearance is unchanged** (Lewis's hard requirement): no digest card, no "Wealthbox digest" title. Each cluster fires a normal single-change card. The only change is that duplicate page-cards are suppressed.
  - **Suppressed pages stay in Notion** (logged, scored, summarised; `Teams Alert Sent` stays False) and still feed the monthly newsletter. Nothing is dropped.
  - **Safe fallback:** on any clustering failure (API error, malformed/non-partition response) the agent returns one cluster per change — i.e. today's one-alert-per-page behaviour. De-dup can never make things worse or merge incorrectly on error.
  - **Trade-off:** two *genuinely unrelated* high-score changes for the same competitor in one poll land in separate clusters → still two alerts. Only same-event pages collapse.
- **Validated against the real incident** (read-only dry run over Notion): the 4 Wealthbox pages clustered into 1 insight → 1 alert (representative `/blog/`, score 7). `py_compile` clean on both changed files.
- **Both changes are live on `main`** (this commit). The daily workflow runs from `main`, so the new schedule + dedup take effect on the next 23:00 UTC run.

### Earlier — 2026-06-01 (end of day): shipped, sent, and verified
- **Refactor committed and pushed to `main`** (commit `ae556f3`). The monthly cron and manual broadcast now run the new code.
- **Newsletter Draft workflow ran successfully in GitHub Actions** — first proof the CI secrets resolve server-side (the new Resend API key + `RESEND_AUDIENCE_ID`). Draft email delivered to the reviewer.
- **Real broadcast for May 2026 sent to the CI Newsletter audience.** `segment_id` was accepted, no 422 — the open issue below is RESOLVED.
- **Formatting bug found and fixed** in `_render_news_stories()`: the Competitive News section was rendering every body paragraph bold and shattering each story into fragments (the renderer split on blank lines, which also separate intra-story label blocks). Replaced with a label-driven parser. Headlines and the three labels are bold; bodies are plain.
- **Architecture changed to fully automatic (per Lewis's request).** The two-step draft→review→manual-broadcast flow is gone. `newsletter-draft.yml` was deleted. `newsletter-broadcast.yml` now runs on a monthly schedule and **auto-broadcasts to the CI Newsletter audience with no human review**. The manual `workflow_dispatch` trigger remains for ad-hoc re-sends and still requires `confirm=SEND`; scheduled runs skip that gate. There is no reviewer step anymore.
  - Trade-off Lewis accepted: a bad newsletter (formatting regression, hallucinated claim) now ships straight to `sales@`, `customersuccess@`, `pm@` with no eye-check.
- **Schedule set to `cron: 0 16 1 * *` (16:00 UTC).** GitHub cron ignores DST, so this lands at 09:00 Pacific during PDT (~Mar–Nov) and 08:00 Pacific during PST — biased early so it's never later than 9am. Lewis delegated this decision.
- **Resend API key: Lewis ADDED a new key (not rotated).** The old key stays valid, so `competitive_intel/.env` and `~/.zshrc` (release-automation system) need no update. No further sharing required.
- **Audience confirmed correct:** `sales@maximizer.com`, `customersuccess@maximizer.com`, `pm@maximizer.com` are the intended recipients.
- **Deleted local `competitive_intel/.env.bak`** (plaintext secrets backup). `.gitignore` already blocks `.env.bak` / `*.env.bak` so it can't be recreated and committed.
- **First fully-automatic run: 2026-07-01 at 16:00 UTC**, sending the June 2026 newsletter. The scheduled-trigger path (cron fires, SEND gate skipped) has not executed yet — first live exercise is that run.

### What just happened (earlier on 2026-06-01)
- **2026-06-01 09:00 UTC monthly newsletter email never arrived at lewisdyson@maximizer.com.** Root cause not yet confirmed.
- **A Teams "Monthly Strategic Synthesis" card DID post, but it was truncated and not useful.** Lewis wants it removed from the monthly path. Daily Teams alerts stay intact.
- **Critical bug discovered:** `jobs/monthly_newsletter.py` exits 0 on email send failure. A green GitHub Actions run is NOT proof of delivery. Email errors are caught, logged, and swallowed. This needs fixing alongside the refactor (exit 1 on send failure).

### Likely causes for missing 2026-06-01 email (priority order)
1. `SMTP_FROM` secret may default to `onboarding@resend.dev` (Resend sandbox — only delivers to account owner).
2. `NEWSLETTER_RECIPIENTS` secret may default to `marketing@maximizer.com` (Lewis not on it).
3. GitHub Actions cron delayed/skipped silently (best-effort, 10-60 min delays common).
4. M365 quarantine if sender domain isn't DKIM/SPF-verified in Resend.
5. Resend `RESEND_API_KEY` missing/rotated (job warns then exits 0).

### Decisions made and implemented this session
1. **Removed the monthly Teams summary card.** Daily Teams alerts stay intact.
2. **~~Two-step draft → broadcast flow.~~** SUPERSEDED 2026-06-01: replaced with a fully automatic monthly broadcast (no review step) at Lewis's request. See "Latest update" above. The draft workflow was deleted.
3. **Broadcast target = Resend Audience "CI Newsletter"** (Lewis confirmed it exists). Uses Resend Broadcasts API (`POST /broadcasts` with `send: true`), NOT `/emails`.
4. **One script with `--mode {draft,broadcast}` flag** + two GitHub Actions workflow YAMLs (cron-scheduled draft, manual broadcast with `confirm = "SEND"` text-input guardrail).
5. **Regenerate from Notion at broadcast time** rather than persist a draft between runs — prior-month Notion data is immutable so re-runs produce near-identical content; no new state to manage.
6. **`monthly_newsletter.py` now exits 1 on send failure** (deliberate change from prior behaviour) so GitHub Actions surfaces the failure instead of silently succeeding.

### What Lewis needed to verify before the test run (DONE — kept for reference)
These were verified during the 2026-06-01 test run; the draft CI run and broadcast both succeeded.
GitHub repo → Settings → Secrets and variables → Actions:
- `SMTP_FROM` = a `@maximizer.com` address on a Resend-verified domain (NOT `onboarding@resend.dev`)
- `RESEND_AUDIENCE_ID` = UUID of "CI Newsletter" audience (`082d3537-5ee3-4a6b-81c5-a732a738eae8`) — added.
- `DRAFT_REVIEWER` is optional (defaults to `lewisdyson@maximizer.com` in code if unset).
- Note: there is no `NEWSLETTER_RECIPIENTS` secret and the workflows don't need one.

Resend dashboard:
- Confirm account is on a Marketing plan that includes the Broadcasts API. Free tier availability is ambiguous. If transactional-only, broadcast path fails at runtime — upgrade or fall back to looping `/emails` over audience contacts.
- Confirm sender domain on `SMTP_FROM` is verified (DKIM/SPF green).
- Filter Emails → `to: lewisdyson@maximizer.com` 09:00-10:00 UTC 2026-06-01 to see if the cron fired at all and what Resend did with it.

### Implemented changes (all 7 file ops landed; `py_compile` passed)

| # | Path | Status |
|---|---|---|
| 1 | `competitive_intel/config.py` | Added `RESEND_AUDIENCE_ID` + `DRAFT_REVIEWER`. Kept `NEWSLETTER_RECIPIENTS` with migration-window comment (nothing in the codebase imports it now — safe to delete after first successful broadcast). |
| 2 | `competitive_intel/agents/newsletter_agent.py` | `email_newsletter()` replaced with `send_draft_email(html, subject, recipient)` (POST `/emails`) and `send_broadcast(html, subject, audience_id, internal_name)` (POST `/broadcasts` with `send: true`, auto-injects `{{{RESEND_UNSUBSCRIBE_URL}}}` footer if missing). Both use `logger.error` on every failure path. |
| 3 | `competitive_intel/jobs/monthly_newsletter.py` | Argparse `--mode {draft,broadcast}` + optional `--year` / `--month`. Defaults to previous month. Dispatches to the right send function. **Exits 1 on send failure** (deliberate). Teams card block + import removed. |
| 4 | `competitive_intel/integrations/teams_client.py` | `_build_newsletter_card()` and `send_newsletter_announcement()` deleted. Daily-flow functions kept. |
| 5 | `competitive_intel/scripts/test_newsletter_announcement.py` | Deleted (plus matching `__pycache__/.pyc`). |
| 6 | `.github/workflows/monthly-synthesis.yml` → `newsletter-draft.yml` | Renamed. Cron `0 9 1 * *` preserved. Runs `--mode draft`. `NEWSLETTER_RECIPIENTS` and `TEAMS_GENERAL_WEBHOOK` removed from this workflow's env. `DRAFT_REVIEWER` added. |
| 7 | `.github/workflows/newsletter-broadcast.yml` | Now runs on `cron: 0 16 1 * *` (auto-broadcast, no review) AND manual `workflow_dispatch` (requires `confirm = "SEND"`; scheduled runs skip the gate). Has `RESEND_AUDIENCE_ID` in env. `newsletter-draft.yml` was deleted. |

### ✅ RESOLVED: `segment_id` vs `audience_id`

The May 2026 broadcast went out with `segment_id` and Resend accepted it (HTTP 2xx, no 422). The field name in `send_broadcast()` is correct as-is. No change needed. (If a future Resend API change ever rejects `segment_id`, the fallback is `audience_id` — one-line swap in `send_broadcast()`.)

### Test sequence (do this in order)

1. **Verify Resend dashboard first** — confirm `to: lewisdyson@maximizer.com` for 2026-06-01 09:00 UTC. Tells you whether today's cron fired and what happened. Collapses the 5 candidate causes for the missing email down to 1.
2. **Verify / add GitHub secrets:**
   - `SMTP_FROM` = verified `@maximizer.com` address (NOT `onboarding@resend.dev`)
   - `RESEND_AUDIENCE_ID` = "CI Newsletter" audience UUID (NEW — required for broadcast)
   - `DRAFT_REVIEWER` = `lewisdyson@maximizer.com` (NEW — optional, defaults in code)
   - There is **no `NEWSLETTER_RECIPIENTS` GitHub secret** — the draft/broadcast workflows don't use it. Nothing to delete on GitHub. (`NEWSLETTER_RECIPIENTS` survives only as a fallback constant in `config.py`, unused by any code path.)
3. **Run draft locally for May:** `cd competitive_intel && python3 -m jobs.monthly_newsletter --mode draft --year 2026 --month 5`. Confirm the email arrives at Lewis's inbox.
4. **Trigger broadcast via GitHub Actions UI:** Actions tab → Newsletter Broadcast (Manual) → Run workflow → year=2026, month=5, confirm=SEND. Confirm audience receives it. If 422 on `segment_id`, fix per above and re-run.
5. **Wait for 2026-07-01 09:00 UTC cron** firing of `newsletter-draft.yml`. Confirm draft email arrives. Then manually trigger broadcast when ready.

### Resend Broadcasts API notes (for the refactor agent)
- Endpoint: `POST https://api.resend.com/broadcasts` with `Authorization: Bearer $RESEND_API_KEY`.
- Body: `{segment_id, from, subject, html, reply_to, name, send: true}`. The `send: true` flag collapses create-then-send into one call.
- Field name is `segment_id` (canonical). `audience_id` accepted as legacy alias.
- Look up audience by name: `GET /audiences`, iterate `data[]`, match `name == "CI Newsletter"`, extract `id`.
- HTML body MUST contain `{{{RESEND_UNSUBSCRIBE_URL}}}` merge tag (Gmail/Yahoo/M365 bulk-sender compliance). Resend does NOT auto-append. Triple braces required.
- Likely requires paid Marketing plan ($40/mo+). Free tier ambiguous.
- Sources: https://resend.com/docs/api-reference/broadcasts/create-broadcast, https://resend.com/changelog/create-and-send-broadcasts-via-api

### Still pending (post-refactor)
- The "CI Newsletter" Resend Audience currently holds **3 live internal addresses**: `sales@maximizer.com`, `customersuccess@maximizer.com`, `pm@maximizer.com`. (It is no longer test-only — the May 2026 broadcast went to these three.) Confirm these are the intended recipients and expand/trim as needed.
- Add the real sales team to the Competitive Intel Teams chat (currently test participants only).
- **`NEWSLETTER_RECIPIENTS` cleanup:** there is no GitHub secret to remove. Optionally delete the now-unused `NEWSLETTER_RECIPIENTS` constant from `config.py` — nothing imports it anymore.
- Decide whether `TEAMS_GENERAL_WEBHOOK` stays in repo-level secrets (daily flow still needs it) or moves to environment-scoped secrets for the daily workflow only.

### Path note
Repo root is `/Users/lewisdyson/Claude Code/` (no Desktop). The implementation agent flagged that earlier handoff/brief copies referenced `/Users/lewisdyson/Desktop/Claude Code/`. The "Desktop" prefix shows up in some bash sandbox views but the real git checkout is at `/Users/lewisdyson/Claude Code/`. Use that path going forward.

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
