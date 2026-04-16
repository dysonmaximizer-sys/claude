# Competitive Intelligence Agent — Setup Guide

## What This System Does

| Trigger | Action |
|---|---|
| Daily (06:00 UTC) | Polls Visualping for competitor page changes → logs to Notion |
| Monthly (1st, 08:00 UTC) | AI scores every change 1–10, summarises high scores, fires Teams alerts, updates battlecards |
| Monthly (1st, 09:00 UTC) | Generates Strategic Synthesis newsletter → emails + Teams |

---

## Prerequisites

- Python 3.12+
- A GitHub account (free tier is sufficient)
- A Notion account with an integration token
- A Visualping account with API access
- An Anthropic API key

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
Copy the two DB IDs it prints and paste them into `.env`:
```
NOTION_COMPETITORS_DB_ID=...
NOTION_CHANGES_DB_ID=...
```

---

## Step 2 — Visualping Setup

- Log in to your Visualping account
- Add monitoring for each competitor's key pages (pricing, product/features, homepage)
  - Suggested pages per competitor: `/pricing`, `/features` or `/product`, `/`
- Copy your API key from Account Settings → API
- Add it to `.env` as `VISUALPING_API_KEY`

**Naming your checks:** Name each check to include the competitor name
(e.g. "HubSpot Pricing", "Equisoft Features") — the system uses the check name
to match changes to the right competitor.

---

## Step 3 — MS Teams Setup (when ready)

For each channel you want alerts in:
1. Open the channel in Teams → **…** → **Connectors** → **Incoming Webhook**
2. Name it "Competitive Intel" → **Create** → copy the webhook URL
3. Add to `.env`:
   - General channel: `TEAMS_GENERAL_WEBHOOK=https://...`
   - Per competitor: `TEAMS_WEBHOOK_HUBSPOT=https://...` etc.

Until webhooks are added, alerts are logged locally and not dropped — they'll
send as soon as you add the URLs.

---

## Step 4 — Email Setup (newsletter)

Use a Gmail app password or SendGrid:

**Gmail:**
1. Enable 2FA on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create an app password → copy it
4. Add to `.env`: `SMTP_USER=you@gmail.com`, `SMTP_PASSWORD=<app-password>`

**SendGrid:** Change `SMTP_HOST=smtp.sendgrid.net`, `SMTP_PORT=587`,
`SMTP_USER=apikey`, `SMTP_PASSWORD=<sendgrid-api-key>`

---

## Step 5 — Deploy to GitHub Actions (recommended)

**5a. Create a GitHub repo**
```bash
cd "/Users/lewisdyson/Desktop/Claude Code"
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
VISUALPING_API_KEY
NOTION_PARENT_PAGE_ID
NOTION_COMPETITORS_DB_ID
NOTION_CHANGES_DB_ID
TEAMS_GENERAL_WEBHOOK          (add when ready)
TEAMS_WEBHOOK_EQUISOFT         (add when ready)
TEAMS_WEBHOOK_CLOVEN           (add when ready)
TEAMS_WEBHOOK_HUBSPOT          (add when ready)
TEAMS_WEBHOOK_LAYLAH           (add when ready)
TEAMS_WEBHOOK_SALESFORCE       (add when ready)
TEAMS_WEBHOOK_WEALTHBOX        (add when ready)
TEAMS_WEBHOOK_MONDAY           (add when ready)
TEAMS_WEBHOOK_ZOHO             (add when ready)
TEAMS_WEBHOOK_ONEVEST          (add when ready)
TEAMS_WEBHOOK_PIPEDRIVE        (add when ready)
TEAMS_WEBHOOK_ADVORA           (add when ready)
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
NEWSLETTER_RECIPIENTS
```

**5c. Test manually**
Go to **Actions** tab → **Daily Competitive Poll** → **Run workflow**

---

## Step 6 — Fill in the Battlecards

After setup_notion.py runs, each competitor has a skeleton battlecard page in Notion.
Use the Equisoft template in `resources/Equisoft Battlecard.docx` as a reference
to fill in each competitor's:
- Overview paragraph
- Feature comparison table
- Why We Win bullets
- Talk Tracks

The system will keep the **Recent Intel** section current automatically.

---

## Running Locally (optional)

```bash
cd competitive_intel
pip install -r requirements.txt

# Run a job manually
python -m jobs.daily_poll
python -m jobs.monthly_score
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
