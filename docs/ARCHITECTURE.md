# Architecture

One deterministic core, many views. Every new feature reads the same journey, events and rules,
so the passenger never sees two different answers for the same question.

```mermaid
flowchart TD
  SRC["RailDataSource<br/>SimulatedSource (now) · OfficialSource stub (needs authorised access)"] --> EV[Journey + Events]
  CLK["Clock (IST, replayable)"] --> DET
  EV --> DET["Detector<br/>situations"]
  EV --> TWIN["Digital Twin"]
  PROF["Passenger profile<br/>(walking speed, step-free, senior)"] --> XFER["Transfer Intelligence<br/>station_transfer.yaml (simulated)"]
  XFER --> TWIN
  XFER --> PLAN
  RULES["Rules engine<br/>versioned YAML, paise, cited"] --> PLAN["Planner<br/>CSA route search + plan builder"]
  DET --> PLAN
  PLAN --> RANK["Ranker<br/>time · money · risk · transfers · family"]
  RANK --> RC["Rights Clock"]
  RANK --> WI["What-If simulator<br/>hypothetical events, never stored"]
  WI --> CF["Counterfactual recommendation"]
  RANK --> WAL["Rights Wallet"]
  STORE[("SQLite store<br/>claims · prefs · actions · reports")] --> WAL
  RANK --> FAM["Family Guardian"]
  RANK --> OFF["Offline card (masked)"]
  WAL --> AST["Assistant<br/>keywords → intent → facts"]
  TWIN --> AST
  LLM["Optional LLM"] -. "explanation slots / intent only" .-> AST
  LLM -.-> EXP["Explainer + validator"]
  COM["Community reports<br/>unverified, expiring"] --> STORE
  COM -. "shown beside advice, never used by it" .-> UI
  RC & CF & WAL & FAM & OFF & AST & TWIN & EXP --> API["FastAPI"] --> UI["React PWA<br/>service worker + IndexedDB"]
```

## Design rules (kept from the original build, enforced by tests)

- **Money and deadlines are deterministic.** Only the rules engine computes them. Every result carries the rule id,
  version, categories, effective date, legal status, source and unresolved conditions.
- **AI is optional.** The LLM may fill explanation templates (slots only, validated) or pick an assistant intent.
  It never produces numbers, rules, dates or advice. With no key, everything works.
- **No business logic in React.** Screens display backend results; the only client logic is formatting,
  the offline store and the browser speech APIs.
- **Data honesty.** All railway data is simulated and labelled. Transfer times are simulated estimates. Offline
  cards say "snapshot, not live" with the time they were made. Community reports are unverified and cannot change
  recommendations (a test compares assessments with and without reports).
- **Privacy.** No names: family members are labels. The offline card masks the PNR. Community notes reject phone
  numbers and emails; reporters are stored only as hashes. The only device storage is the masked card (IndexedDB)
  and the language setting.

## Feature → module map

| Feature | Backend | Frontend |
| --- | --- | --- |
| Digital Twin | `twin/twin.py` | `components/TwinPanel.tsx` (Overview) |
| What-If | `whatif/simulator.py` | `screens/WhatIfScreen.tsx` |
| Family Guardian | `family/family.py`, `data/groups.json`, scenarios 5–6 | `screens/FamilyScreen.tsx` |
| Offline Guardian | `offline/card.py` | `screens/OfflineCardScreen.tsx`, `offlineStore.ts`, `public/sw.js` |
| Transfer Intelligence | `plan/transfer.py`, `data/station_transfer.yaml`, `plan/csa.py` (per-station transfer rule) | badges in Options, Twin |
| Rights Wallet | `wallet/wallet.py`, `store.py` | `screens/WalletScreen.tsx` |
| Assistant | `assistant/assistant.py` | `screens/AssistantScreen.tsx` (Web Speech API) |
| Resilience | `insights/resilience.py` | `screens/ResilienceScreen.tsx` |
| Counterfactuals | `plan/counterfactual.py` | `components/RecommendationBox.tsx` |
| Community | `community/reports.py` | `screens/CommunityScreen.tsx` |

## Security and deployment design (after the final audit)

- **Static files:** the server only serves files that are really inside `frontend/dist`; any `../` path gets the app page.
- **Rate limit:** per caller address. In Docker, uvicorn runs with `--proxy-headers`, so behind Render's proxy each user is counted separately. Quiet addresses are forgotten.
- **Presenter protection:** optional `DEMO_TOKEN` (set in the hosting dashboard). The presenter page sends it as `X-Demo-Token`; passenger endpoints never need it.
- **Headers:** `nosniff`, `no-referrer`, `X-Frame-Options: DENY`, and `Permissions-Policy` allowing only the microphone (for voice).
- **CORS:** not needed in production (one origin); only the local dev origin is allowed by default.
- **Community reports:** one caller = one reporter (hashed address); client headers are ignored.
- **Honest money labels:** if an amount depends on a rule with legal status ANNOUNCED, the UI shows "Estimate: rule not yet confirmed" (never "Automatic"), and the assistant adds a warning.

## Bugs found and fixed

See `docs/TEST_REPORT.md` for the full list with the test that guards each fix.

## Next round additions

Still one modular monolith. The new parts read the same journey, events and rules as everything else.

```mermaid
flowchart TD
  PROV["Providers (interfaces)<br/>Simulated* now · Official* stubs raise ProviderNotConfigured"] --> EV[Journey + Events]
  EV --> G["Journey Recovery Graph<br/>graph/journey_graph.py<br/>nodes, RIDE/TRANSFER edges, cause→effect trace"]
  G --> REC["Recovery view<br/>graph/recovery.py<br/>urgency, consequence, next steps, rights"]
  RULES["Rules engine"] --> REC
  PLAN["Planner + ranker"] --> REC
  RULES --> KB["Knowledge corpus<br/>rules YAML + curated docs, provenance, injection filter"]
  KB --> RET["Retriever protocol<br/>BM25 (EN/HI/Hinglish), as_of filter"]
  RET --> GA["Grounded answers with citations"]
  TOOLS["Copilot tools (read-only, validated)"] --> CP["Journey Copilot<br/>deterministic planner · optional LLM (validated, PII removed)"]
  G & REC & PLAN & RULES & GA --> TOOLS
  REC --> CACHE["TTL cache"] --> API["FastAPI /api and /api/v1"]
  CP & GA --> API
  API --> UI["React: Home · My journeys · Journey (graph timeline) · Disruption Centre · Options ·<br/>What-If compare · Wallet stepper · Copilot · Offline · Settings (accessibility)"]
```

| New module | Job |
| --- | --- |
| `app/graph/journey_graph.py` | Builds the connected-journey graph from events every time (no hidden state) and explains how a delay spreads |
| `app/graph/recovery.py` | One "what now?" view: urgency, consequence, next steps, rights |
| `app/knowledge/` | Corpus, retriever, grounded answers (see `docs/AI_ARCHITECTURE.md`) |
| `app/copilot/` | Tools + planner + composer (see `docs/AI_ARCHITECTURE.md`) |
| `app/providers/` | Data-source interfaces so official feeds can replace simulated ones |
| `app/core/cache.py` | Small in-process TTL cache (no Redis needed at this scale) |
| `frontend/src/screens/{Home,MyJourneys,Disruption,Copilot,Settings}Screen.tsx` | New screens; old screens and routes kept |

Scaling plan, proportionate: one process handles the demo easily; next steps would be a real database
(`STORE_PATH` → Postgres), more instances behind a load balancer (the app keeps no per-user state in memory except
the short cache), and provider-side caching of live status. No Kafka, Kubernetes or microservices are needed for this.

## Decision upgrade: PREDICT → DECIDE → RECOVER

```mermaid
flowchart LR
  EV["Journey events<br/>(+ station per reading)"] --> DP["Delay Propagation Engine<br/>predict/delay.py"]
  NET["Route sections, other trains<br/>network.yaml + network_events"] --> DP
  WX["WeatherProvider<br/>Simulated (demo) · IMD stub"] --> DP
  DP --> CR["Connection Risk Engine<br/>predict/connection.py"]
  XFER["Transfer times + passenger needs"] --> CR
  CR --> RE["JourneyRecoveryEngine<br/>recover/engine.py"]
  TT["Timetable"] --> RE
  BUS["BusProvider<br/>demo samples · none"] --> RE
  RULES["Rules engine"] --> DM["Decision model<br/>decide/decision.py"]
  DP & CR & RE --> DM
  DM --> API["/api/v1/.../decision · prediction · recovery-options"]
  DM --> CP["Copilot tools (read-only)"]
  API --> UI["Decide screen"]
```

Still one modular monolith. No new services, queues or databases. Every new engine is a plain Python module with
its own tests, and every external data source is behind an interface that refuses (`ProviderNotConfigured`) instead of pretending.
