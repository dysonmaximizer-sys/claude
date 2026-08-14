# Story: Webinar McGill Catch (Focal AI + Maximizer webinar, Aug 19)

**Persona:** Adam (wealth door). **Presenter:** Gabe, during the joint webinar
(recording Fri Aug 14). **Standalone story:** its own household (Halloran
Family — Dan 54, Priya 52, Maya 17), its own manifest, clean removal without
touching walk-in-ready or any other story.

**Aha:** in the meeting John captures with Focal, Dan mentions in passing
that Maya got into McGill (starts next September). The line never makes the
extracted action items. When Gabe asks IQ Boost "What should I follow up on
from today's meeting?", the answer connects that throwaway line to context
already on the Maximizer record: the RESP is still growth-allocated, and an
open task from ~2 years ago says to revisit the allocation when Maya gets
close to university. The audience missed the line too; the record didn't.

**Differentiation beat:** IQ Boost reads more than the transcript — notes,
calls, and tasks on the record. Second question, "Where do the Hallorans
stand on selling the cottage?", surfaces today's transcript AND Priya's
June call.

## What must be true in the data on recording day

1. Halloran household with Dan, Priya, and Maya (17, birthdates seeded).
2. Spring review note ~14 weeks back (believable recent history).
3. Thin two-line note ~5 months back ("Portfolio review w/ Dan + Priya.
   Discussed RESP.") — the "before" contrast against the synced Focal note.
4. RESP allocation note ~2 years back: growth-focused (~80/20), glide-path
   change planned as Maya approaches university.
5. OPEN task ~2 years back: "Revisit RESP allocation when Maya gets close
   to university" (AssignedTo MASTER per rule 10). Deliberately old.
6. Incoming call from Priya ~9 weeks back raising the cottage sale
   (emails cannot be fabricated — the cottage moment is a CALL).
7. The Focal-side meeting (John's account) must include, buried
   mid-conversation and NOT in the action items: "Maya got into McGill,
   she starts next September." Plus agreed action items: cottage valuation
   contact, RESP contribution.

## Accuracy gates

- The payoff is allocation glide path + withdrawal planning. NEVER "unused
  grant room" (CESG ends the year the child turns 17; Maya is 17).
- IQ Boost scope: the client record you're in. No book-of-business claims.
- Confirm with product that IQ Boost draws on tasks and calls, not just
  notes/transcripts, before the recording. The beat rests on it.

## Seeding

- `engine/seed-webinar-mcgill.py` — creates the household, contacts, and
  context records; refuses to run if its own manifest exists.
- Cleanup: `--cleanup` removes only this story's records (household last).
- If the literal EMAIL beat is wanted on screen, send a real email between
  demo mailboxes (Outlook capture); the API cannot fabricate emails.
- Focal side must capture/sync the meeting to the HALLORAN household (John
  or Jerry to confirm how the sync matches the Maximizer record).
