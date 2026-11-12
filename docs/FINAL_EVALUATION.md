# Final evaluation of the submission (strict judge view)

Reviewed: the 8-slide deck, `FINAL_VIDEO_SCRIPT.md`, `LIVE_DEMO_SCRIPT.md`, README and the running app.
Every number on the slides was checked against the code, the test run or the cited source.

## Score

| Criterion | /10 | Why | What would raise it |
| --- | --- | --- | --- |
| Problem clarity | 9 | One concrete night-time story; six real decision questions; strong one-line takeaway | — |
| Passenger impact | 7 | Groups are clear, but impact isn't measured (no official data on missed connections / deadlines; we say so) | Pilot numbers: time to decide, money kept |
| Innovation | 7 | Rights Clock + What-If + personal transfer check is a new combination; status, alternates and TDR filing exist elsewhere | Lead harder with "when your options disappear" |
| Solution quality | 8 | Working, integrated, honest labels, explains "why #1" | Fewer screens; simpler "More" menu |
| Technical implementation | 9 | 192 + 15 tests, deterministic rules engine, versioned rules, security audit | — |
| Feasibility | 6 | Real use needs authorised NTES/IRCTC and seat data the team doesn't have | A written data-access plan / letter of intent |
| User experience | 7 | Mobile-first, Hindi, voice; never tested with real passengers | 5–10 user tests before finals |
| Validation | 4 | Only technical validation; zero passenger feedback (stated honestly) | **Biggest gap**: even 10 short user tests would lift this to 6–7 |
| Scalability | 5 | Single process, in-memory store; architecture is ready for a database but not built | Postgres + stateless API + caching plan |
| Presentation quality | 8 | Clean, consistent, real screenshots, sources on slides | A short screen recording instead of static screens on slide 5 |
| **Total** | **70 / 100** | | Realistic with user tests + public demo link: **~77–80** |

## Weakest slides and what was improved

1. **Slide 6 (feedback):** there is no passenger feedback. Fabricated reviews were *not* added; that would be
   misleading to judges and risky if checked. Instead it shows four honest columns (tested / reviewed / checked /
   not validated) with a concrete test plan. **To improve before the deadline:** ask 5–10 friends or family who
   travel by train to try the fog scenario. Write down what they actually said and update slide 6 (real quotes only,
   with their permission).
2. **Slide 4 (scale):** the exact problem has no official statistic. The slide now uses three official numbers plus
   "what nobody measures yet", rather than inventing a market size.
3. **Slide 5 (prototype):** first render had a 4th screenshot running off the slide and a two-line title; fixed (3
   screenshots, one-line title, shorter architecture labels). Found and fixed a real app bug while capturing it:
   the "Why this is first" list was laid out sideways because of a CSS class clash.
4. **Slide 1:** the official template needs UID, team name and college. Only you have these; the fields are marked.

## Consistency check (deck ↔ script ↔ demo ↔ README)

| Item | Deck | Script | Demo | README |
| --- | --- | --- | --- | --- |
| Main scenario: fog, Prayagraj, 06:15 connection | Slide 2 | 0:00 | Steps 1–2 | Demo table #4 |
| ₹455 if approved, decide by 09:15 | Slide 5 screenshot | 0:55 | Step 3 | Demo table #4 |
| "Options lost by waiting" at 7 h | Slide 5 screenshot | 0:55 | Step 5 | DEMO_AND_PITCH |
| 192 backend + 15 E2E tests | Slide 6 | 1:20 | — | Tests section |
| Simulated data, no live integration | Footer + slide 5/6 | 1:20 | Intro | Top warning |
| No passenger testing yet | Slide 6 | 1:20 | — | Known limitations |
| Roadmap 3 weeks / 3 months / 12 months | Slide 7 | 1:31 | — | — |

## Competitors (only verified, public capabilities — see `DEMO_AND_PITCH.md` for sources)

RailOne (official super-app: booking, PNR, live status, refunds, Rail Madad), NTES (running status), AskDISHA 2.0
(voice/chat booking and refund status in English, Hindi, Hinglish), ConfirmTkt/ixigo (waitlist prediction,
alternates, a paid "Alternate Travel Plan" add-on). We did not find, in their published features, a per-passenger
deadline view ("decide by") combined with a what-if simulator and transfer feasibility. That is a claim about what we
found, not proof that it doesn't exist.
