# Passenger Decision Model

Module: `backend/app/decide/decision.py`. API: `GET /api/v1/journeys/{id}/decision?priority=`.
Screen: **Decide** tab (`#/decide/<id>`). It is also reached from the journey alert ("What should I do?"), the Disruption Centre and the What-If screen.

**Promise:** PREDICT → DECIDE → RECOVER. The passenger should never have to interpret technical output to decide.

## Screen layout
1. **Header:** "Your connecting journey is at risk." (or the matching status). It shows:
   - the first train and its delay;
   - the expected arrival range and most likely time;
   - the connecting train and its departure;
   - the time available, the time needed and the risk;
   - when the data was last updated, and whether it is fresh.
2. **Recommended next step:** one plain instruction with numbers, plus "why".
3. **What can you do now?** Six cards. Each one shows:
   - what the option means and what happens;
   - the money and the risk;
   - the deadline that matters and the next action.
   - If a card can't be filled, it says **why** ("Live bus data is not connected yet", "The trains on your ticket have already left", "This is a counter ticket: use the counter"). There are never empty boxes; a test checks every card for every demo journey.

| Card | Built from |
| --- | --- |
| Continue current journey | Delay engine range + connection engine (slack at early / likely / late arrival), what to watch |
| Cancel and get a refund | Rules engine `cancellation_refund` for the first ticket whose train hasn't left: class, status, quota, rule id, charge, refund, legal status, **when the refund drops and to how much**, and whether a TDR is relevant |
| Take another train | Recovery engine (direct, one change, nearby station) |
| Travel unreserved | Recovery engine unreserved list + `GUIDE-UNRESERVED` rules |
| Take a bus | Bus provider (demo samples only) |
| Wait for the next service | Next-day trains + Tatkal timing (`GUIDE-TATKAL`) |

4. **Money: act now or wait?** Each row uses the rules engine at that exact time:
   - Cancel now.
   - Wait 15 minutes, then cancel.
   - Wait until the decision point, then cancel. The decision point is the minute before the refund drops, or the time the train reaches the station to watch, whichever comes first, and always before the train leaves.
   - Cancel later, just after the refund drops.
   - Keep the ticket and claim a TDR if needed.
   - Take another train (fare unknown).
5. **Where your money stands:** kept apart on purpose:
   - cancellation refund (estimate);
   - TDR eligibility (an assessment);
   - TDR submitted? ("No — Agla Kadam never files for you");
   - railway approval (unknown);
   - money received (unknown).
6. **Will the delay grow or recover?** Shows the trend, trains ahead (counted and not counted, with reasons), fog, the time the train can win back, quality, missing inputs, and why no percentage is shown.

## Recommendation rules (deterministic, in this order)
1. Live data stale or missing → **check NTES or RailOne, or call 139** (no advice on stale data).
2. Journey has a change of train:
   - Comfortable or Tight → **stay and watch**. "Check at {station}: if it is more than {X} min late, come back."
   - High risk → **stay but prepare**: a named backup train, the same watch rule. If a TDR for a missed connection would return more than cancelling now, the step also says: **"Don't cancel your connecting ticket now."**
   - Unlikely or Not feasible → **book the best alternative** (same day if possible, otherwise next day with Tatkal timing). Then:
     - if the PNRs are linked, **file a TDR for the missed train** by its deadline, "if approved";
     - if not, say plainly that the TDR is **not available** and why. A missed connection does **not** automatically qualify.
3. Single train (or last leg): follow the rules-engine plan.
   - More than 3 h late before departure → **file a TDR before departure**.
   - Waitlisted after the chart or train cancelled → **automatic refund, look at another train**.
   - Otherwise → **travel as booked**, plus "Not travelling any more? Decide by {time}: cancelling before then returns about ₹X". If the delay is near 3 hours: "If it goes over 3 hours, a TDR may be possible".

## Six demo scenarios (simulated, through the real backend)
| PNR | Scenario | What the passenger sees |
| --- | --- | --- |
| 8100000008 | Delay may recover: 40 → 30 → 20 min late | Trend "recovering", connection **Tight**, recommendation **stay and watch at New Delhi (more than 35 min late = change fails)** |
| 8100000009 | Delay getting worse: 0 → 10 → 20 min, two late trains just ahead on Agra–New Delhi | Congestion **moderate** (90723, 90725 counted; 90724 *opposite direction* and 90729 *too far ahead* not counted). **High risk**, stay but prepare; don't cancel (₹0 vs TDR ₹645 if approved) |
| 8100000010 | Fog: dense fog warning on Agra–New Delhi (an expired morning warning is ignored) | Wider range (late end +30 min), **High risk**, the weather evidence and its limits |
| 8100000011 | Connection missed: 75 min late | **Not feasible**. Shows the night train 90823, a Nizamuddin option (90811), unreserved, sample buses, next day. TDR ₹645 if approved, by its deadline |
| 8100000012 | Financial decision: train 2 h 30 m late before departure | Cancel now ₹660 (50% slab, announced rule) vs ₹0 after 01:30; "decide by 01:29"; a TDR may be possible only if the delay goes over 3 h |
| 8100000013 | Next-day recovery: arriving 4 h+ late at night | No same-day train left. Recommends 90801 tomorrow 07:40; Tatkal opened at 10:00 the day before (AC), never guaranteed |

## AI's role
The Journey Copilot calls the same engines through read-only tools:
- `predict_delay`
- `compare_decisions`
- `find_alternatives`
- `check_unreserved`
- `find_bus`
- `next_day_options`

It then explains the result in English or Hindi. It cannot invent trains, fares, seats, probabilities or refunds:
- any AI rewording that adds a number is rejected (tested with a fake AI that invents train 90999);
- it cannot book, cancel or file anything.
