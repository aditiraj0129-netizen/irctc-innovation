# Demo, pitch and comparison

## Demo scenarios

| # | PNR | Scenario | Key expected output |
| --- | --- | --- | --- |
| 1 | 8100000001 | Normal journey | Calm; travel as booked; cancel preview ₹1,960; resilience score shown |
| 2 | 8100000002 | Delay around 3 hours | TDR plan ₹1,180 if approved, act by 17:10; set delay to 170 → TDR disappears; Wallet shows "You can file" |
| 3 | 8100000003 | Family waitlisted after chart | Automatic refund ₹2,140; alternative 90305 "seats not checked"; What-If says cancelling is not needed |
| 4 | 8100000004 | **Fog: missed connection (main demo)** | See flow below |
| 5 | 8100000005 + 8100000006 | Family on two PNRs | "Different ticket status"; everyone together on 90305 (₹4,830 back, ₹1,770 lost) vs split (₹3,180 back), labelled |
| 6 | 8100000004 + prefs | Senior, step-free | Transfer needs 40 min at Patna instead of 30; badges and twin change |
| 7 | 8100000002 + clock +40 min | Stale data | No advice, official channel only; assistant refuses to advise |
| 8 | any | No AI key | Everything works; explanations from templates, assistant from keywords |

### Main demo flow (connecting journey, about 2 minutes)

1. **Detect** – open PNR 8100000004. Alert: "Your connection at Prayagraj Jn is at risk."
2. **Twin** – "Journey broken: act now". Leg 2 "Likely missed". Transfer box: "Change not possible · −1h 25m to spare · must reach by 05:45".
3. **Rights** – Options: top plan 90205 + 90601, arrive 20:30, ₹455 back if approved, deadline marked "not yet officially confirmed".
4. **Rights Clock** – decide by 09:15.
5. **Why** – "Arrives earlier · every change of train is possible"; "If you wait 30 min: nothing changes".
6. **What-If** – drag "How long you wait" to 7 h → "Options lost by waiting". Show "Cancel the ticket now: ₹455 lost".
7. **Wallet** – rule version, effective date, source, "still uncertain"; mark "I filed it"; download summary.
8. **Ask** – type or say "Meri train late hai, ab kya karun?" → answer with the same numbers and rule id; read aloud.
9. **Offline** – save card, switch on airplane mode → "You are offline. Showing your saved card." with 139 / 182 / 1930 / 112.

## 5-minute live demonstration script

Before going on stage: open `#/presenter` on the laptop (enter the presenter token if set), press Reset for
`missed_connection`, `edge_three_hours` and `family_confirmed`. Save the offline card on the phone once.

| Time | Screen (phone) | Say |
| --- | --- | --- |
| 0:00–0:30 | Home → "Fog: connection at Prayagraj" | "A fog delay. Two linked PNRs. Will I make my connection?" Point at the yellow "Simulated data" strip. |
| 0:30–1:15 | Overview (twin) | "Journey broken: act now. My change at Prayagraj needs 30 min; I'm 85 min short. These transfer times are simulated estimates." |
| 1:15–2:00 | Options | "Ranked options. Top: 90205 + 90601, arrive 20:30, ₹455 back if approved, decide by 09:15. Here's why it's first, and what happens if I wait." Show the Rights Clock. |
| 2:00–2:45 | What-If | Drag "How long you wait" to 7 h: "Options lost by waiting." Show "Cancel now: ₹455 lost". "Same rules engine, nothing invented." |
| 2:45–3:20 | Wallet | Open the rule: version, source, effective date. "If a rule is only announced, we say so." Tap "I filed it". |
| 3:20–3:50 | More → Ask | Say or type "Meri train late hai, ab kya karun?" → same numbers, rule id. Tap Read aloud. |
| 3:50–4:20 | More → Family group (switch to `family_confirmed`) | "Two confirmed, two waitlisted. Together option first; split options clearly labelled." |
| 4:20–4:45 | Offline card + airplane mode | "Fog and bad signal come together: saved, masked, time-stamped, with 139/182/1930/112." |
| 4:45–5:00 | Presenter: set `edge_three_hours` delay to 170 | "Delay drops under 3 hours → the TDR right disappears live. Rules, not guesses." |

Backup: a screen recording of the same flow, in case of network trouble.

## 2-minute pitch

> Every winter, fog delays a train and a passenger misses their connection at Prayagraj. In that moment they have
> four questions: is my connection really gone, what are my options, how much money can I get back, and by when
> must I decide? Today the answers are spread across a status app, refund-rule PDFs, a TDR form and a call to 139.
>
> **Agla Kadam** answers all four on one screen. It keeps a live picture of your whole journey and checks whether
> *you* can make each change of train, at your walking speed, with a lift if you need one. When something breaks,
> it ranks your options, calculates the money from versioned refund rules, and shows a Rights Clock: the moment
> your options start disappearing. Ask "what if I wait?" and the same engine recalculates.
>
> Families on two PNRs get one plan that keeps them together, or a clearly labelled split. The plan is saved for
> offline use, and you can ask in Hindi, English or Hinglish, by voice.
>
> We built it to be trusted. Every rupee shows its rule, version, date and source. A rule that is only announced is
> labelled as not yet confirmed. AI is optional and can never invent a number. Passenger reports are marked
> unverified and never change your refund. And every train in this prototype is simulated, clearly labelled.
>
> 192 backend and 15 end-to-end tests pass. With authorised NTES and IRCTC data, Agla Kadam can become the
> "my journey changed" button inside RailOne. **Know your next step, before the deadline.**

## Strongest three differentiators

1. **Deadline-aware decisions (Rights Clock + What-If):** shows *when* each option and refund disappears, from one deterministic rules engine.
2. **Personal transfer feasibility:** each change of train is judged for this passenger (speed, step-free), and impossible options are removed.
3. **Rule provenance and honesty:** every amount carries rule id, version, effective date, legal status and source; unconfirmed rules are never shown as certain.

## Other innovations

1. **Rights Clock + What-If on one deterministic engine** – shows *when* options disappear, not just what they are.
2. **Personal transfer feasibility** – the change of train is judged for this passenger (speed, step-free), and impossible options are removed.
3. **Rule provenance everywhere** – version, effective date, legal status, source and unresolved conditions on every amount.
4. **Group-aware recovery** – one decision for a family split across PNRs, together vs split clearly labelled.
5. **Offline-first honesty** – a saved, masked, time-stamped snapshot that never pretends to be live.

## Features that need official railway data before real use

| Feature | Needs |
| --- | --- |
| Digital Twin, detector | Authorised live running status (NTES / CRIS) and chart status |
| Alternatives, What-If | Official timetable feed and **seat availability** (we never claim seats) |
| Transfer intelligence | Real platform layouts, walking times, lift/ramp status per station |
| Rights Wallet | Official refund rules (notification for the April 2026 slabs), TDR status from IRCTC |
| Family Guardian | Linked group bookings from IRCTC |
| Community reports | Moderation and abuse protection at scale |
| Assistant voice | Testing with real users, more languages |

## Comparison with existing apps (verified public capabilities only)

| App | What it verifiably does (sources below) | What Agla Kadam adds |
| --- | --- | --- |
| **RailOne** (CRIS, official) | One app for booking, PNR, live train status, Rail Madad and refund requests for cancelled or missed journeys; the Ministry says its waitlist confirmation prediction improved from 53% to 94% accuracy | A disruption decision layer: transfer feasibility, ranked recovery options, Rights Clock, what-if and rule provenance. Designed to plug *into* RailOne, not replace it |
| **NTES** (official) | Live running status; now also available inside RailOne | Turns status into "what should I do and by when" |
| **AskDISHA 2.0** (IRCTC) | Chat and voice in English, Hindi, Hinglish (and Gujarati, per reports) for booking, PNR, cancellation and refund status | Answers disruption questions ("should I wait?") from computed rights and options, refuses to advise on stale data |
| **ConfirmTkt / ixigo** | Waitlist prediction, "Alternates" (other trains / boarding points), Alternate Travel Plan (formerly Travel Guarantee): a **paid, opt-in** add-on giving extra refund value as coupons if a ticket stays waitlisted; Assured free cancellation | Free, rule-based rights for every ticket; deadlines; family and transfer awareness; no paid insurance product |

We did **not** verify, and do not claim, anything about these apps' internal features beyond the sources below.

Sources:
- RailOne: [Business Today](https://www.businesstoday.in/india/story/railone-app-launched-key-features-for-ticket-booking-journey-planning-others-482593-2025-07-01), [App Store listing](https://apps.apple.com/in/app/railone/id6473384334), [Times Bull on prediction accuracy](https://www.timesbull.com/railone-mobile-app-know-whether-your-train-ticket-will-get-confirmed-or-not), [Curly Tales on merged apps](https://curlytales.com/indian-railways-introduces-railone-app-with-all-in-one-travel-features-know-the-details-here)
- AskDISHA 2.0: [Business Standard](https://www.business-standard.com/finance/personal-finance/askdisha-2-0-book-cancel-track-train-refunds-with-irctc-s-new-ai-125053000593_1.html), [CoRover](https://corover.ai/askdisha)
- ConfirmTkt / ixigo: [ConfirmTkt Alternate Travel Plan](https://www.confirmtkt.com/alternate-travel-plan), [ConfirmTkt SOP (paid, opt-in)](https://confirmtkthelp.freshdesk.com/support/solutions/articles/44002617339-travel-guarantee-updated), [ixigo Travel Guarantee](https://ixigo.com/travel-guarantee), [ConfirmTkt App Store](https://apps.apple.com/app/id1037974704)

## Railway rules verification table (as of 13 Nov 2026)

| Rule id | What it does | Category | Effective | Source (strength) | Status in app |
| --- | --- | --- | --- | --- | --- |
| RS-REG-2015 | Old slabs: >48 h flat, 48–12 h 25%, 12–4 h 50%, <4 h none | Regular | 12 Nov 2015 – 31 Mar 2026 | IRCTC rules PDF hosted by a third party | NOTIFIED; `last_verified` empty → shows "source not yet checked" |
| RS-REG-2026-APR | New slabs: >72 h flat, 72–24 h 25%, 24–8 h 50%, <8 h none | Regular | 1 Apr 2026 (phased to 15 Apr) | Govt publication *New India Samachar* (PIB), Apr 2026; media reports of the Minister's announcement. **Gazette text not found** | **ANNOUNCED** → "Estimate: rule not yet confirmed" |
| RS-VBS-AB2-2026 | Vande Bharat Sleeper / Amrit Bharat II: >72 h 25%, 72–8 h 50%, <8 h none | VBS / AB-II only | 16 Jan 2026 | Gazette G.S.R. 41(E) of 16 Jan 2026 (as reported) | NOTIFIED; never applied to other trains |
| TDR-LATE-3H | Train > 3 h late, not travelled → full fare, TDR before actual departure | Regular | 12 Nov 2015 | Refund Rules 2015, Rule 13(1) (statute text via Indian Kanoon) | NOTIFIED; always "if approved" |
| TDR-LATE-3H-VBS | Same for VBS | VBS | 2026 | not confirmed | NEEDS VERIFICATION → app says "check official channel" |
| AUTO-TRAIN-CANCELLED | Train cancelled → automatic full refund (e-ticket) | Regular | 2015 | 2015 rules; e-ticket terms | NOTIFIED |
| AUTO-WL-DROPPED | WL e-ticket after chart → auto refund minus ₹60 clerkage per passenger | Regular | 2015 | e-ticket terms copy | NOTIFIED (clerkage source should be re-checked) |
| TDR-MISSED-CONNECTION | Linked PNR, missed because first train late → TDR | Regular | 2019 | 2019 announcement (media); **deadline (3 h after arrival) only from a partner help page** | deadline shown as "not yet officially confirmed" |

No refund is ever called guaranteed. Every TDR amount says "if approved".

## Deployment readiness checklist

| Item | Status |
| --- | --- |
| Backend tests (192) / E2E (15) / type-check / build | ✅ pass |
| Health check `/api/health` used by render.yaml | ✅ |
| Secrets only in environment (`LLM_API_KEY`, `DEMO_TOKEN`), `.env` git-ignored | ✅ |
| Path traversal closed, security headers, input validation (422), rate limit (429) | ✅ tested |
| Real client IP behind proxy (`--proxy-headers`) | ✅ configured, ⚠️ not tested on Render |
| Presenter protected (`DEMO_TOKEN`) | ✅ tested; ⚠️ set it in the Render dashboard |
| Docker image builds | ⚠️ not verified (no Docker daemon here) → run `docker build -t agla-kadam .` on the Mac |
| Deployed URL | ❌ not deployed |
| Persistent storage | ⚠️ in-memory by default (fine for a demo) |
| Simulated data labelled on every screen | ✅ |

## Honest competition score (strict judge)

| Criterion | Score /10 | Why it may lose points | What would raise it |
| --- | --- | --- | --- |
| Problem relevance | 9 | — | Real passenger quotes/survey numbers |
| Originality | 7 | Pieces exist elsewhere (status, alternates, TDR) | Show the Rights Clock as the headline idea |
| Technical depth | 8 | — | — |
| Feasibility | 6 | Needs authorised NTES/IRCTC/seat data that a student team doesn't have | Clear integration plan with RailOne/CRIS APIs |
| User experience | 7 | Many screens; never tested with real passengers | 5-user test, simplify "More" |
| Social impact | 7 | Impact not measured | Estimate passengers affected by fog/missed connections |
| Reliability & trust | 8 | Two rule sources still weak | Find Gazette text for 2026 slabs and the missed-connection deadline |
| Scalability | 5 | One process, SQLite in memory | Postgres + stateless API; caching |
| Demonstration quality | 6 | Not deployed; no video yet | Deploy, record a clean 5-min video |
| Competitive differentiation | 6 | RailOne/AskDISHA/ixigo cover parts | Lead with deadline + transfer feasibility, which we did not find in their published features |
| **Total** | **69 / 100** | | Deploying, user-testing and verifying the two weak rules could realistically reach ~78–80 |

## Known limitations

- All railway data is simulated (trains 90xxx). Station codes are real; walking times are invented estimates.
- Seats on alternatives are never checked. The April 2026 refund slabs are announced, not notified.
- The missed-connection TDR deadline comes from a partner help page (marked unverified).
- Resilience score weights are our judgement, not validated against real outcomes.
- Store defaults to in-memory: claims, preferences and reports reset on restart (set `STORE_PATH`).
- Voice input depends on browser support (Chrome/Android work best; many iOS browsers don't).
- Community reports count one reporter per network address (people on the same Wi-Fi count as one); no moderation.
- One process, one SQLite file: fine for a demo, not for scale.

