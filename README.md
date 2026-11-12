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

> ⚠️ **All railway data is SIMULATED.** Trains numbered 90xxx are invented; station codes are real.
> This is **not** an official IRCTC or Indian Railways app. A TDR is a request; the Zonal Railway decides the refund.

---

## 1. Run it on macOS

Needs Python 3.11+ and Node 20+ (`brew install python@3.12 node`).

```bash
# Backend
cd agla-kadam/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest                                  # expect: 119 passed
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
| Backend (119 tests) | `cd backend && pytest` | Refund slabs and exact boundary times, rule versions by date and train category, the TDR 3-hour boundary, invalid inputs, the disruption detector, route search vs Connection Scan, ranking, the Rights Clock, LLM failures (timeout, bad JSON, invented numbers, promise wording), the API, and the 4 demo scenarios |
| End-to-end (6 tests) | `cd frontend && npm run build && npx playwright install chromium && npm run test:e2e` | Full passenger journeys on a phone-sized screen, Hindi toggle, invalid PNRs, stale data |

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

Extra edge cases to show from the presenter: **+1 h** with no new update → "Live data is out of date, so we won't advise".
**Cancel train** → automatic full refund plus alternatives.

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
  main.py                FastAPI: passenger API + presenter endpoints + serves the built frontend
frontend/src
  screens/               Add journey → My journey → Your options (+ Rights Clock) → How to do it → Summary; Presenter
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
(`anthropic` or `openai`-compatible), `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS`, `CORS_ORIGINS`.

## 6. Deploy (free tier)

1. Push this folder to GitHub.
2. On Render: **New → Blueprint**, select the repo. `render.yaml` builds the Dockerfile (frontend and backend in one service).
3. Open `https://<your-app>.onrender.com`. Free instances sleep, so open the app 10 minutes before judging.

Local Docker test: `docker build -t agla-kadam . && docker run -p 8000:8000 agla-kadam`

## 7. Before you pitch: verify these

- [ ] **April 2026 all-train refund slabs**: find the official notification. Until then they're badged "announced, not notified" (`RS-REG-2026-APR`).
- [ ] **2015 refund slabs**: check against the official PDF (`RS-REG-2015` has `last_verified: null`).
- [ ] **Missed-connection TDR deadline** (3 h after arrival): currently from a partner help page.
- [ ] **Vande Bharat Sleeper / Amrit Bharat II late-running refund**: the app deliberately says "check the official channel".
- [ ] Rule boundaries (e.g. exactly 72 h, exactly 8 h) follow our reading of "more than" vs "up to". Confirm them.
- [ ] Keep the "Simulated data" strip visible in every screenshot and video frame.

## 8. Demo checklist

- [ ] `pytest` green · `npm run test:e2e` green
- [ ] Deployed app opened on the phone over mobile data
- [ ] One run-through with `LLM_ENABLED=false`
- [ ] Presenter panel reset between scenarios
- [ ] A backup screen recording of all 4 scenarios
