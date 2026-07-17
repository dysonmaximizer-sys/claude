# Maximizer Release Notes — Output Template

> This template is the authoritative format for all Zendesk release notes articles.
> Do not deviate from the structure, headings, labels, or formatting rules.
> Omit optional sections if no relevant content exists — do not leave them empty.

---

## FORMATTING RULES (MANDATORY — READ FIRST)

These rules override any default formatting behaviour. Follow them exactly on every output.

1. **No bold on Edition or Area labels.** Write `Edition: All` not `**Edition:** All`
2. **Bold on content section labels only.** Write `**What's new**`, `**Why it matters**`, `**How it works**`, `**What has changed**`. Do NOT bold `Edition`, `Area`, or `Release Date`.
3. **No Description label.** Do not insert a `Description` or `**Description**` heading between Area and What's new
4. **No horizontal section dividers.** Do not use `---` between features, improvements, or sections
5. **No bold on Release Date.** Write `Release Date: Month DD, YYYY` not `**Release Date:**`
6. **Numbered steps in How it works.** Use `1.` `2.` `3.` — not bullet points (`-`)
7. **No emojis in any heading**
8. **Omit How it works entirely** if no meaningful steps exist for a feature
9. **Omit optional sections entirely** (Fixes, Admin & Configuration Updates) if no content applies — do not leave them empty or with placeholder text
10. **Feature type determines label:** New Features use `What's new` — Improvements use `What has changed`
11. **No Table of Contents.** Do NOT author a `## Table of Contents` block or any in-body TOC. The Zendesk Help Center theme auto-generates its own TOC from the article headings on publish. A hand-written one produces a second, duplicate TOC on the live page.
12. **Body headings use Heading 2 only.** Use Heading 2 (`##`) for the section headers `Summary`, `New Features`, `Improvements`, and for each individual feature/improvement name. Do not use Heading 1 anywhere in the body — H1 is reserved for the article title (set in the Title field). Note: sections and feature names sit at the same level, so the auto-TOC is a flat list, not nested.
13. **No article title in the body.** Do NOT start the body with an `# Maximizer Cloud – ...` title. The release title is set in the Zendesk article **Title** field (see naming convention below); a body title duplicates it and adds a stray top-level entry to the TOC. The body's first heading is `# Summary`.
14. **Edition and Area on separate rows.** Put `Edition: ...` and `Area: ...` on their own lines with a blank line between them so they render as two separate rows. A single line break between them collapses into one combined string in HTML (`Edition: X Area: Y`).
15. **No "Screenshots" label before images.** Do NOT write a `Screenshots` heading/label or a `Screenshot:` caption prefix before visual content. Place images inline beneath the relevant section with no label or caption prefix.
16. **Image sizing (manual, during content prep).** Resize each image so it is proportionate to the body text — roughly the article content-column width (≈650px max), aspect ratio preserved. Do not insert excessively zoomed-in crops or images that span multiple screens inline.
17. **Article Title field naming convention.** The Zendesk Title field must read `Maximizer Cloud – {{Month}} {{Year}} ({{Year}} M{{Month number}})` — e.g. `Maximizer Cloud – May 2026 (2026 M5)`. Always include the `({{Year}} M{{Month number}})` release number for consistency with prior release articles.
18. **Edition naming convention.** The Loop page uses shorthand; the published article uses full names. Convert: `FSE` → `Financial Services Edition`, `FSE+` → `Financial Services Edition +`, `Base` → `Base Edition`, `Sales Leader` → `Sales Leader Edition`, `All` → `All Editions`. Keep `Business+` exactly as written. Join multiple editions with a comma and space, e.g. `Financial Services Edition +, Business+`. (Area names — `Web` / `Mobile` / `Outlook` — are used as-is.)

---

## TEMPLATE START

<!-- Zendesk article TITLE field (set on the article, NOT written in the body): Maximizer Cloud – {{Month}} {{Year}} ({{Year}} M{{Month number}})  e.g. Maximizer Cloud – May 2026 (2026 M5) -->

Release Date: {{Month DD, YYYY}}

## Summary

{{A concise 2–3 sentence summary covering the main value of the release, the problem it solves, and the overarching benefit to advisors, admins, or sales teams.}}

## New Features

## {{Feature Name}}

Edition: {{Financial Services Edition + / Sales Leader Edition / Base Edition / All Editions}}

Area: {{Web / Mobile / Outlook}}

**What's new**

{{2–3 sentences describing the core functionality and change. Active voice, benefits-first.}}

**Why it matters**

{{1–2 sentences clearly describing user value, workflow improvement, or business outcome.}}

**How it works**

1. {{Step 1}}
2. {{Step 2}}
3. {{Step 3}}

[IMAGE: FeatureName_1]
[GIF: FeatureName_Interaction_1]

{{Link to User Guide, if provided}}

*(Repeat the above block for each new feature)*

## Improvements

## {{Improvement Name}}

Edition: {{Financial Services Edition + / Sales Leader Edition / Base Edition / All Editions}}

Area: {{Web / Mobile / Outlook}}

**What has changed**

{{1–2 sentences describing the specific update. Active voice, concise.}}

**Why it matters**

{{1–2 sentences describing the user impact or improved workflow.}}

**How it works**

1. {{Step 1}}
2. {{Step 2}}
3. {{Step 3}}

[IMAGE: ImprovementName_1]
[GIF: ImprovementName_Interaction_1]

{{Link to User Guide, if provided}}

*(Repeat the above block for each improvement)*

## Fixes
*(Omit this entire section if no fixes are included in this release)*

- {{Edition}} – {{Area}}: {{Short description of fix}}
- {{Edition}} – {{Area}}: {{Short description of fix}}

## Admin & Configuration Updates
*(Omit this entire section if no admin updates are included in this release)*

- {{New admin setting}}
- {{New AI Hub control}}
- {{Updated default behavior}}
- {{New field / schema update}}

If you need assistance, contact [support@maximizer.com](mailto:support@maximizer.com)

## TEMPLATE END

---

## Writing Guidelines Reference

### Tone & Style
- Professional, concise, and user-centered
- Benefits-first — lead with what the user gains, not what changed technically
- No fluff, no hype, no promotional language
- Short paragraphs, scannable formatting
- Active voice throughout
- Avoid repeating the same phrasing across features
- Plain language suitable for advisors, salespeople, and admins

### Consistency Rules
- Normalize vocabulary: always use "What's new," "Why it matters," "How it works," "What has changed" — exactly as written, no bold, no colon
- Ensure parallel structure across all features and improvements
- Use Heading 2 for Summary / New Features / Improvements and for each feature or improvement name (no Heading 1 in the body)
- Always include Edition and Area for every item — no bold on either label, each on its own line (blank line between) so they render as separate rows
- Fix grammar, remove redundancies, unify tone across PM inputs
- Use numbered steps (not bullets) for How it works
- Assign a clear, descriptive title to every feature — avoid vague names like "Update to Settings"
- Feature type drives the label: new capabilities use "What's new", changes to existing behaviour use "What has changed"

### Formatting Rules
- Do not bold Edition, Area, or any section label (What's new, Why it matters, etc.)
- Do not add a Description heading or label
- Do not use horizontal section dividers (no ---)
- Do not bold Release Date
- Do not use emojis in headings
- Do not include empty optional sections
- No "Screenshots" label or caption before images — place visual content inline with no label
- Resize images to be proportionate to body text (≈650px max width, aspect ratio preserved); no excessively zoomed-in crops or full-screen-spanning images
- GIFs are preferred over static screenshots where interaction is being demonstrated
