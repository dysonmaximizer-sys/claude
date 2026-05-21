# Maximizer Release Notes — Output Template

> This template is the authoritative format for all Zendesk release notes articles.
> Do not deviate from the structure, headings, labels, or formatting rules.
> Omit optional sections if no relevant content exists — do not leave them empty.

---

## FORMATTING RULES (MANDATORY — READ FIRST)

These rules override any default formatting behaviour. Follow them exactly on every output.

1. **No bold on Edition or Area labels.** Write `Edition: All` not `**Edition:** All`
2. **Bold on content section labels only.** Write `**What's new**`, `**Why it matters**`, `**How it works**`, `**What has changed**`. Do NOT bold `Edition`, `Area`, `Screenshots`, or `Release Date`.
3. **No Description label.** Do not insert a `Description` or `**Description**` heading between Area and What's new
4. **No horizontal section dividers.** Do not use `---` between features, improvements, or sections
5. **No bold on Release Date.** Write `Release Date: Month DD, YYYY` not `**Release Date:**`
6. **Numbered steps in How it works.** Use `1.` `2.` `3.` — not bullet points (`-`)
7. **No emojis in any heading**
8. **Omit How it works entirely** if no meaningful steps exist for a feature
9. **Omit optional sections entirely** (Fixes, Admin & Configuration Updates) if no content applies — do not leave them empty or with placeholder text
10. **Feature type determines label:** New Features use `What's new` — Improvements use `What has changed`

---

## TEMPLATE START

# Maximizer Cloud – {{Release Version}}

## Table of Contents
- [Summary](#summary)
- [New Features](#new-features)
  - [{{Feature Name 1}}](#feature-name-1)
  - [{{Feature Name 2}}](#feature-name-2)
- [Improvements](#improvements)
  - [{{Improvement Name 1}}](#improvement-name-1)
- [Fixes](#fixes) *(omit if empty)*
- [Admin & Configuration Updates](#admin--configuration-updates) *(omit if empty)*

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

Screenshots

[Screenshot: FeatureName_1]
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

Screenshots

[Screenshot: ImprovementName_1]
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
- Always include Edition and Area for every item — no bold on either label
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
- GIFs are preferred over static screenshots where interaction is being demonstrated
