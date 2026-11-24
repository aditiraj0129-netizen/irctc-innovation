# Product audit (24 Nov 2026)

Method: every demo journey was opened on a phone-sized and a desktop screen, in English and Hindi, and walked
through Overview → Decide → Station → Disruption → Options → What-If → Wallet → Copilot. Numbers were checked
against the API. All data is simulated.

## 1. Passenger scenarios checked (15)

| # | Scenario | Demo | Result before | Now |
| --- | --- | --- | --- | --- |
| 1 | Normal journey, nothing wrong | PNR …01 | Works | Works; Station tab shows the honest "no station map / live platform unavailable" state (E2E 29) |
| 2 | Train > 3 h late, TDR window | …02 | Works | Works |
| 3 | Family waitlisted after chart | …03 | Works | Works |
| 4 | Missed connection in fog | …04 | Works | Works |
| 5 | Family group on two PNRs | …05 + …06 | Works | Works |
| 6 | Connected journey Bhopal → Delhi → Chandigarh | …07 | Works; **no platforms anywhere** | Station tab: scheduled platforms only, result capped, passenger can enter the board platform |
| 7 | Delay recovering | …08 | Works | Works |
| 8 | Delay worsening | …09 | **Overview said "all clear" while Decide said "at risk"** | Fixed: Overview and Disruption Centre show the Decide outlook |
| 9 | Fog ahead | …10 | Works | Works |
| 10 | Connection already missed | …11 | Works | Works |
| 11 | Cancel now vs later | …12 | Works | Works |
| 12 | Next-day recovery | …13 | Works | Works |
| 13 | Tight change at a big station, which platform, how far | — | **Not possible** | PNR …14: platforms with status, walk, Possible but tight, "Prepare to get off" |
| 14 | Platform changed at the last minute; needs lifts | — | **Not possible** | …14: platform change recalculates; step-free → High risk, lift status unknown |
| 15 | "I'm at the station, where is the exit / washroom / metro?" | — | **Not possible** | Stations screen: search + route at NDLS, HWH, CSMT |

## 2. Bugs and problems found

| Bug | Fix |
| --- | --- |
| Overview and Disruption Centre used only the current delay, so they could say "all clear" while Decide said "at risk" | Both now show the Decide outlook (E2E test 31) |
| What-If showed choices with exactly the same result as "Act now" with no hint | Marked: "Same result as 'Act now' — this choice doesn't change anything" (E2E test 31) |
| No platform information anywhere | Platform service with 5 statuses + unavailable message |
| No station navigation | Station graph, route engine, Station screens |
| Station map: labels overlapped, platforms drawn at half length | Fixed scale and label placement |
| QR-style link did not update the location on the same screen | Fixed (E2E test 30) |
| Directions said "Walk along Platform 16 towards Platform 16" | Fixed (backend test added) |

## 3. Real vs simulated

Real: refund/TDR rules (versioned, cited), public station facts (cited). Simulated: trains, delays, platforms,
platform changes, seat availability, buses. Estimated: walking times. Unavailable: live platform feed, lift status,
live NTES running status, IMD weather.

## 4. Unresolved

- Station geometry is schematic; only 3 stations are mapped.
- No live platform source; real feasibility depends on one.
- The older What-If screen still overlaps with Decide; it now links to Decide and marks repeated results, but a merge is a product decision.
- Walking speeds are general estimates, not measured at these stations.
