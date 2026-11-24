# Agla Kadam — "Your journey changed. Know your next step before the deadline."

A prototype for the **Think Ticketing, Think IRCTC** challenge (SBI Youth Ideathon 2026).

When a booked train journey changes (a delay that breaks a connection or crosses 3 hours,
a ticket still waitlisted after the chart, or a cancellation), Agla Kadam:

1. **detects** what changed for *your* journey (rules, no AI),
2. works out your **refund/TDR rights and deadlines** from versioned, cited rules (no AI),
3. **ranks recovery plans** (timetable search + explainable ranking, no AI),
4. shows the **Rights Clock**: your rights losing value over time, and the exact "decide by" moment,
5. explains the top plan in **Hindi or English** (an optional LLM, checked by a validator, with a template fallback),
6. gives the **official steps**. It never files, cancels or logs in for you.

**Upgrade: Railway Journey Protection Platform.** The same engine now also powers, as one product:

| Feature | Where in the app | What it does |
| --- | --- | --- |
| Journey Digital Twin | Overview | Every leg, every change of train, how fresh each fact is, what is affected, expected final arrival |
| Station Transfer Intelligence | Overview, Options | Classifies each change of train as Comfortable / Tight / High risk / Not possible, using simulated station estimates and your walking speed / step-free needs; impossible changes are never offered |
| What-If Simulator | What-If | 7 scenarios (act now, wait, delay grows, cancel, other train, missed connection, one-change route), each calculated by the rules engine, with confidence and assumptions |
| Counterfactual reasoning | Options | Why the top option is first, how it compares, and what changes if you wait or the delay grows (only from calculated scenarios) |
| Passenger Rights Wallet | Wallet | Estimate vs eligible vs filed vs approved vs received, kept apart; rule version, effective date, source, unresolved conditions; claim tracking; text export |
| Family Journey Guardian | More → Family group | One view for a group on two PNRs; together vs split options, clearly labelled; labels only, no names |
| Offline Journey Guardian | More → Offline card | Masked snapshot saved on the phone (IndexedDB), service worker for the app shell, "not live" + time made, emergency numbers |
| Multilingual assistant | More → Ask | Text or voice (browser speech API) in English, Hindi or Hinglish; answers built only from backend facts; read-aloud |
| Resilience score | More → Resilience | Experimental, transparent weighted score with every factor shown |
| Community reports | More → Station reports | Unverified, expiring, de-duplicated passenger reports; personal data rejected; never change options or refunds |

**Critical upgrade: PREDICT → DECIDE → RECOVER.** The app now tells the passenger *what to do next*, not just what happened.

| What's new | Where | What it does |
| --- | --- | --- |
| Decide screen | Journey → **Decide** (also "What should I do?" on the alert) | Header ("Your connecting journey is at risk"), one **recommended next step**, six never-blank option cards (continue, cancel, another train, unreserved, bus, wait / next day), money compared (cancel now / wait 15 min / wait until X / later / claim), claim stages kept apart |
| Delay Propagation Engine | Decide → "Will the delay grow or recover?" | Own-train trend, late trains just ahead on the same track section (with reasons for those *not* counted), fog warnings, recovery allowance → arrival **range** + risk band. **No fake probabilities** |
| Connection Risk Engine | Decide header and Continue card | Whole arrival range vs. the transfer time this passenger needs: Comfortable / Tight / High risk / Unlikely / Not feasible, plus "if more than X min late at Y, the change fails" |
| Journey Recovery Engine | Decide cards | Direct, one-change, nearby-station (Nizamuddin), unreserved (rules), sample buses (demo only), next-day with Tatkal timing; one result type per option; transparent ranking |
| Copilot decision questions | Copilot | "Can I catch the next train?", "If I cancel now, how much?", "Find another train", "Can I use a general ticket?", "Bus?", "Tomorrow?", "Safest option in Hindi" |
| 6 decision demos | Home → demo list (PNR 8100000008–13) | Recovering delay, worsening delay with congestion, fog, missed connection, cancel-now-or-wait, next-day recovery |

Docs: [Decision clarity audit](docs/DECISION_CLARITY_AUDIT.md) · [Delay propagation](docs/DELAY_PROPAGATION_INTELLIGENCE.md) ·
[Recovery engine](docs/JOURNEY_RECOVERY_ENGINE.md) · [Decision model](docs/PASSENGER_DECISION_MODEL.md) ·
[Data sources and confidence](docs/DATA_SOURCE_AND_CONFIDENCE.md) · Screenshots: `submission/screenshots/decide/`

**Next round: from a set of features to one journey product.**

| What's new | Where | What it does |
| --- | --- | --- |
| Home dashboard and My journeys | Home, My journeys | Journeys saved on this device (ids only, never the PNR), most urgent first, KPIs, recent activity, ask box, main demo |
| Journey Recovery Graph | Journey → Overview | Every stop and change of train on a timeline; how a delay spreads, in plain sentences ("The change at New Delhi is no longer possible…") |
| Disruption Centre | Journey → Disruption | What happened, when it was updated, what is affected, what it means, how urgent (countdown), what to do next, your rights now |
| What-If compare | Journey → What-If | Any two outcomes side by side: arrival, extra time, money, deadline, transfer risk, rules, confidence label |
| Rights Wallet stepper | Journey → Wallet | Estimate → Eligible → Filed → Approved → Received |
| Journey Copilot | Copilot | Chat in English/Hindi/Hinglish, incl. "what if I wait 45 minutes?". Read-only tools, rules engine numbers, citations, tools used, next actions |
| Knowledge base with citations | Copilot, Settings | Rule documents with source, version, effective dates and status; "no reliable source" instead of guessing |
| Accessibility | Settings | Larger text, high contrast, simple-language mode, Hindi, skip link, keyboard and screen-reader labels |
| Main demo | Home → "Try the main demo" | **Bhopal → New Delhi → Chandigarh** (PNR `8100000007`) |

AI design: [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md) · Data and privacy: [docs/DATA_TRUST_AND_PRIVACY.md](docs/DATA_TRUST_AND_PRIVACY.md) ·
Strategy: [docs/NEXT_ROUND_PRODUCT_STRATEGY.md](docs/NEXT_ROUND_PRODUCT_STRATEGY.md) · Audit and plan: [docs/NEXT_ROUND_AUDIT.md](docs/NEXT_ROUND_AUDIT.md) ·
Screenshots: `submission/screenshots/next-round/`

> ⚠️ **All railway data is SIMULATED.** Trains numbered 90xxx are invented; station codes are real.
> This is **not** an official IRCTC or Indian Railways app. A TDR is a request; the Zonal Railway decides the refund.

**Competition submission (SBI Youth Ideathon 2026 · Think Ticketing, Think IRCTC):**
deck `submission/Agla_Kadam_Innovation_Challenge_Pitch.pptx` · real screenshots `submission/screenshots/` ·
[video script](docs/FINAL_VIDEO_SCRIPT.md) · [live demo](docs/LIVE_DEMO_SCRIPT.md) ·
[submission checklist + GitHub steps](docs/FINAL_SUBMISSION_CHECKLIST.md) · [evaluation](docs/FINAL_EVALUATION.md)

---

## 1. Run it on macOS

Needs Python 3.11+ and Node 20+ (`brew install python@3.12 node`).

```bash
# Backend
cd agla-kadam/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest                                  # expect: 314 passed
uvicorn app.main:app --reload           # API on http://localhost:8000  (docs: /docs)
```

In a second terminal:

```bash
cd agla-kadam/frontend
npm install
npm run dev                             # app on http://localhost:5173
```

Open http://localhost:5173 on your laptop, or on your phone on the same Wi-Fi (`npm run dev -- --host`).

**Single-server mode** (what gets deployed): `cd frontend && npm run build`, then run only the backend.
FastAPI serves the built app at http://localhost:8000.

## 2. Tests

| Suite | Command | What it covers |
| --- | --- | --- |
| Backend (314 tests: the original 119 + 73 upgrade + 39 next round + 48 decision engines + 35 station intelligence) | `cd backend && pytest` | Refund slabs and exact boundary times, rule versions by date and train category, the TDR 3-hour boundary, invalid inputs, the disruption detector, route search vs Connection Scan, ranking, the Rights Clock, LLM failures (timeout, bad JSON, invented numbers, promise wording), the API, the demo scenarios; plus the twin, transfer classes, what-if, counterfactuals, resilience, wallet stages and claims, family groups, offline card, assistant intents (EN/HI/Hinglish, stale data, LLM failure), community reports (duplicates, expiry, conflicts, personal data, no effect on recommendations) and every new endpoint |
| End-to-end (31 tests: the original 6 + 9 upgrade + 5 next round + 5 Decide screen + 5 Station Navigator + 1 screens-agree) | `cd frontend && npm run build && npx playwright install chromium && npm run test:e2e` | Full passenger journeys on a phone-sized screen, Hindi toggle, invalid PNRs, stale data; plus twin → options → what-if, wallet claim + export, family group, offline card with the network switched off, Hinglish assistant question, community reports, accessibility needs, Hindi on the new screens, announced-rule refunds never shown as certain; next round: home dashboard, the Bhopal→Delhi→Chandigarh flow, Copilot What-If, Copilot prompt injection, accessibility settings |

Full results: [docs/TEST_REPORT.md](docs/TEST_REPORT.md). API: [docs/API.md](docs/API.md). Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Demo, pitch and comparison: [docs/DEMO_AND_PITCH.md](docs/DEMO_AND_PITCH.md).

If Playwright's browser download is blocked, point it at Chrome:
`CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" npm run test:e2e`

## 3. Demo script (exact inputs → expected outputs)

Open the **presenter panel** at `#/presenter` on the laptop, and the passenger view on the phone.
Press **Reset scenario** before each run.

| # | Demo PNR | What it shows | Expected output |
| --- | --- | --- | --- |
| 1 | `8100000001` | **Normal journey**: 3A, ₹2,140, departs 15 Dec 22:00; clock 12 Dec 21:00 | "Nothing needs your attention". Top plan: travel as booked. Cancel preview: **₹1,960 back** (₹180 flat). Rights Clock: refund drops to ₹1,605 at 22:00 (badge: rule announced, not notified) |
| 2 | `8100000002` | **Edge case**: LKO→NDLS, 3A ₹1,180, live delay 190 min, clock 15 Dec 12:30 | "More than 3 hours late". The "Don't travel and file a TDR" plan shows **₹1,180 back · if approved**, act by **17:10** (the train's actual departure). Presenter: set the delay to **170** and press *Send delay update*. Within 3 s the TDR plan and its Rights Clock bar disappear, and a "may become eligible" warning appears |
| 3 | `8100000003` | **High impact**: family of 4, SL, waitlisted after the chart at 13:00 | "Do nothing: refund comes automatically": **₹2,140** (4 × ₹595 − 4 × ₹60 clerkage). Top plan (Reach soonest): 90305 at 17:00, arriving 06:30, marked **Seats not checked**. Decide by **16:30** |
| 4 | `8100000004` | **Missed connection in fog**: NDLS→PRYJ (late 2h10m) then PRYJ→DBG, linked PNRs | Connection at Prayagraj at risk (margin −85 min). Top plan: 90205 + 90601, arriving 20:30, plus a TDR for the missed train, **₹455 if approved**, with its deadline marked *not yet officially confirmed*. Decide by **09:15** |

| 5 | `8100000005` + `8100000006` | **Family group** on two PNRs (2 confirmed, 2 waitlisted after chart), NDLS→PNBE 3A ₹1,650 each | Open More → Family group. "Members have different ticket status". With "Keep family together": everyone switches to 90305, **₹4,830 back**, ₹1,770 lost, 4 new tickets; split options labelled **Splits the group** with ₹3,180 back |

| 6 | `8100000007` | **Main demo — connected journey**: BPL→NDLS (90701, 3A ₹1,320) then NDLS→CDG (90801, CC ₹645), linked PNRs, 30 min minimum change | Starts 25 min late: change at New Delhi has **5 min** to spare → "Watch closely". Presenter: delay **95** → graph shows the change is not possible, leg 2 "Likely missed", Disruption Centre "Act by 09:45". Top option: **90803**, arrive 13:40, plus a TDR for the missed connection, **₹645 if approved**. Copilot: "What if I wait 45 minutes?" |

| 7–12 | `8100000008` … `8100000013` | **Decision demos** (open the **Decide** tab) | 08 recovering → *Tight, stay and watch*; 09 worsening + 2 late trains ahead → *High risk, stay but prepare, don't cancel (₹0 vs TDR ₹645 if approved)*; 10 fog → wider range; 11 missed → *book 90823, file TDR*; 12 cancel ₹660 now vs ₹0 after 01:30; 13 next day 90801 + Tatkal timing |

| 13 | `8100000014` | **Station Navigator** (open the **Station** tab): BPL→NDLS (90721) then NDLS→CDG (90821, 19:45) | Platform 4 *Reported* → Platform 12 *Confirmed*; walk 6–11 min, 2 stairs; **Possible but tight**; "Prepare to get off" (43 min). Presenter (`#/presenter`): train 90821, NDLS, Departure, 16, *Send platform* → "changed from 12", recalculated. Pick *No stairs (lifts)* → **High risk**, lift status unknown. Also open **Stations** → New Delhi / Howrah / CSMT and search "exit", "washroom", "metro" |

Extra edge cases to show from the presenter: **+1 h** with no new update → "Live data is out of date, so we won't advise".
**Cancel train** → automatic full refund plus alternatives.


### Station Navigator (new)

Which platform, how to get there, can I make my connection, where is the exit/washroom/metro — for **New Delhi,
Howrah and Mumbai CSMT** on **schematic** maps. Every platform has one status (Confirmed / Reported / Scheduled /
Predicted / Unknown); with no live feed the app says "Live platform information is currently unavailable. Please
verify station display boards and announcements." Lift status is always shown as unknown. No GPS: you pick your
location or open a QR-style link (`#/stations/NDLS?at=PF2`). Docs: [STATION_INTELLIGENCE.md](docs/STATION_INTELLIGENCE.md),
[STATION_NAVIGATION_ARCHITECTURE.md](docs/STATION_NAVIGATION_ARCHITECTURE.md), [STATION_DATA_SOURCES.md](docs/STATION_DATA_SOURCES.md),
[PRODUCT_AUDIT.md](docs/PRODUCT_AUDIT.md).

## 4. How it is built

```
backend/app
  core/clock.py          replayable clock (demo + tests), IST only, rejects naive times
  rules/                 versioned refund/TDR rules (rulesets.yaml) + deterministic engine
  domain/models.py       journey, legs, events (every event labelled SIMULATED/OFFICIAL)
  data/                  RailDataSource interface, SimulatedSource, OfficialSource stub, timetable.csv, scenarios/
  detect/detector.py     connection buffer, >3h late, waitlisted after chart, cancelled, stale data
  plan/                  csa.py (route search), builder.py, ranker.py, rights_clock.py, service.py
  explain/               Hindi/English templates, LLM client, validator
  twin/twin.py           Journey Digital Twin
  plan/transfer.py       Station Transfer Intelligence (data/station_transfer.yaml, simulated)
  plan/counterfactual.py why first, comparisons, counterfactuals
  whatif/simulator.py    What-If scenarios (hypothetical events, never stored)
  wallet/wallet.py       Passenger Rights Wallet stages + export
  family/family.py       Family Journey Guardian (data/groups.json, labels only)
  offline/card.py        masked offline snapshot
  assistant/assistant.py intent detection (keywords; optional LLM picks an intent only)
  insights/resilience.py experimental resilience score
  community/reports.py   unverified, expiring passenger reports
  store.py               SQLite: actions, claims, preferences, reports
  main.py                FastAPI: passenger API + presenter endpoints + serves the built frontend
frontend/src
  screens/               Add journey → My journey (twin) → Your options (+ Rights Clock) → How to do it → Summary; Presenter;
                         What-If, Wallet, More, Resilience, Family, Offline card, Assistant, Community, Preferences
  components/            RightsClock, SectionNav, TwinPanel, RecommendationBox
  offlineStore.ts        IndexedDB for the saved offline card
public/sw.js             service worker (app shell only, never /api)
  components/RightsClock.tsx
  i18n.ts                all Hindi/English text and the official steps
e2e/                     Playwright tests
```

**Where AI is (and isn't) used.** Refund amounts, deadlines, eligibility and plan ranking are fixed code,
and every answer carries the rule ID, its source link and its last-checked date. The only AI is the plan
explanation. The LLM may write only slot names like `{refund}`; code fills in the numbers. A validator
rejects any digit outside a slot, unknown slots, and promise words ("guaranteed", "पक्का"). If the LLM is
off, slow (over 4 s), errors, or fails validation, the hand-written template is used. The app is fully
usable with `LLM_ENABLED=false`, which is the default.

**Data honesty.** No official API is assumed and nothing is scraped. `OfficialSource` is an empty stub
showing where authorised IRCTC/CRIS data would plug in. Seat availability is never shown as confirmed.
The minimum transfer time (30 min) is our assumption, not an official figure.

## 5. Environment variables

See `.env.example`. Key ones: `DEMO_MODE` (presenter endpoints on/off), `LLM_ENABLED`, `LLM_PROVIDER`
(`anthropic` or `openai`-compatible), `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS`, `CORS_ORIGINS`, `RATE_LIMIT_PER_MIN`,
`WEATHER_PROVIDER` (simulated|imd|off), `BUS_PROVIDER` (demo|off), `STORE_PATH` (SQLite file for claims, preferences and reports; default `:memory:`, so a restart clears them).
`DEMO_TOKEN` (optional; when set, the presenter page needs this token, so nobody else can change the demo on a public link).
Never put API keys or the demo token in source code; set them in `backend/.env` (git-ignored) or the hosting dashboard.

## 6. Deploy (free tier)

1. Push this folder to GitHub.
2. On Render: **New → Blueprint**, select the repo. `render.yaml` builds the Dockerfile (frontend and backend in one service).
3. In the Render dashboard, set `DEMO_TOKEN` to a secret word. Type it into the presenter page when asked.
4. Open `https://<your-app>.onrender.com`. Free instances sleep, so open the app 10 minutes before judging.

Local Docker test: `docker build -t agla-kadam . && docker run -p 8000:8000 agla-kadam`

## 7. Before you pitch: verify these

- [ ] **April 2026 all-train refund slabs**: a Govt of India publication (New India Samachar, PIB, Apr 2026) says they were introduced, but the Gazette text wasn't found. Until it is, the app labels them "announced, not yet confirmed" everywhere (`RS-REG-2026-APR`).
- [ ] **2015 refund slabs**: check against the official PDF (`RS-REG-2015` has `last_verified: null`).
- [ ] **Missed-connection TDR deadline** (3 h after arrival): currently from a partner help page.
- [ ] **Vande Bharat Sleeper / Amrit Bharat II late-running refund**: the app deliberately says "check the official channel".
- [ ] Rule boundaries (e.g. exactly 72 h, exactly 8 h) follow our reading of "more than" vs "up to". Confirm them.
- [ ] Keep the "Simulated data" strip visible in every screenshot and video frame.

## 8. Demo checklist

- [ ] `pytest` green (279) · `npm run test:e2e` green (25)
- [ ] Deployed app opened on the phone over mobile data
- [ ] One run-through with `LLM_ENABLED=false`
- [ ] Presenter panel reset between scenarios
- [ ] A backup screen recording of all 5 scenarios
- [ ] Offline card saved on the demo phone before going on stage
# irctc-innovation
