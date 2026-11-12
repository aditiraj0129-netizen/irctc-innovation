# Agla Kadam API

Base URL: `http://localhost:8000`. Interactive docs: `/docs` (FastAPI). All railway data is **SIMULATED**.
Money is always in **paise** (₹1 = 100 paise). Times are ISO 8601 with the IST offset (`+05:30`).
`{jid}` is a journey id such as `missed_connection`. Unknown ids return **404**; bad inputs return **422**.
A per-IP rate limit (`RATE_LIMIT_PER_MIN`, default 240) returns **429**.

## Original endpoints (unchanged)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/scenarios` | Demo journeys (now also `group`) |
| POST | `/api/journeys` `{pnr}` | Find a demo journey by 10-digit PNR |
| GET | `/api/journeys/{jid}/assessment?priority=time\|money\|risk\|transfers\|family&lang=en\|hi` | Situation, ranked plans, Rights Clock. **New fields:** `recommendation` (null when data is stale), `profile`; each plan now has `transfers`, `worst_transfer`, `changes` |
| POST | `/api/journeys/{jid}/actions` | Record which plan the passenger chose |
| POST | `/api/demo/{jid}/reset` · `/clock` · `/events` | Presenter controls (only when `DEMO_MODE=true`) |

## New endpoints

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/api/journeys/{jid}/twin` | Journey Digital Twin: `status` (ON_TRACK / DISRUPTED / BROKEN / COMPLETED), `legs[]` (state, expected times, delay, `info.freshness` FRESH/STALE/NONE, `info.source`), `transfers[]` (`check.cls`, `required_minutes`, `margin_minutes`, `latest_safe_arrival`), affected / unaffected segments, expected final arrival |
| GET | `/api/journeys/{jid}/whatif?priority&delay_increase=15..600&wait_minutes=5..720` | 7 `outcomes`: BEST_NOW, WAIT_30, DELAY_GROWS, CANCEL_NOW, TAKE_ALTERNATIVE, MISS_CONNECTION, ONE_CHANGE_ROUTE. Each: arrival, `arrival_diff_minutes` (vs booked arrival), money, rule ids, deadline, changes, `connection_risk`, `confidence` + reasons, pros/cons, `lost_options`, `assumptions`, or `not_applicable_reason` |
| GET | `/api/journeys/{jid}/wallet` | Rights Wallet: `items[]` with `stage`, `rule_stage`, estimate, deadline, `rule` (ids, version, name, categories, effective date, legal status, source, `unresolved`), `actions_needed`; `history[]`; `disclaimer` |
| POST | `/api/journeys/{jid}/wallet/claims` `{item_id, status: FILED\|APPROVED\|RECEIVED\|REJECTED}` | Records a passenger's claim update. Only forward steps are accepted (e.g. can't jump to RECEIVED); otherwise **422 INVALID_CLAIM_STEP** |
| GET | `/api/journeys/{jid}/wallet/export` | Plain-text summary as a download (states "estimates, not guaranteed") |
| GET / PUT | `/api/journeys/{jid}/preferences` `{profile: {walking_speed: normal\|slow, step_free, senior}, priority}` | Accessibility needs used by transfer analysis |
| GET | `/api/journeys/{jid}/resilience` | Experimental score 0–100, every factor with weight, value and score, main risks, suggestions |
| GET | `/api/journeys/{jid}/offline-card` | Masked snapshot for offline use: `pnr_label` masked, `generated_at`, `stale_after` (+30 min), `data_label: SIMULATED_SNAPSHOT_NOT_LIVE`, legs, transfers, top 3 plans, rights, rules, instructions, emergency numbers |
| POST | `/api/journeys/{jid}/assistant` `{text (1–300 chars), lang: en\|hi}` | `intent`, `intent_source` (keywords / llm / none), `answer`, `rule_ids`, `answer_source: RULES_ENGINE`. Refuses to advise when data is stale |
| GET | `/api/journeys/{jid}/community/reports` | Active (non-expired) reports, each `label: UNVERIFIED_PASSENGER_REPORT`, `affects_recommendations: false` |
| POST | `/api/journeys/{jid}/community/reports` `{station: 2–5 capital letters, type, train_no?, note? ≤120}` | Adds or merges a report. Optional header `X-Reporter` (hashed). Notes with phone numbers or emails → **422** |
| GET | `/api/groups` | Family groups |
| GET | `/api/groups/{gid}?priority` (default `family`) | Group view: `divergence`, `group_profile`, member `timeline`, ranked `options` with `suitability` GROUP / INDIVIDUAL and `warnings` |
| POST | `/api/demo/groups/{gid}/reset` | Resets every journey in the group (demo only) |

Report types and how long they live: PLATFORM_CHANGE 60 min, CONGESTION 45, TRAIN_STOPPED 90,
TRANSFER_DIFFICULTY 180, ACCESS_PROBLEM 360. Reports of the same type at the same station within 20 minutes
are merged; the same reporter is counted once; confidence is LOW (1), MEDIUM (2–3), HIGH (4+).
