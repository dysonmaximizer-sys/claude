# Competitive Intelligence System — Handoff Doc
**Last updated:** 2026-05-22
**Repo:** https://github.com/dysonmaximizer-sys/claude
**Project path:** `/Users/lewisdyson/Desktop/Claude Code/competitive_intel/`

---

## What this system does

Automated competitive intelligence pipeline that:
1. **Daily (06:00 UTC):** Polls changedetection.io for competitor page changes, logs to Notion, scores each change inline, sends a Teams alert for high-score items.
2. **Monthly (1st, 09:00 UTC):** Queries Notion for the previous month's changes, generates a newsletter via Claude, emails to recipients via Resend, posts an announcement card to Teams.

Runs on **GitHub Actions** (workflow YAMLs at the repo root in `.github/workflows/`). Local runs via `scheduler.py` (APScheduler) are an alternative if hosted on a VPS. Local CLI runs are for testing only.

---

## Architecture

```
jobs/
  daily_poll.py          # Daily: changedetection.io -> Notion -> score -> summarise -> alert
  monthly_newsletter.py  # Monthly: Notion -> newsletter -> email + Teams

agents/
  scoring_agent.py       # Scores each change 1-10 with reasoning
  summariser_agent.py    # Writes AI summary for high-score changes
  newsletter_agent.py    # Generates and emails the monthly newsletter

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

cd.io scan schedule: business days at 9am PST. The daily GitHub Actions poll runs at 06:00 UTC daily and uses a lookback window wide enough to catch all changes regardless of weekend gaps.

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

- Daily poll runs end-to-end: changedetection.io, Notion log, inline score, summarise (high-score only), Teams alert (high-score only).
- Teams alerts post as Adaptive Cards via the Workflows webhook (confirmed by smoke test on 2026-05-22).
- Teams newsletter announcement card posts correctly with accent styling (confirmed by smoke test on 2026-05-22).
- changedetection.io history correctly parsed (newest-first ordering fixed).
- Notion deduplication prevents double-logging.
- Email delivery via Resend (maximizer.com domain verified).
- Monthly newsletter: pulls real Notion data, generates via Claude, emails HTML version.
- HTML newsletter: proper H1/H2 headings, `<ul><li>` bullet points, no markdown artefacts (`**`, `*`, `---`).
- Newsletter prompt loaded from `resources/newsletter_system_prompt.txt` (edit there, not in code).

---

## What's not done yet

### Should verify
- **First scheduled GitHub Actions run on the new Teams webhook** has not yet been observed in production. The first daily poll firing real alerts via the new code path runs at 06:00 UTC on 2026-05-23. Check the Actions tab the morning after to confirm.
- **End-to-end monthly newsletter (Notion to email to Teams)** has not been re-run since the Teams migration. The Teams announcement card is confirmed (smoke test 2026-05-22), but the full job (`jobs/monthly_newsletter.py`) hasn't been exercised. Either pre-test manually with `python3 -m jobs.monthly_newsletter 2026 4` or wait for the real run on 2026-06-01 at 09:00 UTC.

### Also pending
- Expand `NEWSLETTER_RECIPIENTS` beyond Lewis when ready to go wider.
- Add the real sales team to the Competitive Intel Teams chat (currently has only test participants).

---

## How to run locally (testing only)

```bash
cd "/Users/lewisdyson/Desktop/Claude Code/competitive_intel"

# Run the daily poll manually
python3 -m jobs.daily_poll

# Run the newsletter for a specific month
python3 -m jobs.monthly_newsletter 2026 4

# Smoke-test the Teams alert webhook
python3 -m scripts.test_teams_alert

# Smoke-test the Teams newsletter announcement
python3 -m scripts.test_newsletter_announcement
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
