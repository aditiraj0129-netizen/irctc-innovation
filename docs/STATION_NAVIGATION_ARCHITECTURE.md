# Station Navigation — architecture, route algorithm, feasibility formula

Same modular monolith as the rest of Agla Kadam. **No new services.** One new package: `backend/app/station/`.

## 1. Modules and data flow

```
 station YAML (NDLS/HWH/CSMT)        platforms.yaml + scenario platform_events + passenger entries
          │                                         │
          ▼                                         ▼
   graph.py  build() ──► Station graph     platforms.py  platform_info() ──► one status per platform
   (lru_cache, loaded once)                 (CONFIRMED/REPORTED/SCHEDULED/PREDICTED/UNKNOWN, stale > 45 min)
          │                                         │
          ▼                                         │
   route.py  Dijkstra per profile ◄─────────────────┤
          │                                         │
          ▼                                         ▼
   feasibility.py  assess_connection() ◄── delay prediction (app/predict) ── journey (app/data)
          │
          ├──► service.py journey_station_view() ──► GET /api/journeys/{id}/station  ──► Station tab
          ├──► trusted_transfer_need() ──► Connection Risk Engine + Decide header (only when both platforms trusted)
          └──► Copilot tools get_platforms / station_route / find_facility ──► template answers (EN/HI)
```

**Adapters:** platform data goes through `platform_info()`, which takes observations from any source.
`OfficialPlatformProvider` is the slot for a real feed; it raises `ProviderNotConfigured` today, and the app
then shows the "Live platform information is currently unavailable…" message.

**Caching:** station graphs are parsed once (`functools.lru_cache`). Platform and journey views are computed per request (cheap: < 20 ms in logs).

**Rate limits:** every `/api/` path (station ones included) goes through the existing per-IP limiter (HTTP 429).

**Security:** station code `^[A-Z]{2,5}$`, node ids by regex, search text ≤ 60 characters, platform 1–30,
buffer 0–30, profile/speed as enums; passenger platform entry is checked against the journey's trains and the
station's real platform list. No location is stored on the server. No PNR, phone or email reaches an LLM.

**Staleness / offline:** platform observations older than 45 min are marked stale and lose "trusted" status;
running data that is stale removes "Prepare to get off"; when the API can't be reached the screen shows an error
state with Retry (the existing offline card is unchanged).

## 2. Station graph

| Node kind | Meaning |
| --- | --- |
| `PLATFORM` (`PF4`) | Middle of a platform — used as "you are on Platform 4" |
| `PLATFORM_POINT` (`G2_170`) | A point along a platform pair where stairs/lifts land |
| `FOB` | Foot overbridge deck above a platform pair (level 1) |
| `CONCOURSE` | Head concourse at the end of a terminus |
| `SIDE` | Station entrance/exit side |
| `FACILITY` | Washroom, ticket counter, metro, … |

Edges: `WALK`, `STAIRS`, `LIFT` (status **always `UNKNOWN`**), `ESCALATOR` (direction **`NOT_VERIFIED`**), `FOB`, `LINK` (walkway between complexes). Each node and edge carries a verification level.

## 3. Route algorithm (Dijkstra)

For each profile we run Dijkstra on edge cost = expected seconds:

| Profile | Rule |
| --- | --- |
| `fastest` | Lowest expected time |
| `step_free` | Stairs and escalators removed; lifts only. If no step-free path exists, says so |
| `fewer_levels` | +600 s penalty per level change, so it prefers staying on one level |

Times (estimates, not measured):

| Part | Normal | Slow (elderly, luggage, children) |
| --- | --- | --- |
| Walking speed | 1.3 → 0.8 m/s (fast → crowded) | 0.8 → 0.5 m/s |
| One flight of stairs | 30–75 s | 60–150 s |
| Escalator | 30–60 s | 30–60 s |
| Lift (wait + ride) | 45–240 s | 45–240 s |

Output: a time **range** (min), distance, counts of stairs/lifts/escalators, passenger-friendly steps
("Take the lift up to the North foot overbridge (lift status unknown)"), and `confidence: SCHEMATIC_DEMO`.
Identical paths from different profiles are shown once.

## 4. Connection feasibility formula

```
available time  = connecting departure − expected arrival     (early / likely / late arrival)
required time   = walking time (route range) + safety buffer (5 min default)
margin          = available − required
```

Checked at three points: early arrival + shortest walk, likely arrival + middle walk, late arrival + longest walk.

| Result | Rule |
| --- | --- |
| **Comfortable** | late-case margin ≥ 10 min |
| **Possible but tight** | late-case margin ≥ 0 |
| **High risk** | likely-case margin ≥ 0 (late case fails) |
| **Unlikely** | only the early case works |
| **Not feasible** | even the early case fails |
| **Cannot assess** | a platform is unknown, no station map, or no arrival estimate |

Extra rules: if either platform is only Scheduled/Predicted/stale, the result is **capped at "Possible but tight"**
and the screen says "platform not confirmed". The Decide screen and Connection Risk Engine use the station walk
only when **both** platforms are trusted.

### Worked examples (real numbers from the demo, PNR 8100000014)

Train 90721 arrives New Delhi PF4 (Reported); 90821 leaves PF12 (Confirmed) at 19:45.
Available time: early 42, likely 32, late 18 min.

| Case | Walk | Required (early/likely/late) | Margin (early/likely/late) | Result |
| --- | --- | --- | --- | --- |
| Fastest, PF4 → PF12 | 6–11 min, 376 m, 2 stairs | 11 / 14 / 16 | 31 / 18 / 2 | **Possible but tight** |
| No stairs (lifts), PF4 → PF12 | 6–16 min, 356 m, 2 lifts | 11 / 16 / 21 | 31 / 16 / −3 | **High risk** (+ lift status unknown) |
| Platform changes to 16 | recalculated | — | late case still ≥ 0 | **Possible but tight**, "changed from 12" |
| PNR 8100000007, only scheduled platforms | 5–9 min | 10 / 12 / 14 | 35 / 23 / −1 | **High risk** (and capped: not confirmed) |

## 5. "Prepare to get off"

Shown only when **all** are true: running data is fresh, arrival is 0–45 min away, and the arrival platform is known.

## 6. Positioning hierarchy

Manual selection → QR-style link (`?at=PF2`, demo) → default to your arrival platform. No GPS, no location permission,
session-only storage.
