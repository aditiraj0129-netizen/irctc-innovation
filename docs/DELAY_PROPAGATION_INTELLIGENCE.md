# Delay Propagation Intelligence

Module: `backend/app/predict/` (`delay.py`, `weather.py`, `network.py`, `connection.py`, `evaluation.py`).
API: `GET /api/v1/journeys/{id}/prediction`.

**Question it answers:** will this train win back some delay, or lose more, before the station that matters
(the change of train, or the destination)? And can the passenger still make the connection?

## What is real, what is simulated, what is not done

| Part | Status |
| --- | --- |
| Method (trend, shared sections, fog window, ranges, connection check) | **Implemented and tested** (deterministic code, 48 tests in `test_decision_engines.py`) |
| Train delay readings, other trains' delays, route sections, recovery allowances | **Simulated** demo data (`scenarios/*.json`, `data/network.yaml`) |
| Fog warnings | **Simulated, demo mode only**, labelled "SIMULATED_DEMO (IMD-style warning, not real)" |
| IMD weather API | **Not connected.** IMD's APIs need the caller's IP to be whitelisted through IMD's request form, and use under IMD's terms. `IMDWeatherProvider` refuses, and the app says "weather data unavailable" |
| Probabilities (chance of recovering, of missing the connection) | **Not shown.** There is no historical running data to train or calibrate a model. `probability` is always `null`, `probability_status = DISABLED_NOT_CALIBRATED` |
| Block-section occupancy, signalling, precedence orders | **Not available**; we never claim them |

## Evidence used

1. **The train's own readings.** Each reading has a delay, the time it was made, the station (when known), the source and its age.
   - Uses readings from the last 300 minutes.
   - The slope is (last delay − first delay) ÷ hours between them. If it is +4 min per hour or more, the delay is **growing**. If it is −4 or less, the train is **recovering**. Anything in between is **steady**.
   - Readings closer together than 30 minutes don't count as a trend. A jump from 25 to 95 minutes is a new delay, not "+840 min per hour".
2. **Trains just ahead on the same track section.** For every section still ahead, we look at other trains that use it.
   - A train is **counted** only if all of these are true:
     - it runs in the **same direction**;
     - it enters the section 0–30 min **before** our train (expected times);
     - it is itself at least 10 min late;
     - its reading is at most 45 min old.
   - Everything else is listed with the reason it was **not** counted: opposite direction, behind us, too far ahead, on time, or no recent data. Trains on other corridors are never looked at.
   - Level: 0 trains = none, 1 = low (moderate if that train is 45+ min late), 2 = moderate, 3+ = high.
   - It is shown as a **congestion-risk indicator, not proof** that those trains cause the delay.
3. **Fog warnings.** A warning counts only if it covers a section still ahead **and** is valid at the time our train will pass. Expired warnings are listed as "ignored: expired". A warning raises the risk; it is never stated as the cause of a delay.
4. **Recovery allowance.** This is the minutes a late train can typically win back on each section ahead. The values are simulated placeholders; real ones would come from the working timetable or from history.

## Baseline model (`BASELINE_HEURISTIC_V1`)

```
hours      = minutes still to run / 60
trend      = slope × min(hours, 2) × 0.5            (only half the trend, at most 2 h ahead, capped at ±60 min)
risk_add   = congestion (0 / 5 / 10 / 20) + fog (0 / 15 moderate / 30 dense)
mid        = current delay + trend + risk_add / 2
low        = max(0, min(mid, current delay) − recovery allowance − 5 if recovering)
high       = mid + risk_add / 2 + uncertainty,  uncertainty = min(40, 10 + 5 × hours)
```

**Outputs:**
- An **arrival range** (early, most likely, late).
- An **outlook**: may recover, likely stable, may increase, or not enough evidence.
- A **growth-risk band**: lower, moderate, high, or insufficient evidence.
- Every prediction also carries:
  - when it was generated, and the time of the latest data;
  - the evidence list and missing inputs;
  - a quality grade (good, limited or poor);
  - an explanation (codes and numbers) and its limitations.

**Stale or missing data:**
- No readings, or the newest reading is older than 15 minutes → no range; "not enough evidence".
- The Decide screen then tells the passenger to check NTES or RailOne, or to call 139.

## Connection Risk Engine (`connection.py`)

`slack = next departure − (first-train arrival + transfer time this passenger needs at this station)`.
The transfer time comes from `station_transfer.yaml`: the station's complexity, the passenger's walking speed and step-free needs, and never less than the journey's minimum. The check is run at the **early, likely and late** ends of the arrival range:

| Result | Rule |
| --- | --- |
| Comfortable | slack ≥ 10 min even at the late end |
| Tight | slack ≥ 0 at the late end |
| High risk | works at the likely arrival, fails at the late end |
| Unlikely | works only at the early end |
| Not feasible | fails even at the early end |
| Insufficient information | no fresh running data |

It also returns the **largest delay that still works** and the next station to check ("If it is more than 35 min late at New Delhi, the change won't work"). A 25-minute gap is never treated as proof by itself.

## How a real model would be added and judged

- Any model can implement the `DelayModel` protocol (`predict(features) -> (low, mid, high)`).
- `evaluation.py` already has MAE, RMSE, interval coverage, the Brier score, a calibration table and per-group breakdowns. Groups can be by train, route, season or lead time.
- These metrics are tested only on hand-made numbers. **No model has been trained or evaluated**: `EVALUATION_STATUS = NOT_EVALUATED_NO_HISTORICAL_DATA`.
- Probabilities should be switched on only after a model is evaluated on real history and is well calibrated.
