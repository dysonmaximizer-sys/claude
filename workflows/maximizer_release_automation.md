# Maximizer Release Automation Agent — Workflow Instructions

## Purpose
Transform raw product update data from a Microsoft Loop page into three polished, publish-ready marketing assets: a Zendesk release notes article, a HubSpot CS email draft, and a Zendesk in-app notification. All outputs are saved for human review before publishing. Nothing is auto-published.

---

## Trigger
This workflow is scheduled to run on the **17th of each month**.

On trigger, Claude Code will:
1. Ask the operator for the Microsoft Loop page URL for the current release cycle.
2. Ask for the release version label (e.g., `April 2026` or `v26.4`).
3. Proceed through the steps below.

---

## Step 1 — Authenticate and Fetch the Loop Page

### Credential requirements
Microsoft Loop is hosted on SharePoint (Microsoft 365). Access requires a valid access token.

On first run, prompt the operator:
> "To fetch the Loop page, I need a Microsoft Graph API access token or SharePoint credentials. Please paste your access token, or confirm that you have saved it to the environment variable `MS_GRAPH_TOKEN`."

Use the provided token to fetch the Loop page via Microsoft Graph API:
```
GET https://graph.microsoft.com/v1.0/me/drive/root:/path/to/loop/file:/content
Authorization: Bearer {MS_GRAPH_TOKEN}
```

If the token is missing or expired, output the following warning and stop:
> **WARNING:** Microsoft Loop credentials are missing or invalid. The workflow cannot proceed without a valid access token. Please provide a fresh token and re-trigger the workflow.

If the page is successfully fetched, proceed to Step 2.

---

## Step 2 — Parse and Filter the Loop Table

The Loop page contains a table of product features. Each row has a column named **"Release Notes?"**.

### Filtering rules (strict)
- **Include** only rows where `Release Notes?` = `True`
- **Discard** all rows where `Release Notes?` = `False`, blank, or any other value
- For each included row, also extract the associated **product feature description** found in the body text below the table (matched by feature name)

### Warning — no eligible items
If zero rows have `Release Notes?` = `True`, output this warning and stop:
> **WARNING:** No items on this Loop page are marked "Release Notes? = True". No output has been generated. Please review the Loop page and re-trigger the workflow once items are marked correctly.

### Data to extract per feature
For each eligible row, capture:
- Feature name
- Feature type: `New Feature` or `Improvement` (or `Fix` / `Admin Update` if labelled as such)
- Edition: `Financial Services Edition` / `Sales Leader Edition` / `Base Edition`
- Area: `Web` / `Mobile` / `Outlook`
- Full product description from the body section below the table
- Any screenshots or GIF links embedded in the page
- Any linked user guide URLs

---

## Step 3 — Generate Output Assets

Using the filtered data, generate three assets following the rules below.

### Asset 1: Zendesk Release Notes

Follow the template in `resources/release_notes_template.md` exactly.

**Content rules:**
- Combine and harmonize input from all PMs — fix grammar, remove redundancy, unify tone
- Write in active voice, benefits-first, professional and concise
- Never repeat the same phrasing across features
- Suggest a clear, consistent title for every feature
- Generate a table of contents from the feature headings
- Omit `Fixes` and `Admin & Configuration Updates` sections entirely if no items are marked as such — do not include empty sections
- Do not use emojis in headings
- Do not use section dividers (horizontal rules)

**Screenshots:**
- Reference screenshots and GIFs extracted from the Loop page using this format:
  - `[Screenshot: FeatureName_1]`
  - `[GIF: FeatureName_Interaction_1]`
- If no screenshots are available for a feature, omit the Screenshots block for that feature

---

### Asset 2: HubSpot CS Email Draft

**Subject line:**
Write one punchy, professional subject line. Format: `Coming Soon: [Primary benefit or feature theme] – [Month YYYY]`
Example: `Coming Soon: New AI Insights and Faster Workflows – April 2026`

**Email body rules:**
- Audience: existing customers (wealth advisors, insurance advisors, sales teams)
- Tone: warm, professional, benefits-first — not promotional or hypey
- Structure:
  1. Opening line (1 sentence) — frame the release value
  2. Feature highlights — one short paragraph or 3–5 bullet points per feature (benefits-led, not technical)
  3. Closing line — direct them to the release notes with placeholder: `[Link to Release Notes]`
  4. Sign-off: `The Maximizer Team`
- Insert screenshot placeholders in the same format as the Zendesk article where relevant
- Output as clean HTML suitable for pasting into HubSpot's email editor

---

### Asset 3: Zendesk In-App Notification

Write a single, punchy paragraph (3–4 sentences maximum) for Zendesk's native Announcements tool.

**Rules:**
- Lead with the primary benefit of the release
- Name the top 2–3 features in plain language
- Close with a call to action pointing to the release notes
- No technical jargon, no bullet points, no headings
- Plain text only (no HTML or Markdown)

---

## Step 4 — Save Outputs

Create a new folder: `output/YYYY-MM-release/` using the current month and year (e.g., `output/2026-04-release/`).

Save the following files to that folder:

| File | Contents |
|---|---|
| `zendesk_article.md` | Full Zendesk release notes (Markdown) |
| `email_draft.html` | HubSpot CS email body (HTML) |
| `email_subject.txt` | Email subject line (plain text) |
| `inapp_notification.txt` | Zendesk in-app notification (plain text) |
| `release_payload.json` | All four outputs wrapped in JSON (see schema below) |

### JSON schema for `release_payload.json`
```json
{
  "release_version": "{{Release Version}}",
  "release_date": "{{Month DD, YYYY}}",
  "zendesk_content": "{{Full Markdown content of the Zendesk article}}",
  "email_subject": "{{CS email subject line}}",
  "email_body": "{{Full HTML email body}}",
  "in_app_summary": "{{Plain text in-app notification}}"
}
```

---

## Step 5 — Human Review Checkpoint

After saving all files, output the following message to the operator:

> **Review Required**
>
> All draft outputs for the `{{Release Version}}` release have been saved to `output/{{YYYY-MM}}-release/`.
>
> Please review the following files before publishing:
> - `zendesk_article.md` → publish to Zendesk (article)
> - `email_draft.html` + `email_subject.txt` → create draft in HubSpot
> - `inapp_notification.txt` → post via Zendesk Announcements
> - `release_payload.json` → use for API publishing once Zendesk API credentials are configured
>
> **Nothing has been published. No action is taken until you manually approve and publish each asset.**

---

## Publishing Instructions (Manual, Post-Review)

### Zendesk article
1. Log in to Zendesk Guide.
2. Create a new article in the **Release Notes** section.
3. Paste the contents of `zendesk_article.md` (convert Markdown to HTML if required by your Zendesk theme).
4. Add screenshots/GIFs from the Loop page to replace the `[Screenshot]` and `[GIF]` placeholders.
5. Set visibility and publish.

> When Zendesk API credentials are available, add them as `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, and `ZENDESK_API_TOKEN` environment variables. The workflow will then offer to publish the article automatically via the Zendesk Articles API.

### HubSpot email draft
1. Log in to HubSpot Marketing > Email.
2. Create a new email and switch to the HTML editor.
3. Paste the contents of `email_draft.html`.
4. Replace `[Link to Release Notes]` with the published Zendesk article URL.
5. Replace screenshot placeholders with actual images.
6. Set recipients and schedule or send for review.

### Zendesk in-app notification
1. Log in to Zendesk.
2. Navigate to **Announcements** (or the native notifications tool).
3. Paste the contents of `inapp_notification.txt`.
4. Set the target audience and activation date.
5. Publish.

---

## Error Handling Summary

| Condition | Behavior |
|---|---|
| Missing or expired Microsoft auth token | Output warning, stop workflow |
| Zero rows with `Release Notes?` = True | Output warning, stop workflow |
| Feature has no associated description | Include feature with a note: `[Description not found — please add manually]` |
| Screenshot/GIF not found in Loop page | Omit the Screenshots block for that feature silently |
| Missing Edition or Area field | Leave as `[Edition TBC]` or `[Area TBC]` and flag in the review message |
