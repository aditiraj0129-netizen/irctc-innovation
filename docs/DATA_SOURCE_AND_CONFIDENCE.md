# Data sources and confidence

| What the passenger sees | Where it comes from today | Shown as | Real source later |
| --- | --- | --- | --- |
| Train running delays (own train) | Simulated scenario readings | "Simulated" strip, source + time on every reading, "fresh" or "out of date" (15 min) | NTES / CRIS (authorised) |
| Other trains' delays (congestion) | Simulated `network_events` | "Risk indicator, not proof" | NTES / CRIS |
| Route sections, distances, recovery allowances | `data/network.yaml`, simulated | "Simulated route-section model" | Working timetable, history |
| Fog warnings | Scenario file, demo mode only | Source text "SIMULATED_DEMO (IMD-style warning, not real)" | IMD APIs after IP whitelisting |
| Timetable and alternatives | `data/timetable.csv` (trains 90xxx are invented, station codes real) | Result type `DEMO_SIMULATED` | IRCTC/CRIS timetable |
| Seat availability | **Not connected** | "Seats: not checked" on every option | IRCTC (authorised partner) |
| Fares of new tickets | **Not connected** | "Fare: not known (check IRCTC)" | IRCTC fare enquiry |
| Bus timetables and fares | Demo samples only | "Sample only · not a real fare" | State transport operators |
| Refund / TDR amounts and deadlines | Versioned rules YAML, cited | "Estimate", "if approved", "rule announced, not yet confirmed" where true | Gazette / Railway Board circulars |
| Tatkal timing | `GUIDE-TATKAL` (PIB/AIR, June 2025) | "Never guaranteed", "Aadhaar OTP needed" | IRCTC |
| Unreserved rules | `GUIDE-UNRESERVED` (SER passenger guidance PDF) | General guidance | Railway commercial manual |

## Confidence words used (and what they mean)
- **Risk bands** (lower / moderate / high / insufficient evidence): from documented rules, *not* probabilities.
- **Connection** (comfortable / tight / high risk / unlikely / not feasible / insufficient information): from the arrival range against the time needed.
- **Evidence quality** (good / limited / poor):
  - good = at least 3 fresh readings and nothing missing;
  - poor = no fresh data.
- **Probabilities:** never shown. `probability = null`, because no model has been trained or calibrated on real history (`EVALUATION_STATUS = NOT_EVALUATED_NO_HISTORICAL_DATA`).

## Rules for staying honest (each has a test)
- Stale data is never shown as live, and the app gives no advice on it.
- Seats, fares and timetables are never invented. Only demo bus samples have a fare, and it is labelled as not real.
- A refund is never promised; a TDR is a request.
- A missed connection is not assumed to qualify for a refund: unlinked PNRs give "not eligible".
- A delayed train ahead is not taken as the cause of our delay. It counts only if it is on the same section, in the same direction, close ahead, late, and recently observed.
- A fog warning counts only on a section ahead and only while it is valid.
