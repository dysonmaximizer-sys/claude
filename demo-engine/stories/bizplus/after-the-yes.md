# Story: After the Yes (Business+ sales door, gated tour 2)

**Viewer:** second person, sales leader at an SMB. **Scene:** a deal
just closed; the handoff usually dissolves into a Slack thread.
**Aha:** one click starts the onboarding workflow on the client record;
tasks land one at a time with owners; the outcome starts the next
process.

## What the engine staged (2026-07-23)

1. **"Client Onboarding" workflow template** - created via API to native
   conventions: 6 sequential tasks (kickoff call -> paperwork -> account
   setup -> training -> 30-day check-in -> confirm + log outcome), day
   offsets, owner by merge expression (AccountManager). This is the
   template the capture's step-3 click starts.
2. **The hero moment:** Total Serve, "Managed services agreement",
   $54K, WON TODAY (David Canter). Onboarding deliberately NOT started -
   the live click IS the capture.
3. **The cohort** (six companies with wins in the last two weeks, for
   step 5's "six in flight"): Briazz (Jul 20, Amanda), Multicerv
   (Jul 17, Douglas), House Works (Jul 16, Michelle), Sistemos (Jul 13,
   Jane), Widdmann (Jul 10, David), Franklin Simon (Jul 8, Jane).

## Lewis's pre-capture clicks (~3 min) - instances are UI-only

Workflow INSTANCES cannot be created via API (fields read-only), so:

1. In Maximizer, open each cohort company below and start the
   **Client Onboarding** workflow on it (six starts total):
   Briazz, Multicerv, House Works, Sistemos, Widdmann, Franklin Simon.
2. Do NOT start anything on **Total Serve** - that click happens live
   in the capture (accuracy gate: the rep starts it; there is no
   deal-won automation and the data must not imply one).
3. Tell Claude "onboardings started" - Claude then backdates one
   instance's active task so exactly one run shows "behind" for the
   step-5 leader view.

## Accuracy gates carried into the data

- No deal-won trigger exists or is implied; the template sits on the
  client record and is started by a person (gate 1).
- Task subjects are structural work, not sent communications: "kickoff
  call", "collect paperwork" - nothing that reads as an auto-sent email
  (gate 2).
- Packaging: Workflows = Business+; this story lives in the Business+
  tenant.

## Refresh

Won dates roll stale in weeks. refresh-story.py does not roll
Opportunity CloseDates (known gap, also flagged on
monday-pipeline-review). For a new recording: reseed the cohort wins,
or ask Claude to re-date them; the workflow template is permanent and
needs nothing.
