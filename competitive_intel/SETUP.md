# Competitive Intelligence Agent — Setup Guide

## What This System Does

| Trigger | Action |
|---|---|
| Daily (06:00 UTC) | Polls changedetection.io for competitor page changes → logs to Notion → scores each change → fires Teams alerts on high scores |
| Monthly (1st, 09:00 UTC) | Generates Strategic Synthesis newsletter → emails + Teams |

---

## Prerequisites

- Python 3.12+
- A GitHub account (free tier is sufficient)
- A Notion account with an integration token
- A changedetection.io account (hosted plan) with API access
- An Anthropic API key
- A Resend account (or any provider with a verified sending domain)

---

## Step 1 — Notion Setup

**1a. Create a parent page**
- In Notion, create a new page called **Competitive Intelligence**
- Do NOT put it inside another page — top level is cleanest

**1b. Share with your integration**
- Open the page → **Share** (top right) → search for your integration by name → **Invite**
- If you haven't created an integration yet: [notion.so/my-integrations](https://www.notion.so/my-integrations) → New integration → copy the token

**1c. Get the page ID**
- Copy the page URL. It looks like: `https://notion.so/Competitive-Intelligence-<32-char-id>`
- The 32-character hex string at the end is your page ID
- Add it to `.env` as `NOTION_PARENT_PAGE_ID`

**1d. Run the setup script**
```bash
cd competitive_intel
pip install -r requirements.txt
python setup_notion.py
```
Copy the DB ID it prints and paste it into `.env`:
```
NOTION_CHANGES_DB_ID=...
```

---

## Step 2 — changedetection.io Setup

- Sign up for a hosted [changedetection.io](https://changedetection.io) account
- For each competitor, add the URLs you want monitored (pricing, product/features, homepage)
  - Suggested pages per competitor: `/pricing`, `/features` or `/product`, `/`
- For JS-rendered sites (HubSpot, Salesforce, Monday), switch the watch's "Fetch method" to use a Chrome-based browser. For everything else the default fast fetcher is fine.
- Copy your API key from **Settings → API** in the cd.io dashboard
- Find your account URL (e.g. `https://yourname.changedetection.io`) and copy it without a trailing slash
- Add both to `.env`:
  ```
  CHANGEDETECTION_API_KEY=...
  CHANGEDETECTION_BASE_URL=https://yourname.changedetection.io
  ```

**Naming your watches:** Set each watch's **Title** to include the competitor slug
(e.g. "hubspot - pricing", "equisoft - features") — the system uses the title
(case-insensitive) plus the URL to match changes to the right competitor.

---

## Step 3 — MS Teams Setup (when ready)

For each channel you want alerts in:
1. Open the channel in Teams → **…** → **Connectors** → **Incoming Webhook**
2. Name it "Competitive Intel" → **Create** → copy the webhook URL
3. Add to `.env`:
   - General channel: `TEAMS_GENERAL_WEBHOOK=https://...`
   - Per competitor (optional): `TEAMS_WEBHOOK_HUBSPOT=https://...` etc.

Until webhooks are added, alerts are silently skipped — Teams isn't notified.

---

## Step 4 — Email Setup (Resend)

1. Sign up at [resend.com](https://resend.com) and create an API key.
2. Verify your sending domain (e.g. `maximizer.com`) in **Resend → Domains**.
3. Add to `.env`:
   ```
   RESEND_API_KEY=re_...
   SMTP_FROM=competitive-intel@maximizer.com
   NEWSLETTER_RECIPIENTS=lewisdyson@maximizer.com
   ```
4. Expand `NEWSLETTER_RECIPIENTS` as a comma-separated list when you're ready to go wider.

---

## Step 5 — Deploy to GitHub Actions (recommended)

**5a. Create a GitHub repo**
```bash
cd "/Users/lewisdyson/Claude Code"
git init
git add .
git commit -m "Initial competitive intel system"
# Create repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/competitive-intel.git
git push -u origin main
```

**5b. Add secrets**
In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

Add each of these:
```
ANTHROPIC_API_KEY
NOTION_TOKEN
CHANGEDETECTION_API_KEY
CHANGEDETECTION_BASE_URL
NOTION_PARENT_PAGE_ID
NOTION_CHANGES_DB_ID
TEAMS_GENERAL_WEBHOOK          (add when ready)
TEAMS_WEBHOOK_EQUISOFT         (optional)
TEAMS_WEBHOOK_CLOVEN           (optional)
TEAMS_WEBHOOK_HUBSPOT          (optional)
TEAMS_WEBHOOK_LAYLAH           (optional)
TEAMS_WEBHOOK_SALESFORCE       (optional)
TEAMS_WEBHOOK_WEALTHBOX        (optional)
TEAMS_WEBHOOK_MONDAY           (optional)
TEAMS_WEBHOOK_ZOHO             (optional)
TEAMS_WEBHOOK_ONEVEST          (optional)
TEAMS_WEBHOOK_PIPEDRIVE        (optional)
TEAMS_WEBHOOK_ADVORA           (optional)
RESEND_API_KEY
SMTP_FROM
NEWSLETTER_RECIPIENTS
```

**5c. Add the workflows**

Create `.github/workflows/daily_poll.yml` and `.github/workflows/monthly_newsletter.yml` and commit them. See "Workflow YAML" at the bottom of this doc for the canonical contents.

**5d. Test manually**
Go to **Actions** tab → pick a workflow → **Run workflow**.

---

## Running Locally (optional)

```bash
cd competitive_intel
pip install -r requirements.txt

# Run a job manually
python -m jobs.daily_poll
python -m jobs.monthly_newsletter 2025 3   # specific month

# Run the scheduler (for VPS deployment)
python scheduler.py
```

---

## Phase 2 — Expanding the Knowledge Base

The Notion Changes database is already structured with a `Source Type` field
(Web / CRM / Staff Intel / Fathom) so Phase 2 intel feeds can plug straight in:

- **Staff Intel:** A simple Notion form or Slack bot that writes directly to the Changes DB
- **CRM Updates:** Export/webhook from your CRM → writes to Changes DB with `Source Type: CRM`
- **Fathom Transcripts:** Fathom webhook → extract competitor mentions → log to Changes DB

All intel then flows through the same scoring → alerting → newsletter pipeline.
