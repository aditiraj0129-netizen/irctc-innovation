# Station data sources and their limits

All sources were checked on **24 Nov 2026**. No data in this prototype comes from a live railway system.

## Station layout sources (used)

| # | Source | Data used | Access method | Update frequency | Reliability | Limits | Permitted use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NDLS S1 | [Wikipedia — New Delhi railway station](https://en.wikipedia.org/wiki/New_Delhi_railway_station) | 16 platforms; Platform 1 on Paharganj side, 16 on Ajmeri Gate side; metro on Ajmeri Gate side | Read by hand | Community-edited, irregular | Medium | No geometry, no FOB/lift positions | Facts only (CC BY-SA text not copied) |
| NDLS S2 | [Governance Now (2010)](https://www.governancenow.com/news/regular-story/soon-new-waiting-facility-new-delhi-station) | Two FOBs connecting Ajmeri Gate and Paharganj | Read by hand | Not updated (2010) | Low–medium (old) | May be out of date; marked `REPORTED` | Fact only |
| HWH S1 | [Wikipedia — Howrah railway station](https://en.wikipedia.org/wiki/Howrah_railway_station) | Old Complex 1–15, New Complex 17–23 (16 reported non-functional); Yatri Niwas | Read by hand | Irregular | Medium | No geometry | Facts only |
| HWH S2 | [Wikivoyage — Howrah Station](https://en.wikivoyage.org/wiki/Howrah_Station) | Three parts: Old Complex, New Complex, Howrah Metro | Read by hand | Irregular | Medium | Travel guide, not official | Facts only |
| CSMT S1 | [erail.in station info](https://erail.in/info/c-shivaji-maharaj-t-railway-station-CSMT/29924) / Wikipedia | 18 platforms: 1–7 suburban, 8–18 long distance | Read by hand (public page, no scraping) | Unknown | Medium | Third-party site | Facts only |
| CSMT S2 | IndianRailYatra blog (2026) | Separate long-distance entrance on P. D'Mello Road side | Read by hand | Unknown | Low (secondary) | Marked `REPORTED` | Fact only |

## Sources looked at but not used

| Source | Why not used |
| --- | --- |
| **NTES / IRCTC platform data** | No documented public API. Their websites are not scraped (terms of use, anti-bot protections). |
| **OpenStreetMap (Overpass API)** | Open data (ODbL) and would be the best next step, but the network allowlist of the build environment blocked it, so no OSM geometry was imported. If added later it must carry ODbL attribution. |
| **Official station maps** | Not published in a machine-readable, licensed form that we could find. |
| **IMD weather APIs** | Need IP whitelisting (already reported as `unavailable` by the weather provider). |

## Platform data (simulated)

| File | What | Label in app |
| --- | --- | --- |
| `backend/app/data/platforms.yaml` | Scheduled platforms for demo trains (e.g. 90721 arrives NDLS PF5, 90821 departs PF12) and 7-run histories | `SCHEDULED` / `PREDICTED (simulated history)` |
| `backend/app/data/scenarios/14_station_connection.json` | Platform events (90721 PF4 Reported, 90821 PF12 Confirmed) | Source `SIMULATED_DEMO` |
| Passenger entry (`POST /api/journeys/{id}/station/platform`) | What the passenger reads on the board | `REPORTED`, source `PASSENGER_FROM_STATION_BOARD` |

**Limits:** the platform numbers are invented for demo trains (90xxx numbers are not real trains). They must never be read as real platform assignments.

## Lift and escalator data

No source gives working status. Lifts are always **"status unknown"**; escalator direction is **"not verified"**.
