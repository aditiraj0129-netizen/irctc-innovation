# Next-round product strategy

## The problem, in one line
When one train in a connected journey runs late, the passenger has minutes to understand *what breaks*,
*what they are owed* and *what to do next* — and today that means checking 3–4 apps and reading refund rules.

## What Agla Kadam does now (all working and tested on simulated data)

1. **Detect** — the journey graph sees a delay and checks every change of train.
2. **Update the Digital Twin** — expected times, freshness, affected legs.
3. **Calculate connection risk** — margin vs the station's minimum transfer time and the passenger's walking needs.
4. **Show rights** — refund / TDR eligibility and deadlines from versioned, cited rules.
5. **Simulate recovery** — What-If: wait, delay grows, another route, cancel; side-by-side compare.
6. **Explain the next step** — ranked options with reasons; Copilot answers in English, Hindi or Hinglish.
7. **Update the Wallet** — estimate → eligible → filed → approved → received.

Central demo: **Bhopal → New Delhi → Chandigarh** (PNR 8100000007). A 25-minute delay leaves 5 minutes of margin
("watch closely"); at 95 minutes the change at New Delhi breaks, the Disruption Centre shows "act by 09:45",
the top option is train 90803 (arrive 13:40) plus a TDR for the missed connection (≈₹645 if approved).

## Who it is for
- Long-distance passengers with **two PNRs** (no through train) — most exposed to missed connections.
- **Families and seniors** — need step-free / slower-walking transfer checks and one view for the group.
- Hindi-first users — every screen and the Copilot work in Hindi.

## How it fits IRCTC
A module inside the IRCTC / RailOne app, not a separate booking system: read journey + live status,
explain rights, deep-link to the official TDR / cancellation / booking pages. It never books or files on its own.

## Roadmap (honest)

| Stage | What | Depends on |
| --- | --- | --- |
| Now (prototype) | All 7 steps above on simulated data; 231 backend + 20 E2E tests | — |
| Pilot | Swap `Simulated*` providers for authorised NTES/IRCTC feeds (interfaces already exist) | Data access agreement |
| Pilot | Verify every rule against Gazette text; remove "needs checking" labels | Legal review |
| Scale | Push alerts; real station transfer times from station masters | Railway partnership |
| Later | Optional LLM rewording in more Indian languages (validator already in place) | Model budget |

## How we will measure success (pilot)
- Time from disruption to a decision (target: under 2 minutes).
- TDRs filed before the deadline (vs. missed deadlines).
- Share of answers with a citation; zero answers with an invented amount (checked by tests and logs).

## Architecture choice
A **modular monolith** (FastAPI + React), one deterministic core. No Kafka/Kubernetes/microservices — they would
add cost without helping a passenger. Providers, retriever and AI model are behind interfaces, so each can be
replaced without rewriting the app.
