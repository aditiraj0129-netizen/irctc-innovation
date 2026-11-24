# Data trust and privacy

## Where every fact comes from

| Data | Source today | Label shown in the app |
| --- | --- | --- |
| Train running status, delays, chart status | **Simulated** scenarios (`backend/app/data/scenarios/`) | "Simulated data" strip on every page; `source: SIMULATED` on each event |
| Timetable (trains 90xxx) | **Invented** trains; real station codes | "Trains shown are simulated" |
| Minimum transfer times per station | **Simulated estimates** (`station_transfer.yaml`) | "Transfer times are simulated estimates, not official" |
| Refund / TDR rules | Versioned YAML with source URL, version, effective dates, legal status | Rule id, version, "official rule" / "announced, not confirmed" / "needs checking" |
| Community reports | Passengers, unverified, expiring | "Unverified", never used by advice |

**Never shown as live:** each fact carries a freshness state (FRESH / STALE / NONE) and its age. When data is stale,
the app and the Copilot stop advising and point to official channels (139, NTES, RailOne).

**Never invented:** no prices of new tickets ("check IRCTC"), no seat availability ("seats not checked"),
no promise of a refund ("estimate", "if approved"; a TDR is decided by the Zonal Railway).

## What is stored, and where

| Where | What | Not stored |
| --- | --- | --- |
| Phone/browser `localStorage` | Journey **ids** (e.g. `bhopal_delhi_chandigarh`), short activity labels, language, accessibility choices | PNR, names, phone numbers |
| Phone/browser IndexedDB | Offline card (PNR **masked** as `81xxxxxx07`) — only when the passenger taps Save | Full PNR |
| Server SQLite (`STORE_PATH`, in-memory by default) | Claim stage updates, preferences, community reports (reporter as a **hash**), idempotency keys | Raw IPs, names |

Settings → "Clear saved journeys on this device" removes the local list, activity and the offline card database.

## AI and personal data

- AI is optional (`LLM_ENABLED=false` by default).
- Before anything is sent to an AI model, `redact()` removes 10-digit numbers (PNR or phone), +91 phone numbers and
  emails from the question, the chat history and the tool facts. Tool results already use the masked PNR.
- The AI never receives credentials and cannot call anything that changes a booking.

## Security basics (from the earlier audit, still in place)

Per-IP rate limit; strict input validation (422); path-traversal-safe static serving; security headers;
optional `DEMO_TOKEN` for presenter endpoints; no secrets in the repo (`.env` is git-ignored, `.env.example` provided);
`Idempotency-Key` support on claim updates so a double tap can't record two updates.

## Before real deployment (not done, needs a partner)

Authorised access to IRCTC/NTES data; a legal review of the rules corpus against Gazette text; a privacy notice and
consent screen; server-side encryption if real PNRs are ever stored.
