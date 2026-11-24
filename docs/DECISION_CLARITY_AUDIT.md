# Decision clarity audit (24 Nov 2026)

**Question asked:** when a journey is disrupted, does Agla Kadam tell the passenger *what to do next*?
**Short answer before this upgrade:** it gave correct facts, but too often left the passenger to work out the decision.

How the audit was done:
- Read every backend module: What-If simulator, planner, rules, graph, twin, Copilot.
- Called the APIs for all 7 demo journeys.
- Ran a script that opened all 12 journey pages × 5 journeys in Chrome and listed every section, table cell or field that was empty, "—", "0" or "…".

## 1. Why sections looked blank or repeated

| # | Where | What the passenger saw | Root cause |
| --- | --- | --- | --- |
| B1 | What-If, compare table | "Transfer risk: —", "Deadline: —", "Rights: —" in many cells (17 empty cells on the main demo, 18 on the normal journey) | The table printed `null` fields as a dash, with no reason given (e.g. "no change of train in this option", "no deadline because you keep your ticket") |
| B2 | What-If, "Take another train" / "Route with one change" | A grey card with only a code like `NO_ALTERNATIVE_NEEDED_OR_FOUND` | Not-applicable outcomes carried a code, not an explanation or a next step |
| B3 | What-If, four cards | "Act now", "Wait", "Connection is missed" and "Take another train" showed **the same train, the same arrival and the same ₹645** | Each scenario independently picked "the best plan", which was often the same plan. Nothing said "these lead to the same result" |
| B4 | What-If, "Cancel the ticket now" | "₹645 lost · Medium" with no explanation | The simulator silently cancelled **only the next unused leg** (Delhi → Chandigarh, 3 h before departure → ₹0 under the announced 2026 slab). It never said *which* ticket, never said "don't cancel: a TDR may return ₹645 if you miss the connection", and never showed when the refund would change |
| B5 | What-If, "Changes 0" on an alternative train | Looked like no change was needed | `changes` counted changes *inside the new plan*, not "you change from your booked train to a new one" |
| B6 | Every What-If card | "Information confidence: Medium" | Almost every outcome had one of the same reasons (simulated data, refund needs approval), so the label carried no information |
| B7 | Wallet, rule details | Empty fields (the scan found 4–8 per page) | False alarm: they are inside a closed `<details>` and fill when opened. No change needed |

## 2. Buttons that do nothing
None found. Every `<button>` in `frontend/src` has a click handler or submits a form; the scan found no dead links.
The weak spot was different: some buttons led to a page that did not answer the question (e.g. "See options" on a
calm journey showed "Travel as booked" with no explanation of why that is safe).

## 3. Outputs with technical facts but no next step

| Output | Problem |
| --- | --- |
| Connection check | One subtraction: *expected arrival + 30 min ≤ departure*. It never said how sure we are about the arrival time, whether the delay is growing, or what to watch next |
| Delay | The latest delay was treated as fixed until arrival. The "delay gets worse" slider used a number the passenger picked, not evidence |
| Alternatives | Only reserved trains from the timetable. No unreserved option, no bus, no next-day option, no nearby station, and no "data source / last updated" per result |
| Refund | Correct amounts, but no "cancel now vs. later" comparison and no warning when cancelling would throw away a better claim (TDR) |
| Recommendation | Explained *why the top plan ranks first*, but didn't give one plain instruction such as "Stay on your train. Check again at Agra at 03:25. If it is more than 40 min late there, book train 90803." |

## 4. Data gaps (honest)

- **No authorised live data:** no official running status, seat availability or fares for alternative trains, and no bus schedules.
- **No historical delay data:** so no ML model can be trained or calibrated.
- **IMD weather APIs need IP whitelisting and acceptance of IMD terms**, applied for through IMD's request form.
  - We have not been whitelisted, so real IMD data cannot be used.
  - Weather therefore runs on clearly labelled simulated warnings, and only in demo mode.

## 5. What changed as a result (this upgrade)

| Finding | Fix |
| --- | --- |
| B1–B6, section 3 | New **Decide** screen backed by `GET /api/v1/journeys/{id}/decision`. It has 6 option cards (continue, cancel, another train, unreserved, bus, wait / next day). Every card shows: meaning, what happens, money, risk, deadline and next action. If data is missing, the card says *what* is missing. There is one "Recommended next step" |
| Delay treated as fixed | **Delay Propagation Engine**: own-train trend, shared-section congestion indicator, fog warnings. It gives an arrival **range** and a risk band, never a fake probability |
| Single subtraction | **Connection Risk Engine**: checks the whole arrival range against the transfer time for the passenger's needs. Result is Comfortable / Tight / High risk / Unlikely / Insufficient information |
| Alternatives | **JourneyRecoveryEngine**: direct, one-change, nearby-station, unreserved, bus (demo samples only) and next-day results, each labelled with exactly one result type, ranked by transparent weights |
| Refund | **Decision comparison**: cancel now, wait 15 min, wait until the decision point, cancel later, alternative. Each uses the rules engine, with the exact time the refund changes |

The old What-If screen is kept and still works (its tests are unchanged). It now links to the Decide screen.
