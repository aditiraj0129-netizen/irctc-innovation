# Journey Recovery Engine

Module: `backend/app/recover/engine.py`. API: `GET /api/v1/journeys/{id}/recovery-options?priority=`.

**Goal:** practical ways to still reach the destination when the booked journey fails or is at risk.

## Where the search starts
- **Change of train at risk or broken:**
  - Search from the change station.
  - Start time = likely arrival there + the transfer time the passenger needs.
  - The booked connecting train is excluded.
- **Single train late, cancelled or not confirmed:** search from the boarding station, starting 15 minutes from now.
- **Everything is fine:** the same search runs as a **backup** ("if things change, here is your plan B").

## What it searches (all from the timetable provider, today the simulated timetable)
1. **Direct trains.**
2. **One-change trains.** Each change of train is checked with the same transfer engine. Impossible changes are dropped.
3. **Nearby stations** (`network.yaml`, e.g. New Delhi ↔ Hazrat Nizamuddin, about 40 min by metro or taxi, an *estimate*). The trip across the city is shown as its own step.
4. **Unreserved (General) travel.** Same-day trains whose every train has General coaches. Each one states:
   - a separate unreserved ticket is needed;
   - the current reserved ticket is not valid on it;
   - travel only in General coaches;
   - seats are not guaranteed.
   Chair-car-only trains are never offered.
5. **Buses.**
   - A `BusProvider` interface.
   - In demo mode, `DemoSampleBusProvider` gives **SAMPLE** buses labelled "not a real timetable / not a real fare".
   - Otherwise `NoBusProvider` → the card says "Live bus data is not connected yet".
6. **Next-day trains.** Services on a later day from 04:00. Each one shows:
   - when Tatkal opens for that run (10:00 for AC classes, 11:00 for non-AC, one day before);
   - "already open" or "not open yet";
   - "Aadhaar OTP needed";
   - "never guaranteed".
   Source: PIB / All India Radio, June 2025 (`GUIDE-TATKAL` in the knowledge base).

Duplicates are removed. **Dominated** options are removed too. Example: "train A then change to train B" is dropped when you could simply take train B all the way, because it leaves no earlier, arrives no later and has fewer changes.

## Exactly one result type per option
`CONFIRMED_SCHEDULE`, `LIVE_RUNNING`, `CONFIRMED_AVAILABILITY`, `AVAILABILITY_UNAVAILABLE`, `ESTIMATED_ALTERNATIVE`,
`DEMO_SIMULATED`. With the simulated providers, every result is `DEMO_SIMULATED`. Separately, every option also carries:
- `seat_availability = UNKNOWN_NOT_CONNECTED` (or "no seat reservation" for unreserved travel);
- `fare_status = NOT_AVAILABLE` (or `SAMPLE_NOT_REAL` for demo buses);
- `data_source` and `last_updated`.

## Ranking (transparent points; lower is better)

| Part | Points (priority "reach soonest") |
| --- | --- |
| Arrives later than the earliest option | 1.0 per 30 min |
| Changes of train | 0.5 each (2.0 when "fewest changes" is chosen) |
| Change risk | tight 0.5, high risk 1.5 (×2 for "least risk") |
| Nearby station (cross the city) | 0.5 |
| Bus (road trip, sample data) | 1.0 |
| Step-free passenger changing at a hard station | 1.0 |
| Seats unknown, fare unknown | 0 (the same for every option, so they don't change the order; shown so nobody thinks they were checked) |

Every option returns its `score_parts`. The app shows them under "Why this rank".

## Provider interfaces
| Data | Interface | Today | Real source (needs authorisation) |
| --- | --- | --- | --- |
| Timetable | `data/timetable.py` loader (the next interface to add) | Simulated CSV | IRCTC/CRIS timetable feed |
| Running status | `TrainStatusProvider` | Simulated events | NTES / CRIS |
| Seat availability | not connected | always "unknown" | IRCTC availability (authorised partner only) |
| Fares | not connected | always "unknown" | IRCTC fare enquiry (authorised partner only) |
| Stations / nearby | `network.yaml` | Simulated estimates | Station masters, maps |
| Buses | `BusProvider` | Demo samples / none | State transport operators |
| Weather | `WeatherProvider` | Simulated / IMD stub | IMD (IP whitelisting required) |

We never scrape protected services or invent private railway APIs.
