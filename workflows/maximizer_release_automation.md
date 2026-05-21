# Maximizer Release Automation Agent — Workflow Instructions

## Purpose
Transform raw product update data from a Microsoft Loop page into three polished, publish-ready marketing assets: a Zendesk release notes article, a Resend CS email draft, and a Zendesk in-app notification. All outputs are saved for human review before publishing. Nothing is auto-published.

---

## Trigger
This workflow is scheduled to run on the **17th of each month**.

**Business day rule:** If the 17th falls on a Saturday or Sunday, the workflow runs on the following Monday. No action is ever taken on a weekend.

On trigger, Claude Code will:
1. Ask the operator for the Microsoft Loop page URL for the current release cycle.
2. Ask for the release version label (e.g., `April 2026` or `v26.4`).
3. Calculate and display the full schedule of actions for this cycle (see Timing Schedule below).
4. Proceed through the steps below.

---

## Timing Schedule

On trigger, calculate and display the following dates for the operator, adjusting all dates to business days:

| Action | Timing rule | Business day adjustment |
|---|---|---|
| Workflow runs, drafts generated | 17th of the month | If weekend, use next Monday |
| Review window closes — CS team notified | +2 business days from trigger | Already a business day |
| Zendesk article + in-app notification go live | 7 days before end of month | If weekend, use preceding Friday |
| Customer email sent (with Learn more link) | Same day as Zendesk publish | Same as above |

> **Note:** This workflow does not account for public holidays. The operator should manually verify that calculated dates do not fall on a public holiday and adjust if needed.

**Example output for April 2026:**
```
Release cycle: April 2026
Workflow triggered:          Friday, April 17
Review deadline:             Tuesday, April 21  ← CS team notified by email
Zendesk + notification live: Thursday, April 23  ← article published, notification activated
Customer email sent:         Thursday, April 23  ← Resend email deployed with Learn more link
```

---

## Step 1 — Open and Read the Loop Page via Browser

Microsoft Loop requires Microsoft 365 authentication. Rather than using the Graph API, this workflow reads the Loop page directly through the Claude in Chrome browser extension, using the operator's existing authenticated browser session. No API token or separate credentials are required.

### Requirements
- The **Claude in Chrome** browser extension must be active
- The operator must be logged in to their Microsoft 365 account in Chrome

### Process
1. Open a new tab using `tabs_create_mcp`
2. Navigate to the Loop URL provided by the operator using `navigate`
3. Wait for the page to fully load (title changes from "Microsoft Loop" to the page title, e.g., "2026 M4")
4. Extract the full page content using the following approach:
   - Use `javascript_tool` to find the scrollable canvas container
   - Scroll through the page in sections (the Loop canvas uses virtual rendering — content below the fold is not in the DOM until scrolled into view)
   - Extract text using a `TreeWalker` traversal at each scroll position
   - Filter out lines containing `http`, `sharepoint`, or `loop.cloud` to avoid security filter blocks
   - Collect all unique text across scroll positions into a single content string

### Scroll strategy
The Loop canvas has a total scroll height of approximately 7000–9000px depending on content. Scroll through in the following passes:
- Position 0 (top) — captures page header and table
- Position 2500 — captures full table with all rows and column values
- Position 7204 (bottom) — captures feature description sections

At each position, run the TreeWalker extraction and concatenate unique content.

### Warning — page not accessible
If the page fails to load or returns a login screen, output the following and stop:
> **WARNING:** The Loop page could not be read. Please ensure you are logged in to Microsoft 365 in Chrome and that the Claude in Chrome extension is active. Re-trigger the workflow once confirmed.

If the page is successfully read, proceed to Step 2.

---

## Step 2 — Parse and Filter the Loop Table

The Loop page contains a table of product features. Each row has a column named **"Release Notes?"**.

### Filtering rules (strict)
- **Include** only rows where `Release Notes?` = `True`
- **Discard** all rows where `Release Notes?` = `False`, blank, or any other value
- This rule applies to **all item types without exception** — New Features, Improvements, Fixes, and Admin Updates are only included if explicitly tagged `Release Notes?` = `True`. Do not infer, assume, or include items based on type alone.
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
- Omit `Fixes` and `Admin & Configuration Updates` sections entirely unless one or more items of that type are explicitly tagged `Release Notes?` = `True` in the Loop table — do not include these sections based on PM notes, descriptions, or any source other than the Loop table tag
- Do not use emojis in headings
- Do not use section dividers (horizontal rules)

**Screenshots:**
- Reference screenshots and GIFs extracted from the Loop page using this format:
  - `[Screenshot: FeatureName_1]`
  - `[GIF: FeatureName_Interaction_1]`
- If no screenshots are available for a feature, omit the Screenshots block for that feature

---

### Asset 2: Resend Email Draft

Follow the template in `resources/email_template.md` exactly, including the Master Prompt input processing rules at the top of that file.

**Subject line:**
Write one punchy, professional subject line. Format: `Coming Soon: [Primary benefit or feature theme] – [Month YYYY]`
Example: `Coming Soon: New AI Insights and Faster Workflows – April 2026`

**Role & context:**
Write as a Senior Product Marketing Manager at Maximizer with 15+ years of experience writing CRM release communications for financial services professionals.

**Filtering rule (mandatory):**
Only include features where `Release Notes?` = `True`. Do not reference, summarize, or acknowledge any excluded features. If no eligible features exist, output only: `No features marked as Release Notes Worthy were provided.`

**Tone & style:**
- Professional, clear, confident
- Practical and benefit-driven
- No hype, no exaggeration, no promotional language
- No exclamation marks, no buzzwords, no em dashes
- No dramatic phrasing
- Short to medium length paragraphs
- Clarity over cleverness
- Written for advisors, insurance professionals, sales teams, and operations users
- Avoid vague phrases like "powerful enhancement" or "exciting update"
- Avoid repeating the feature title inside the description
- Avoid technical jargon unless necessary

**Email header:**
Always begin the body with:
`[Month Year] Release Notes Preview`
Example: `October 2025 Release Notes Preview`
No emojis. No introductory paragraph. Start immediately with the first feature.

**Feature section format (repeat for every eligible feature):**

```
[Feature Title]

What's new:
[1–3 sentences explaining exactly what changed. Mention where it appears in the UI.
Mention if configuration is required. Mention limits if applicable. No benefits here.]

Why it matters:
[1–3 sentences on workflow impact and practical benefit. Mention compliance,
time savings, clarity, or accuracy where relevant. No new technical detail.]

[Image caption — plain text, descriptive, no colon at end, no filename, no "Screenshot of"]
```

**Feature title rules:**
- Sentence case, no trailing period, under 10 words when possible
- Outlook integrations: `Maximizer CRM for Outlook: [Feature Name]`
- Renames: clearly state the rename and that functionality is unchanged

**Screenshot caption rules:**
- One caption per feature minimum
- Plain text, not bold
- Describes what is visible (e.g., `Accounts module showing grid and Kanban toggle buttons`)
- Multiple captions: one per line, blank line between each

**Consistency rules:**
- Every feature must include both `What's new` and `Why it matters`
- Every feature must include at least one screenshot caption
- Section labels (`What's new:`, `Why it matters:`) must be bold
- No summary paragraph unless explicitly requested
- No emojis, no exclamation marks

**Closing:**
End the email body with:
```
[Link to Release Notes]

The Maximizer Team
```

**Output format:** Clean HTML suitable for sending via Resend.

**Resend delivery configuration:**
- From: `marketing@maximizer.com` (requires maximizer.com domain verified in Resend)
- CS team recipient: `customersuccess@maximizer.com`
- Customer list: **Release Notes** audience in Resend (`$RESEND_AUDIENCE_ID`)

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
| `email_draft.html` | Resend email body (HTML) |
| `email_subject.txt` | Email subject line (plain text) |
| `inapp_notification.txt` | Zendesk in-app notification (plain text) |
| `release_payload.json` | All four outputs wrapped in JSON (see schema below) |

### JSON schema for `release_payload.json`
```json
{
  "release_version": "{{Release Version}}",
  "release_date": "{{Month DD, YYYY}}",
  "zendesk_content": "See zendesk_article.md",
  "email_subject": "{{CS email subject line}}",
  "email_body": "See email_draft.html",
  "in_app_summary": "{{Plain text in-app notification}}",
  "zendesk_draft_article_id": "{{Zendesk article ID returned by API}}",
  "zendesk_draft_url": "{{Base article URL without anchor}}",
  "zendesk_article_url": "{{Full article URL including #anchor to first section — set on publish day}}"
}
```

**Auto-save rule:** After creating the Zendesk draft in Step 4, immediately write `zendesk_draft_article_id` and `zendesk_draft_url` to `release_payload.json`. After publishing on Step 7a, update `zendesk_article_url` with the full URL including the anchor to the first content section (e.g. `#h_01...`). This URL is then used automatically in Step 7c to populate the `{{LEARN_MORE_URL}}` token in `email_draft.html` — no manual copy-paste required.

---

## Step 5 — Human Review Checkpoint

After saving all files, output the following message to the operator:

> **Review Required**
>
> All draft outputs for the `{{Release Version}}` release have been saved to `output/{{YYYY-MM}}-release/`.
>
> Please review the following files before the review deadline:
> - `zendesk_article.md` → review and approve for Zendesk
> - `email_draft.html` + `email_subject.txt` → review and approve for Resend
> - `inapp_notification.txt` → review and approve for Zendesk Announcements
> - `release_payload.json` → use for API publishing once all credentials are configured
>
> **Review deadline: {{Review Deadline Date}}**
> **Nothing has been published. No action is taken until you manually approve.**

---

## Step 6 — CS Team Notification (Review Deadline)

On the review deadline date (trigger + 2 business days), send an internal email to the CS team via Resend.

**From:** `marketing@maximizer.com`
**To:** `customersuccess@maximizer.com`
**Subject:** `Action Required: {{Release Version}} Release Assets Ready for Review`

**Body:**
```
Hi team,

The draft assets for the {{Release Version}} release are ready for your review.

Please review and approve the following before {{Publish Date}}:

- Zendesk release notes article: output/{{YYYY-MM}}-release/zendesk_article.md
- Customer email draft: output/{{YYYY-MM}}-release/email_draft.html
- In-app notification: output/{{YYYY-MM}}-release/inapp_notification.txt

Publishing schedule:
- Zendesk article + in-app notification go live: {{Publish Date}}
- Customer email deploys: {{Publish Date}}

Please flag any changes needed before the publish date.

This is an automated message from the Maximizer Release Automation Agent.
```

**Resend API call:**
```
POST https://api.resend.com/emails
Authorization: Bearer {RESEND_API_KEY}
Content-Type: application/json
{
  "from": "Maximizer <marketing@maximizer.com>",
  "to": ["customersuccess@maximizer.com"],
  "subject": "Action Required: {{Release Version}} Release Assets Ready for Review",
  "html": "{{email body above}}"
}
```

---

## Step 7 — Publish Day (7 Days Before End of Month)

On the publish date (7 days before end of month, adjusted to a business day), the following actions occur in this order:

### 7a — Publish Zendesk Article
- Publish `zendesk_article.md` to Zendesk Guide as the official release notes article in the **Release Notes → Cloud** section (`ID: 23951413801741`)
- After publishing, retrieve the live article URL and identify the anchor for the first content section
- **Immediately** write `zendesk_article_url` (full URL + anchor) to `release_payload.json`
- Activate the in-app notification using the content in `inapp_notification.txt` via Zendesk Announcements

### 7b — Confirm Publish
Output a confirmation to the operator:
> **Published:** Zendesk article and in-app notification for `{{Release Version}}` are now live.
> Article URL: `{{Zendesk Article URL}}`

### 7c — Inject Screenshots into Email Draft

Before sending, run the screenshot injection script to pull Zendesk attachment URLs and replace the `<!-- SCREENSHOT:Name -->` markers in `email_draft.html` with real `<img>` blocks:

```bash
source ~/.zshrc
python3 "resources/screenshot_inject.py" "output/{{YYYY-MM}}-release/"
```

The script fetches all attachments from the published Zendesk article (using `zendesk_draft_article_id` from `release_payload.json`), matches each attachment filename to the corresponding marker in the email, and inserts a full-width image table. Any marker with no matching attachment is silently removed — the caption text below it is preserved.

**How markers work:**
- `email_draft.html` contains `<!-- SCREENSHOT:Name -->` comment markers where images should appear — no caption text
- When the inject script runs and finds a matching Zendesk attachment, the marker is replaced with a full-width `<img>` block
- When no match is found, the marker is silently removed — no placeholder, no caption, no broken layout
- The email is always sendable regardless of how many screenshots are resolved

**Screenshot naming convention for PMs (mandatory):**
Filenames uploaded to the Zendesk article must exactly match the marker names. Convention: `FeatureName_ImageDescription` with no spaces. Examples:

| Marker name | Upload filename |
|---|---|
| `InsuranceSuite_Dashboard` | `InsuranceSuite_Dashboard.png` |
| `InvestmentDashboard_Overview` | `InvestmentDashboard_Overview.png` |
| `Workflows_MainScreen` | `Workflows_MainScreen.png` |

The full marker list for any release is visible in `email_draft.html` as `<!-- SCREENSHOT:Name -->` comments.

After injection, confirm the script output shows all markers resolved. If any are missing, the PM needs to upload the corresponding file to the Zendesk article and re-run the script.

### 7d — Deploy Customer Email via Resend
- Read `zendesk_article_url` from `release_payload.json`
- Confirm `email_draft.html` has been updated by the screenshot injection step above
- In `email_draft.html`, replace `{{LEARN_MORE_URL}}` (or the `[Link to Release Notes]` placeholder if still present) with the value from `zendesk_article_url` — do not manually construct this URL
- Send the updated email via Resend to the **Release Notes** audience (`$RESEND_AUDIENCE_ID`)
- Use the subject line from `email_subject.txt`

Resend sends to a contact list via the **Broadcasts** API (two-step: create then send):

**Step 1 — Create broadcast:**
```
POST https://api.resend.com/broadcasts
Authorization: Bearer {RESEND_API_KEY}
Content-Type: application/json
{
  "audience_id": "{RESEND_AUDIENCE_ID}",
  "from": "Maximizer <marketing@maximizer.com>",
  "subject": "{{email_subject}}",
  "html": "{{email_body with live Learn more link}}"
}
```
Note the `id` returned in the response — required for Step 2.

**Step 2 — Send broadcast:**
```
POST https://api.resend.com/broadcasts/{id}/send
Authorization: Bearer {RESEND_API_KEY}
Content-Type: application/json
{}
```

> **Note:** For CS team test sends (single recipient, not full audience), use the standard `/emails` endpoint instead (same format as Step 6).

Output a final confirmation:
> **Deployed:** Customer email for `{{Release Version}}` has been sent via Resend.
> Subject: `{{Email Subject}}`
> Zendesk article: `{{Zendesk Article URL}}`
> Screenshots injected: `{{N}} of {{N}} resolved`
>
> Release cycle complete.

---

## Publishing Instructions (Manual, Post-Review)

> These manual steps apply until all API credentials are fully configured and tested end-to-end.
> Once confirmed working, Steps 6 and 7 execute automatically.

### Step 6 — CS team notification (review deadline)
1. Log in to [resend.com](https://resend.com) and go to **Emails → Send email**.
2. Set **From** to `marketing@maximizer.com`, **To** to `customersuccess@maximizer.com`.
3. Paste the subject and HTML body defined in Step 6 above.
4. Send on the review deadline date. Do not send on a weekend.

### Step 7a — Publish Zendesk article (publish date)
1. Log in to Zendesk Guide.
2. Open the draft article created in the **Release Notes → Cloud** section.
3. Upload screenshots/GIFs from `output/{{YYYY-MM}}-release/` and replace `[Screenshot]` and `[GIF]` placeholders.
4. Publish and copy the live article URL.

### Step 7a (cont.) — Activate in-app notification (same day)
1. Log in to Zendesk.
2. Navigate to **Announcements**.
3. Paste the contents of `inapp_notification.txt`.
4. Set the target audience and activate immediately.

### Step 7c — Deploy customer email (same day)
1. Log in to [resend.com](https://resend.com) and go to **Broadcasts**.
2. Create a new broadcast, selecting the **Release Notes** audience.
3. Paste the HTML from `email_draft.html` — replace `[Link to Release Notes]` with the live Zendesk article URL, linked as **Learn more**.
4. Replace screenshot placeholders with actual images.
5. Set the subject line from `email_subject.txt` and schedule for send. Do not send on a weekend.

---

## Environment Variables Reference

| Variable | Value | Purpose |
|---|---|---|
| `ZENDESK_SUBDOMAIN` | `maximizer8634` | Zendesk account subdomain |
| `ZENDESK_EMAIL` | `oulamurad@maximizer.com` | Zendesk admin account |
| `ZENDESK_API_TOKEN` | stored in `~/.zshrc` | Zendesk API authentication |
| `RESEND_API_KEY` | stored in `~/.zshrc` | Resend API authentication |
| `RESEND_FROM_EMAIL` | `marketing@maximizer.com` | Verified sender (requires maximizer.com domain verified in Resend) |
| `RESEND_AUDIENCE_ID` | set once audience is created in Resend dashboard | Release Notes contact audience |
| Claude in Chrome extension | active in Chrome | Microsoft Loop page access (replaces Graph API) |

### Email Template Image URLs

All template images are hosted on maximizer.com via WordPress. These are static assets — do not change between releases unless the branding is updated.

| Asset | WordPress URL |
|---|---|
| Header banner | `https://www.maximizer.com/wp-content/uploads/2026/04/header_banner.png` |
| Footer logo | `https://www.maximizer.com/wp-content/uploads/2026/04/footer_logo.png` |
| Facebook icon | `https://www.maximizer.com/wp-content/uploads/2026/04/icon_facebook.png` |
| LinkedIn icon | `https://www.maximizer.com/wp-content/uploads/2026/04/icon_linkedin.png` |
| X / Twitter icon | `https://www.maximizer.com/wp-content/uploads/2026/04/icon_twitter.png` |
| Instagram icon | `https://www.maximizer.com/wp-content/uploads/2026/04/icon_instagram.png` |
| App Store badge | `https://www.maximizer.com/wp-content/uploads/2026/04/badge_appstore.png` |
| Google Play badge | `https://www.maximizer.com/wp-content/uploads/2026/04/badge_googleplay.png` |

These URLs are baked into `resources/email_template.html`. If branding changes, update the files in WordPress, upload the new versions, and replace the URLs in the template.

### Resend domain verification requirements (one-time setup)

Before any email can be sent from `marketing@maximizer.com`, IT must add two DNS records to maximizer.com:

| Record type | Purpose |
|---|---|
| TXT (SPF) | Authorizes Resend to send on behalf of maximizer.com |
| CNAME (DKIM) | Cryptographic signing to prevent spoofing |

Records are generated automatically in the Resend dashboard under **Domains → Add Domain**. Once added, provide the records to IT and re-check status in Resend once DNS propagates (typically 24–48 hours).

Until domain verification is complete, test sends can be directed to `lewisdyson@maximizer.com` using the `onboarding@resend.dev` from address (available on all Resend accounts without domain setup).

---

## Error Handling Summary

| Condition | Behavior |
|---|---|
| Loop page fails to load or shows login screen | Output warning, stop workflow — ensure Chrome is logged in to M365 |
| Zero rows with `Release Notes?` = True | Output warning, stop workflow |
| Feature has no associated description | Include feature with note: `[Description not found — please add manually]` |
| Screenshot/GIF not found in Loop page | Omit the Screenshots block for that feature silently |
| Missing Edition or Area field | Leave as `[Edition TBC]` or `[Area TBC]` and flag in the review message |
| Resend API key missing or invalid | Output warning, fall back to manual sending instructions |
| Zendesk API token missing or invalid | Output warning, fall back to manual publishing instructions |
