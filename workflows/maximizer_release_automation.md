# Maximizer Release Automation Agent — Workflow Instructions

## Purpose
Transform raw product update data from a Microsoft Loop page into two polished, publish-ready marketing assets: a Zendesk release notes article and a Resend CS email draft. All outputs are saved for human review before publishing. Nothing is auto-published.

> **Parked (revisit later):** Previously this workflow also produced a Zendesk in-app notification for Announcements. That step is removed pending a plan upgrade (Zendesk Announcements requires Enterprise tier; Maximizer is currently on Professional).

---

## Trigger
This workflow is **manually kicked off by the operator** each release cycle.

A separate scheduled routine (cron-fired on the 17th of each month) emails the operator a reminder. The operator then starts this workflow manually any time before the end of the month — typically same day or within a few business days of the reminder.

**Why manual:** Step 1 reads Microsoft Loop via the Claude in Chrome browser extension, which requires the operator to be logged in to Microsoft 365 in Chrome. A remote unattended fire has no browser, so the workflow cannot run unattended.

On kickoff, Claude Code will:
1. Ask the operator for the Microsoft Loop page URL for the current release cycle.
2. Ask for the release version label (e.g., `April 2026` or `v26.4`).
3. Calculate and display the full schedule of actions for this cycle (see Timing Schedule below).
4. Proceed through the steps below.

---

## Timing Schedule

The trigger date is the day the operator kicks off the workflow. From that date, calculate and display the following dates, adjusting to business days:

| Action | Timing rule | Business day adjustment |
|---|---|---|
| Workflow runs, drafts generated | Trigger date (operator kickoff) | Operator chooses a business day |
| Review window closes — CS team notified | +2 business days from trigger | If weekend, use following Monday |
| Zendesk article goes live | 7 days before end of month | If weekend, use preceding Friday |
| Customer email sent (with Learn more link) | Same day as Zendesk publish | Same as above |

> **Hard rule:** Everything must complete before the end of the calendar month. If the trigger date is late enough that standard timing would push publish into the next month, compress: review and publish on the same day, no later than the last business day of the month.

> **Note:** This workflow does not account for public holidays. The operator should manually verify that calculated dates do not fall on a public holiday and adjust if needed.

**Example output (trigger date Tuesday, May 26, 2026):**
```
Release cycle: May 2026
Workflow triggered:          Tuesday, May 26
Review deadline:             Tuesday, May 26   ← compressed (late kickoff)
Zendesk + email go live:     Tuesday, May 26   ← compressed (same day)
```

---

## Step 1 — Get the Loop Page as a PDF Export

The release content lives on a Microsoft Loop page. **Do not screen-scrape the live Loop page** — its canvas virtualizes content (only the visible slice is in the DOM) and its feature headings are not semantic HTML, which makes live reading slow, lossy, and unreliable for mapping images to features. Instead, work from a PDF export, which is a complete, stable snapshot with full-resolution images, all text in document order, and exact layout positions.

### Get the PDF
Ask the operator to export the current release cycle's Loop page to PDF and provide the file path. Either method works:
- In Loop: open the page menu and choose **Export** (or **Print**), then **Save as PDF**.
- Or in the browser: **Print** (Cmd/Ctrl+P) on the Loop page → **Save as PDF**, saved to `~/Downloads/`.

The exported file is typically named after the page, e.g. `~/Downloads/2026 M6.pdf`.

> Earlier cycles read the live page via the Claude in Chrome extension. That path is retired for content extraction because of the virtualization issues above. (The browser extension is still fine if you only need to *visually confirm* the page; it is not the content source.)

### Extract text + images
Run the extraction helper (requires `pymupdf` — see `requirements.txt`):

```bash
python3 "resources/loop_pdf_extract.py" "~/Downloads/{{Release Page}}.pdf" "output/{{YYYY-MM}}-release/"
```

This produces:
- `output/{{YYYY-MM}}-release/loop_text.txt` — full page text in document order (the table, then each feature's name, Edition, Area, What's new / Why it matters / How it works, and image captions). Read this to author the assets.
- `output/{{YYYY-MM}}-release/images/raw/NN.png` — every content image at full resolution, in document order, with the repeated page-background watermark and emoji icons already filtered out. This folder is the input for Step 3a.
- `output/{{YYYY-MM}}-release/images/raw/_image_context.json` — for each image: its page, vertical position, and the nearest text above it. Use this together with `loop_text.txt` to map each image to the feature whose section it sits under (see Step 3a — **map by section position, never by raw image index**).

### Warning — no PDF / empty extract
If no PDF path is provided, or the extract yields no text, output the following and stop:
> **WARNING:** Could not read the Loop page export. Please export the current release Loop page to PDF (Loop → Export → Save as PDF, or browser Print → Save as PDF) and provide the file path. Re-trigger the workflow once provided.

If no content images are extracted, log it and continue — the cycle can still produce text-only assets, but flag to the operator that no images were found.

Once `loop_text.txt` and the images are extracted, proceed to Step 2.

---

## Step 2 — Parse and Filter the Loop Page

The extracted Loop text (`loop_text.txt` from Step 1) contains:
1. A **table** with a `Release Notes?` column controlling per-item inclusion
2. A **body section** below the table with full feature descriptions, grouped under section headings (`New Features`, `Improvements`, `Fixes`, etc.). The Loop page may render these as H1 **or** H2 — past pages have used both, so classify by heading text, not heading level.

### Filtering rules (strict, evaluated in order)

**Rule 1 — Master filter (gospel):** Only consider rows where the table's `Release Notes?` column = `True`. Any row where the column is `False`, blank, or any other value is discarded immediately, regardless of any heading or content elsewhere on the page. Do not infer or override this.

**Rule 2 — Heading-based classification:** For each row that passes Rule 1, find the corresponding feature description in the body section (matched by feature name) and determine the section heading it sits under. Match on the heading **text**, regardless of whether the Loop page renders it as H1 or H2 (Loop pages have used both — never key off the heading level alone):

| Section heading the description sits under | Outcome |
|---|---|
| `New Features` | Include as `Feature Type = New Feature` |
| `Improvements` | Include as `Feature Type = Improvement` |
| `Fixes` | **Omit entirely** from all outputs |
| Any other heading, or no heading at all | **Omit entirely** |

**Admin & Configuration Updates are omitted entirely**, regardless of `Release Notes?` value. Do not produce this section in any output.

### Warning — no eligible items
If zero items pass both rules and resolve to either `New Feature` or `Improvement`, output this warning and stop:
> **WARNING:** No items qualify for release notes. Either no rows are marked `Release Notes? = True`, or all qualifying rows sit under sections that are excluded (Fixes, Admin, or none). Review the Loop page and re-trigger the workflow once corrected.

### Data to extract per included item
For each row passing both rules, capture:
- Feature name (from table)
- Feature Type (`New Feature` or `Improvement`, derived from the section heading per Rule 2)
- Edition: `Financial Services Edition` / `Sales Leader Edition` / `Base Edition` (from table)
- Area: `Web` / `Mobile` / `Outlook` (from table)
- Full product description (from body section under the section heading)
- Any screenshots or GIF links embedded in the body section
- Any linked user guide URLs

---

## Step 3a — Upload Images to HubSpot

Before generating assets, upload the images extracted in Step 1 to HubSpot Files so both the Zendesk article and the email can reference public CDN URLs.

```bash
source ~/.zshrc   # provides HUBSPOT_SERVICE_KEY
python3 "resources/hubspot_upload.py" "output/{{YYYY-MM}}-release/images/raw/"
```

- The script uploads each image (alphabetical = document order from the Step 1 PDF extract) to `/release-notes/{{YYYY-MM}}/` in HubSpot and writes `output/{{YYYY-MM}}-release/hubspot_urls.json` — a map of local filename → public CDN URL.
- It exits `0` on full success, `2` if any upload failed. On a non-zero exit, surface which files failed and stop before asset generation — do not publish an article with broken image links.
- Auth is the HubSpot Service Key (`HUBSPOT_SERVICE_KEY`, `Files` scope) in `~/.zshrc`. If it is missing or returns 401/403, stop and flag the operator to refresh the key.
- If Step 1 found no images, skip this step and generate text-only assets, flagging that no images were uploaded.

`hubspot_urls.json` is the single source of image URLs for both Asset 1 and the email — no Zendesk attachments, no WordPress.

---

## Step 3 — Generate Output Assets

Using the filtered data, generate two assets following the rules below.

### Asset 1: Zendesk Release Notes

Follow the template in `resources/release_notes_template.md` exactly.

**Content rules:**
- Combine and harmonize input from all PMs — fix grammar, remove redundancy, unify tone
- Write in active voice, benefits-first, professional and concise
- Never repeat the same phrasing across features
- Suggest a clear, consistent title for every feature
- **Order features by customer impact, not by Loop order** — lead with the biggest/highest-impact features within `New Features`, then the rest; keep `Improvements` after `New Features`. Use the **same order in both the Zendesk article and the email** so they stay consistent. When impact is unclear, ask the operator which features are the headline items.
- Normalize Edition names to the published convention (see template formatting rule): `FSE` → `Financial Services Edition`, `FSE+` → `Financial Services Edition +`, `Base` → `Base Edition`, `Sales Leader` → `Sales Leader Edition`, `All` → `All Editions`; keep `Business+` as-is; join multiple editions with a comma (e.g. `Financial Services Edition +, Business+`)
- Do NOT generate a table of contents. Zendesk's Help Center theme auto-generates its own TOC from the article headings on publish; an in-body TOC creates a duplicate on the live page
- Heading structure: use Heading 2 (`##`) for `Summary`, `New Features`, `Improvements`, and each feature/improvement name. Do not use Heading 1 in the body (reserved for the article title)
- Do NOT write an article title in the body. The release title goes in the Zendesk article Title field (see Step 7a), not as a body `#` heading. The body's first heading is `## Summary`
- Put `Edition:` and `Area:` on separate lines with a blank line between them so they render as separate rows, not one combined string
- Omit `Fixes` and `Admin & Configuration Updates` sections entirely — these item types are excluded from all outputs per Step 2 filtering
- Do not use emojis in headings
- Do not use section dividers (horizontal rules)

**Images:**
- Use the HubSpot CDN URLs from `output/{{YYYY-MM}}-release/hubspot_urls.json` (produced in Step 3a). Do NOT use `[IMAGE: ...]` placeholders, Zendesk attachments, or any other source.
- Map each image to the feature whose section it sits under — **by position, not by raw index**. Use `images/raw/_image_context.json` (page + vertical position per image) together with `loop_text.txt` to determine which feature heading each image falls under. Do NOT assume image `NN` belongs to feature `NN`: excluded features (or features with zero/multiple images) shift the alignment. Confirm by matching the image's caption text in `loop_text.txt`.
- Embed each image inline beneath the relevant section as an HTML tag with a constrained width, so it stays proportionate to the body text (this replaces manual resizing):
  `<img src="{CDN URL}" alt="{short description of what is shown}" style="max-width:650px;width:100%;height:auto;">`
- Do NOT precede images with a `Screenshots` label/heading or a `Screenshot:` caption — no label, no caption prefix.
- The 650px max-width keeps inline images readable and aligned to the content column — do not insert full-resolution crops that span multiple screens.
- If no image maps to a given feature, omit the image for that feature.

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
`What's New in Maximizer: [Month] [YYYY]`
Example: `What's New in Maximizer: October 2025`
No emojis. Immediately after the title, add exactly **one sentence** in Maximizer's voice that says what the email is and introduces the release notes (so it doesn't launch straight into features). Example: `Here's a preview of the new features and improvements coming in the June 2026 Maximizer Cloud release.` Then start the first feature.

**Feature section format (repeat for every eligible feature):**

```
[Feature Title]

What's new:
[1–3 sentences explaining exactly what changed. Mention where it appears in the UI.
Mention if configuration is required. Mention limits if applicable. No benefits here.]

Why it matters:
[1–3 sentences on workflow impact and practical benefit. Mention compliance,
time savings, clarity, or accuracy where relevant. No new technical detail.]

<img src="{HubSpot CDN URL for this feature from hubspot_urls.json}" alt="{caption}" style="max-width:600px;width:100%;height:auto;">
[Image caption — plain text, descriptive, no colon at end, no filename, no "Screenshot of"]
```

**Feature title rules:**
- Sentence case, no trailing period, under 10 words when possible
- Outlook integrations: `Maximizer CRM for Outlook: [Feature Name]`
- Renames: clearly state the rename and that functionality is unchanged

**Image rules:**
- Source every image from `output/{{YYYY-MM}}-release/hubspot_urls.json` (Step 3a) — the same CDN URLs used in the Zendesk article. No Zendesk attachments, no markers, no placeholders.
- Embed inline as `<img src="{CDN URL}" alt="..." style="max-width:600px;width:100%;height:auto;">`, associated to features by DOM order (`01.png`, `02.png`, …) exactly as in Asset 1.
- One caption line directly below each image: plain text, not bold, describes what is visible (e.g., `Accounts module showing grid and Kanban toggle buttons`), no colon at the end, no filename, no "Screenshot of".
- Multiple images for one feature: each `<img>` + caption on its own line, blank line between each.

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

**Output format:** Build `email_draft.html` by populating the branded shell `resources/email_template.html` — replace its tokens: `{{EMAIL_TITLE}}` (the `What's New in Maximizer: [Month] [YYYY]` header), `{{INTRO_SENTENCE}}` (the one-sentence intro above), `{{FEATURE_BLOCKS}}` (the per-feature blocks, with HubSpot CDN `<img>` tags), and `{{LEARN_MORE_URL}}`. Do NOT hand-roll a bare HTML body — the shell carries the Maximizer header banner, footer logo, social icons, address, and app-store badges. Each feature block follows the [A] heading / [B] What's new + Why it matters / [C] image pattern documented inline in the shell.

**Resend delivery configuration:**
- From: `marketing@maximizer.com` (requires maximizer.com domain verified in Resend)
- CS team recipient: `customersuccess@maximizer.com`
- Customer list: **Release Notes** audience in Resend (`$RESEND_AUDIENCE_ID`)

---

## Step 4 — Save Outputs

Create a new folder: `output/YYYY-MM-release/` using the current month and year (e.g., `output/2026-04-release/`).

Save the following files to that folder:

| File | Contents |
|---|---|
| `zendesk_article.md` | Full Zendesk release notes (Markdown) |
| `email_draft.html` | Resend email body (HTML) |
| `email_subject.txt` | Email subject line (plain text) |
| `release_payload.json` | All outputs wrapped in JSON (see schema below) |

### JSON schema for `release_payload.json`
```json
{
  "release_version": "{{Release Version}}",
  "release_date": "{{Month DD, YYYY}}",
  "zendesk_content": "See zendesk_article.md",
  "email_subject": "{{CS email subject line}}",
  "email_body": "See email_draft.html",
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
> - `release_payload.json` → use for API publishing once all credentials are configured
>
> **Review deadline: {{Review Deadline Date}}**
> **Nothing has been published. No action is taken until you manually approve.**

---

## Step 6 — CS Team Notification (Review Deadline)

> **Note (2026-07): this step is OPTIONAL.** The CS team is already inside the Release Notes audience, so they receive the broadcast itself. The separate review email was skipped in July 2026; send it only if a cycle specifically needs pre-publish CS review.

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
- Set the article **Title** field to `Maximizer Cloud – {{Month}} {{Year}}.{{Month number}}` — e.g. `Maximizer Cloud – July 2026.7`. (New convention from 2026-07, Lewis-directed; the old `Maximizer Cloud – June 2026 (2026 M6)` style is retired, pre-July 2026 articles keep their existing titles.) Do NOT also place a title heading in the body.
- After publishing, retrieve the live article URL and identify the anchor for the first content section
- **Immediately** write `zendesk_article_url` (full URL + anchor) to `release_payload.json`

### 7b — Confirm Publish
Output a confirmation to the operator:
> **Published:** Zendesk article and in-app notification for `{{Release Version}}` are now live.
> Article URL: `{{Zendesk Article URL}}`

### 7c — Verify Email Images

Images are already embedded as HubSpot CDN `<img>` URLs when `email_draft.html` is generated (Step 3 Asset 2, sourced from `hubspot_urls.json`). There is no injection step.

- Open `email_draft.html` and confirm each feature's image renders from its `https://...hubspotusercontent-na1.net/...` URL.
- If an image is missing or broken, check `hubspot_urls.json` for an empty value (a failed Step 3a upload), fix the upload, and regenerate the email.

> The legacy `resources/screenshot_inject.py` (Zendesk-attachment injection) is superseded by the HubSpot pipeline and is no longer called. The file is left in place for history only.

### 7d — Deploy Customer Email via Resend
- Read `zendesk_article_url` from `release_payload.json`
- Confirm `email_draft.html` images render from their HubSpot CDN URLs (Step 7c)
- In `email_draft.html`, replace `{{LEARN_MORE_URL}}` (or the `[Link to Release Notes]` placeholder if still present) with the value from `zendesk_article_url` — do not manually construct this URL
- Send the updated email via Resend to the **Release Notes** audience (`$RESEND_AUDIENCE_ID`)
- Use the subject line from `email_subject.txt`

**Test send first (standing step since 2026-07, required):** before creating the broadcast, email the operator a copy of the final HTML via the standard `/emails` endpoint — from `marketing@maximizer.com` to `lewisdyson@maximizer.com`, subject prefixed `[DRAFT] `. Wait for the operator's explicit approval before proceeding to the broadcast.

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
> Images: embedded from HubSpot CDN (`{{N}}` images)
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
3. Images are already embedded as HubSpot CDN URLs in the article body (from Step 3a) — no manual screenshot upload needed.
4. Set the article Title field per Step 7a's naming convention, publish, and copy the live article URL.

### Step 7c — Deploy customer email (same day)
1. Log in to [resend.com](https://resend.com) and go to **Broadcasts**.
2. Create a new broadcast, selecting the **Release Notes** audience.
3. Paste the HTML from `email_draft.html` — replace `[Link to Release Notes]` with the live Zendesk article URL, linked as **Learn more**.
4. Images are already embedded from HubSpot CDN — no placeholder replacement needed.
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
| Zero items qualify (no rows with `Release Notes?` = True, or all qualifying rows under excluded H1) | Output warning, stop workflow |
| Feature has no associated description | Include feature with note: `[Description not found — please add manually]` |
| Screenshot/GIF not found in Loop page | Omit the Screenshots block for that feature silently |
| Missing Edition or Area field | Leave as `[Edition TBC]` or `[Area TBC]` and flag in the review message |
| Resend API key missing or invalid | Output warning, fall back to manual sending instructions |
| Zendesk API token missing or invalid | Output warning, fall back to manual publishing instructions |
