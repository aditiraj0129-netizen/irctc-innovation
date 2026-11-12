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

## 2-minute pitch

> Every winter, fog delays a train by two hours and a passenger misses their connection at Prayagraj. In that
> moment they have four questions: is my connection really gone, what are my options, how much money can I
> get back, and how long do I have to decide? Today the answers are spread across a status app, a refund
> rule PDF, a TDR form and a call to 139.
>
> **Agla Kadam** answers all four on one screen. It keeps a live picture of your whole journey, every train and
> every change of train, and checks whether *you* can make the change, at *your* walking speed, with a lift if you
> need one. When something breaks, it shows ranked options, the exact money from versioned refund rules, and a
> Rights Clock: the moment your options start disappearing.
>
> Not sure? Ask "what if I wait?" and the same engine recalculates; it tells you which options you would lose.
> Families on two PNRs see one plan that keeps them together, or a clearly labelled split. The plan is saved
> offline, because fog and bad signal come together. You can ask in Hindi, English or Hinglish, by voice.
>
> We built this to be trusted. Every rupee comes from a rule with its version, date and source. A rule that is
> only announced says so. AI is optional: it may explain and understand questions but can never invent a number.
> Passenger reports are shown as unverified and never change your refund. And all data in this prototype is
> simulated, clearly labelled, because we don't have official access yet.
>
> 181 backend and 14 end-to-end tests pass. With authorised NTES and IRCTC data, Agla Kadam can sit inside
> RailOne as the "my journey changed" button. **Know your next step, before the deadline.**

## Strongest innovations

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

## Known limitations

- All railway data is simulated (trains 90xxx). Station codes are real; walking times are invented estimates.
- Seats on alternatives are never checked. The April 2026 refund slabs are announced, not notified.
- The missed-connection TDR deadline comes from a partner help page (marked unverified).
- Resilience score weights are our judgement, not validated against real outcomes.
- Store defaults to in-memory: claims, preferences and reports reset on restart (set `STORE_PATH`).
- Voice input depends on browser support (Chrome/Android work best; many iOS browsers don't).
- Community reports use a simple hashed-reporter count; no moderation or abuse protection.
- One process, one SQLite file: fine for a demo, not for scale.

## Deployment readiness

| Item | Status |
| --- | --- |
| Backend tests | 181 pass |
| E2E tests | 14 pass |
| Production build | builds (`vite build`) |
| Dockerfile / render.yaml | present, **not built or verified in this environment** (no Docker daemon) |
| Live deployment | **not deployed** |
| Secrets | none in code; LLM key only via env (`LLM_API_KEY`), off by default |
| Before going live | build the Docker image locally, deploy on Render, set `STORE_PATH` to a file on a persistent disk if claims must survive restarts, open the app 10 min before judging (free tier sleeps) |
