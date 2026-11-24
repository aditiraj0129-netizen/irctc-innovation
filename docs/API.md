# Agla Kadam API

Base URL: `http://localhost:8000`. Interactive docs: `/docs` (FastAPI). All railway data is **SIMULATED**.
Money is always in **paise** (₹1 = 100 paise). Times are ISO 8601 with the IST offset (`+05:30`).
`{jid}` is a journey id such as `missed_connection`. Unknown ids return **404**; bad inputs return **422**.
A per-IP rate limit (`RATE_LIMIT_PER_MIN`, default 240) returns **429**. If `DEMO_TOKEN` is set, every `/api/demo/...` call needs the header `X-Demo-Token`, else **403**. Every response carries basic security headers.

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
| POST | `/api/journeys/{jid}/community/reports` `{station: 2–5 capital letters, type, train_no?, note? ≤120}` | Adds or merges a report. One caller (network address, stored only as a hash) counts as one reporter; client headers can't add reporters. Notes with phone numbers or emails → **422** |
| GET | `/api/groups` | Family groups |
| GET | `/api/groups/{gid}?priority` (default `family`) | Group view: `divergence`, `group_profile`, member `timeline`, ranked `options` with `suitability` GROUP / INDIVIDUAL and `warnings` |
| POST | `/api/demo/groups/{gid}/reset` | Resets every journey in the group (demo only) |

Report types and how long they live: PLATFORM_CHANGE 60 min, CONGESTION 45, TRAIN_STOPPED 90,
TRANSFER_DIFFICULTY 180, ACCESS_PROBLEM 360. Reports of the same type at the same station within 20 minutes
are merged; the same reporter is counted once; confidence is LOW (1), MEDIUM (2–3), HIGH (4+).

## Next-round endpoints

Every `/api/...` path also works as `/api/v1/...` (same handler). `GET /api/health` now also returns
`providers` (which data source is used for what) and `api_versions`.

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/api/v1/journeys/{jid}/graph` | Journey Recovery Graph: `nodes` (`L{n}:DEP` / `L{n}:ARR`: scheduled, expected, delay, state OK / DELAYED / AT_RISK / BROKEN / DONE, freshness), `edges` (RIDE, TRANSFER with gap, required, margin, class), `trace` (cause→effect codes with numbers, e.g. `TRAIN_DELAYED → CONNECTION_BROKEN → LEG_LIKELY_MISSED → RECOVERY_NEEDED`), `broken_from_leg`, `status` |
| GET | `/api/v1/journeys/{jid}/recovery?priority=` | Disruption Centre: `what_happened` (events with source and time), `last_updated`, `data_fresh`, `affected_legs`, `consequence` (expected final arrival, delay at destination, connection margin, fare of unusable legs), `urgency` (`NOW` ≤60 min, `SOON` ≤240, `LATER`, `WATCH`, `NONE`, `UNKNOWN` when stale) with `decide_by` and `minutes_left`, `next_steps` (top plans), `rights`, `recommendation` (null when stale), `graph` |
| GET | `/api/v1/dashboard?ids=a,b` | Home / My journeys: up to 10 journey ids (lower-case letters, digits, `_`), unknown ids skipped, sorted most urgent first. Each: status, urgency, freshness, next departure, consequence, top step. Short server cache (`CACHE_TTL_SECONDS`) |
| POST | `/api/v1/journeys/{jid}/copilot` `{message 1–500, lang en\|hi, history ≤10 [{role, text}]}` | `intent`, `planner` (deterministic / llm), `answer`, `answer_source` (TEMPLATES / KNOWLEDGE_EXTRACTIVE / LLM_PHRASED), `clarify`, `tool_calls` (tool, args, ok, error), `citations`, `next_actions` (`route` inside the app or `tel`), `no_reliable_source`, `warnings` |
| GET | `/api/v1/knowledge/sources` | Documents in the knowledge base with provenance (source URL, version, effective dates, status, unresolved) and the chunk count |
| POST | `/api/v1/knowledge/search` `{query 2–300, lang}` | Grounded answer: `found`, `answer` (quoted from sources), `citations` (only the passages used), `source`, `warnings`. Below the relevance threshold: "No reliable source found" |
| POST | `/api/journeys/{jid}/wallet/claims` + header `Idempotency-Key` (8–80 letters, digits, `-`) | Same request repeated with the same key returns the first result and records nothing new. A malformed key → **422 INVALID_IDEMPOTENCY_KEY** |

## Decision endpoints (PREDICT → DECIDE → RECOVER)

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/api/v1/journeys/{jid}/decision?priority=time\|money\|risk\|transfers\|family` | `header` (status, first/second train, arrival range, time available/needed, risk, freshness), `prediction`, `connection`, `recovery`, `cards[6]` (key, status AVAILABLE / NOT_APPLICABLE / DATA_MISSING / NONE_FOUND / NOT_CONFIGURED, meaning, outcome, money, risk, deadline, next_action, items, missing, reason), `money[]` (CANCEL_NOW / WAIT_15 / WAIT_UNTIL / CANCEL_LATER / KEEP_AND_CLAIM / ALTERNATIVE with amount, charge, certainty, rule ids, legal status), `claims` (estimate / TDR eligibility / submission / approval / received), `recommendation` (code + numbers + why) |
| GET | `/api/v1/journeys/{jid}/prediction` | `prediction` (delay low/mid/high, arrival range, outlook, growth risk, trend + observations, congestion checks with reasons, weather applied/ignored, remaining sections, quality, missing inputs, `probability: null`), `connection` (slack early/likely/late, risk, max tolerable delay, watch), `evaluation_status` |
| GET | `/api/v1/journeys/{jid}/recovery-options?priority=` | `options`, `next_day` (with `tatkal`), `unreserved` (with eligibility), `buses`, `bus_status`, `empty_reason`, `weights`, `rules`. Every option: one `result_type`, `seat_availability`, `fare_status`, `data_source`, `last_updated`, `score_parts` |
| POST | `/api/demo/{jid}/events` | now also accepts an optional `station` (2–5 capital letters) so the delay engine sees station-by-station readings |

Environment: `WEATHER_PROVIDER` (`simulated` in demo mode, otherwise `imd`, which reports "unavailable" until IMD access is granted), `BUS_PROVIDER` (`demo` samples in demo mode, otherwise `off`).
