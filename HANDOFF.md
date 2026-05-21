# Maximizer Release Automation — Session Handoff
_Last updated: May 15, 2026_

---

## What was completed this session

### April 2026 Release — DONE ✅
All three assets were generated and published:
- **Zendesk article** — drafted, formatted, published
  - URL: https://support.maximizer.com/hc/en-us/articles/45408748107533-Maximizer-Cloud-April-2026
  - Article ID: `45408748107533`
- **Customer email** — built from template, sent via Resend Broadcasts API
  - Subject: "Coming Soon: Insurance Suite, Workflow Automation, and AI Features – April 2026"
  - From: `marketing@maximizer.com`
  - Audience: Release Notes (Resend)
- **Screenshot injection** — pipeline built but not used this cycle (Zendesk attachments had generic names like "Image", "Image (1)" — no matches). Will be used in May.

### Monthly Schedule — CONFIGURED ✅
A remote CCR routine fires on the **17th of each month at 9am PDT (17:00 UTC)**.
- Routine ID: `trig_01P56uM8PPcbTkVteKxkX6q2`
- Manage at: https://claude.ai/code/routines/trig_01P56uM8PPcbTkVteKxkX6q2
- **Next run: May 17, 2026**
- What it does: creates `output/YYYY-MM-release/`, scaffolds `release_payload.json`, writes `RELEASE_BRIEFING.md`

### Email Notification on Completion — PARTIALLY CONFIGURED ⚠️
Option A (Resend email notification) was chosen but requires the Resend API key to be embedded in the routine prompt. **This is not yet done** — see "Pending Tasks" below.

---

## Pending Tasks

### 1. Add email notification to the monthly routine
The routine currently runs silently. To get a completion email to `lewisdyson@maximizer.com`:
- You need your `RESEND_API_KEY` value
- I will update the routine prompt to add a final `curl` step that sends a summary email via Resend
- To action: open a new Claude Code session and say: _"Update the Maximizer release routine to send a completion email via Resend. Here is my API key: [key]"_

### 2. GitHub App installation
The remote routine clones `dysonmaximizer-sys/claude` to read the workflow file. If the GitHub App isn't installed, the routine will fail silently.
- Install at: https://claude.ai/code/onboarding?magic=github-app-setup
- Check if it's installed before May 17

### 3. Screenshot naming convention — brief PMs before May cycle
For the screenshot injection pipeline to work in May:
- PMs must name Zendesk attachment files to match the feature name exactly
- E.g., `Insurance Suite Overview`, `Workflow Automation`, `AI Timeline Summaries`
- Generic names like `Image` or `Screenshot (1)` will not match and will be silently skipped
- Brief the PM team before they start uploading screenshots to the May Zendesk draft

### 4. Zendesk in-app notification
Maximizer is on the Professional plan — Zendesk Announcements is not available on this tier. Options:
- Upgrade to Enterprise
- Use an alternative in-app channel (to be decided)
- This was deferred from the April cycle

### 5. Feature Type column in Loop (recommended PM workflow improvement)
Adding a "Feature Type" column to the Loop release table would let the agent distinguish major features from minor improvements automatically, without needing to ask. Raise with the PM team.

---

## Key File Locations

| File | Path |
|---|---|
| Workflow instructions | `workflows/maximizer_release_automation.md` |
| Email HTML template | `resources/email_template.html` |
| Screenshot inject script | `resources/screenshot_inject.py` |
| April 2026 release folder | `output/2026-04-release/` |
| April release payload | `output/2026-04-release/release_payload.json` |
| April email draft | `output/2026-04-release/email_draft.html` |
| April Zendesk article | `output/2026-04-release/zendesk_article.md` |

---

## Key Credentials (stored locally in `~/.zshrc`)

| Variable | Used for |
|---|---|
| `RESEND_API_KEY` | Sending emails and creating broadcasts |
| `RESEND_AUDIENCE_ID` | Release Notes audience in Resend |
| `ZENDESK_API_TOKEN` | Creating/updating Zendesk articles |
| `ZENDESK_SUBDOMAIN` | `maximizer` |
| `ZENDESK_EMAIL` | Zendesk API auth email |

> ⚠️ These are local only. The remote CCR routine cannot access them. If you want the routine to call Zendesk or Resend directly, the keys need to be embedded in the routine prompt or stored as GitHub secrets.

---

## Email Template — WordPress Image URLs

All 8 template images are hosted on maximizer.com WordPress:

| Image | URL |
|---|---|
| Header | https://maximizer.com/wp-content/uploads/2026/04/release-email-header.png |
| App store / footer assets | See `resources/email_template.html` for full list |

These are static assets — do not delete from WordPress.

---

## How to Run the May 2026 Release

1. Wait for the routine to fire on May 17 (or run it manually from the routines page)
2. Check `output/2026-05-release/RELEASE_BRIEFING.md` for the checklist
3. Open the Loop page for May 2026 in Chrome (ensure Claude in Chrome extension is active)
4. Start a new Claude Code session and say:
   > _"Run the Maximizer Release Automation workflow for May 2026. The Loop page URL is: [URL]"_
5. The agent will generate the Zendesk article, email draft, and screenshot markers
6. Brief PMs to upload screenshots to the Zendesk draft using exact feature names
7. Run `python3 resources/screenshot_inject.py output/2026-05-release/` to inject screenshots before sending

---

## Resend Broadcasts API — Quick Reference

```bash
# 1. Create broadcast
curl -X POST https://api.resend.com/broadcasts \
  -H "Authorization: Bearer $RESEND_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"audience_id":"$RESEND_AUDIENCE_ID","from":"Maximizer <marketing@maximizer.com>","subject":"SUBJECT","html":"HTML_CONTENT"}'

# 2. Send broadcast (replace BROADCAST_ID)
curl -X POST https://api.resend.com/broadcasts/BROADCAST_ID/send \
  -H "Authorization: Bearer $RESEND_API_KEY"
```

---

## Session Context

- Claude Code project: `/Users/lewisdyson/Desktop/Claude Code/`
- GitHub repo: `dysonmaximizer-sys/claude`
- Output base: `/Users/lewisdyson/Desktop/Claude Code/output/`
- All output files stay in the `output/` folder — never read from here as reference material
- Reference material lives in `/Users/lewisdyson/Context Station/`
