# Competitive Intelligence System — Handoff Doc
**Last updated:** 2026-05-15
**Repo:** https://github.com/dysonmaximizer-sys/claude
**Project path:** `/Users/lewisdyson/Desktop/Claude Code/competitive_intel/`

---

## What this system does

Automated competitive intelligence pipeline that:
1. **Daily (06:00 UTC):** Polls changedetection.io for competitor page changes → logs to Notion → scores each change inline → sends a Teams alert for high-score items
2. **Monthly (1st, 09:00 UTC):** Queries Notion for the previous month's changes → generates a newsletter via Claude → emails to recipients via Resend

Runs on **GitHub Actions** (intended). Local runs via `scheduler.py` (APScheduler) are an alternative if you'd rather host on a VPS. Local CLI runs are for testing only.

---

## Architecture

```
jobs/
  daily_poll.py          # Daily job: changedetection.io → Notion → score → summarise → alert
  monthly_newsletter.py  # Monthly job: Notion → newsletter → email + Teams

agents/
  scoring_agent.py       # Scores each change 1-10 with reasoning
  summariser_agent.py    # Writes AI summary for high-score changes
  newsletter_agent.py    # Generates and emails the monthly newsletter

integrations/
  changedetection_client.py  # Polls changedetection.io API, builds the diff
  notion_client.py       # All Notion reads/writes (Changes DB)
  teams_client.py        # Sends adaptive card alerts to MS Teams channels

resources/
  newsletter_system_prompt.txt  # Prompt loaded by newsletter_agent.py — edit here, not in code
```

Battlecards have been removed from scope. No code touches battlecard pages.

---

## Competitors tracked

| Competitor  | Tier        | changedetection.io monitored? |
|-------------|-------------|----------------------|
| Equisoft    | Tier 1      | Yes                  |
| Cloven      | Tier 1      | Yes                  |
| HubSpot     | Tier 1      | Yes                  |
| Laylah      | Tier 2      | No — needs adding    |
| Salesforce  | Tier 2      | No — needs adding    |
| Wealthbox   | Tier 2      | No — needs adding    |
| Monday      | Tier 2      | No — needs adding    |
| Zoho        | Tier 2      | No — needs adding    |
| Onevest     | Ankle Biter | No — needs adding    |
| Pipedrive   | Ankle Biter | No — needs adding    |
| Advora      | Ankle Biter | No — needs adding    |

To add a competitor to changedetection.io: log into changedetection.io → click "Add a new change detection" → paste the URL → set the **Title** to include the competitor slug (e.g. "salesforce pricing") so `_match_competitor()` picks it up.

---

## Environment variables

All set in `.env` (local) and GitHub Actions secrets (CI). Both must be kept in sync.

| Variable | Status | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Set | |
| `NOTION_TOKEN` | Set | |
| `CHANGEDETECTION_API_KEY` | Set | Found in cd.io dashboard → Settings → API |
| `CHANGEDETECTION_BASE_URL` | Set | e.g. `https://lewisdyson.changedetection.io` (no trailing slash) |
| `NOTION_PARENT_PAGE_ID` | Set | `34474af315fe809883bce99ab29a31ff` |
| `NOTION_CHANGES_DB_ID` | Set | `34474af3-15fe-8182-963e-ef6e0ba93594` |
| `RESEND_API_KEY` | Set | Domain `maximizer.com` verified in Resend |
| `SMTP_FROM` | Set | `competitive-intel@maximizer.com` |
| `NEWSLETTER_RECIPIENTS` | Set | `lewisdyson@maximizer.com` (expand when ready) |
| `TEAMS_GENERAL_WEBHOOK` | **Empty** | Needed for newsletter Teams announcement and daily high-score alerts |
| `TEAMS_WEBHOOK_EQUISOFT` | **Empty** | Per-competitor channel (optional) |
| `TEAMS_WEBHOOK_CLOVEN` | **Empty** | |
| All other TEAMS_WEBHOOK_* | **Empty** | One per competitor (optional) |

---

## What's working

- Daily poll runs end-to-end: changedetection.io → Notion log → inline score → summarise (high-score only) → Teams alert (high-score only)
- changedetection.io history correctly parsed (newest-first ordering fixed)
- Notion deduplication prevents double-logging
- Email delivery via Resend (maximizer.com domain verified)
- Monthly newsletter: pulls real Notion data, generates via Claude, emails HTML version
- HTML newsletter: proper H1/H2 headings, `<ul><li>` bullet points, no markdown artefacts (`**`, `*`, `---`)
- Newsletter prompt loaded from `resources/newsletter_system_prompt.txt` (edit there, not in code)

---

## What's not done yet

### Priority
1. **Confirm production runtime.** Repo says "runs on GitHub Actions" but `.github/workflows/` doesn't exist locally. Either commit workflow YAMLs (recommended) or run `scheduler.py` on a VPS. Until this is settled, nothing is firing on schedule.
2. **MS Teams webhook (at minimum the general one)** — create the channel in Teams, paste the webhook URL into `.env` and the GitHub Actions secret `TEAMS_GENERAL_WEBHOOK`. Until done, all Teams alerts are silently skipped.
3. **changedetection.io coverage** — add monitoring jobs for 8 competitors not yet tracked (see table above)

### Also pending
- Expand `NEWSLETTER_RECIPIENTS` beyond Lewis when ready to go wider
- Confirm all GitHub Actions secrets match current `.env` values

---

## How to run locally (testing only)

```bash
cd "/Users/lewisdyson/Desktop/Claude Code/competitive_intel"

# Run the daily poll manually
python3 -m jobs.daily_poll

# Run the newsletter for a specific month
python3 -m jobs.monthly_newsletter 2026 4
```

**Important:** Always use `python3 -m jobs.<name>` (module syntax) from the `competitive_intel/` directory, not `python3 jobs/daily_poll.py` — the latter breaks relative imports.

---

## Key technical notes

- `config.py` uses `load_dotenv(..., override=True)` — shell env vars are always overridden by `.env`
- `notion_client.py` loads dotenv at module level (before module-level vars are set) — important because it captures `NOTION_TOKEN` at import time
- changedetection.io history array is **newest-first** (index 0 = most recent). The client diffs `history[i]` against `history[i+1]`.
- Alert threshold is set in `config.py` as `ALERT_SCORE_THRESHOLD` — only changes scoring above this get summarised and alerted
- Newsletter system prompt is loaded from `resources/newsletter_system_prompt.txt` at agent startup. Editing that file is all that's needed to change newsletter structure or tone — no code changes required.
- The Changes Notion DB may still contain a `Battlecard Updated` checkbox property from earlier setups. It is no longer written or read by any code. Delete the property in Notion if you want a clean schema.
