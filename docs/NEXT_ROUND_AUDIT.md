# Next-round audit (24 Nov 2026)

Repository: `aditiraj0129-netizen/irctc-innovation`, branch `main`, HEAD `a763762` ("first commit", which only
added one README line on top of the earlier work). Working tree clean.

## Verified baseline (not assumed)

| Suite | Reported earlier | Measured today |
| --- | --- | --- |
| Backend (pytest) | 181 | **192 passed, 0 failed** |
| End-to-end (Playwright, 1 worker) | 14 | **15 passed** |
| Frontend type-check + production build | — | pass |

## Technology found

- **Backend:** Python 3.13, FastAPI, Pydantic v2, PyYAML, httpx, SQLite (stdlib, in-memory by default). It is a modular
  monolith with these modules: `rules` (versioned YAML rules engine, paise maths), `detect` (situation detector),
  `plan` (Connection Scan Algorithm route search, plan builder, ranker, Rights Clock, transfer intelligence,
  counterfactuals), `twin`, `whatif`, `wallet`, `family`, `offline`, `assistant` (keyword intents), `insights`
  (resilience), `community`, `explain` (optional LLM slot-filling with a validator and template fallback), and `store`.
- **Frontend:** React 18, Vite 5, TypeScript, plain CSS (one `styles.css`), a hash router, polling hooks,
  IndexedDB (offline card), a service worker, and the Web Speech API.
- **Data:** everything is simulated (trains `90xxx`, 6 scenarios), with a `RailDataSource` protocol and an
  `OfficialSource` stub. There is no live NTES/IRCTC access.
- **AI today:** an optional LLM fills explanation slots (validated), and an optional LLM can pick an assistant intent.
  There is no retrieval (RAG), no tool calling, and no natural-language What-If.

## Problems found

### UI / UX
1. **No real home.** `#/` is a PNR form plus a list of demo PNRs. There is no dashboard, no "my journeys", and no
   overview of active disruptions.
2. **The navigation is shallow and inconsistent.** Some screens have a 5-tab section nav; Family, Presenter and the
   home screen have none. "More" hides six tools behind tiles.
3. **No desktop layout.** Everything is a 560 px phone column, even on a laptop.
4. **The disruption story is spread out.** The alert is on Overview, the consequences are in the twin, and the
   options are on another tab. There is no single "what happened / what it means / what to do" view.
5. **What-If is a vertical list**, not a side-by-side comparison.
6. **The assistant is a single question/answer box**, not a conversation. It doesn't cite sources and doesn't remember
   context.
7. **Accessibility:** there is no large-text, high-contrast or simple-language mode. Some labels are only colour
   coded (badges).
8. **Polling:** up to three components poll the backend every 3–5 s each. It pauses when the tab is hidden, but it is
   still chatty.
9. **Design tokens:** colours exist as CSS variables, but spacing, radius and type scale are ad hoc. Some components
   repeat similar card markup.

### Backend / intelligence
10. **The connected journey is implicit.** The twin computes legs and transfers, but there is no explicit graph of
    dependencies that shows how a delay propagates step by step.
11. **No grounded knowledge base.** Rule sources live in YAML, but the assistant can't retrieve and cite them.
12. **The assistant can't use tools.** It maps keywords to fixed answers, and an LLM, if configured, only picks an
    intent.
13. **What-If parameters only come from sliders.** There is no natural-language entry ("what if I wait 20 minutes").
14. **No provider interfaces** for train status, stations, rules, AI model or retrieval, beyond the data source.
15. **No API versioning, no idempotency** on claim updates, and no caching.
16. **No user accounts.** Journeys are global demo scenarios. Acceptable for a prototype, but must be documented.

### Security (already fixed in the previous audit and re-checked)
Path traversal is blocked, the rate limit reads the real client IP behind the proxy, `DEMO_TOKEN` protects the
presenter, security headers are set, and community reports can't fake extra reporters. **New risk to manage now:**
adding LLM tool calling and retrieval adds prompt-injection and tool-misuse risk.

### Only simulated
Train running status, timetables, seat availability, station walking times, passenger reports (seeded), and
journeys/PNRs. The rules are real but partly unverified (see the rules table in `DEMO_AND_PITCH.md`).

## Prioritised plan (this round)

| # | Work | Why first |
| --- | --- | --- |
| 1 | **App shell + design system:** tokens, desktop/mobile layout, bottom nav (mobile) and side nav (desktop), accessibility modes (large text, high contrast, simple language) | Every later screen builds on it |
| 2 | **Home dashboard + My Journeys** (with a backend summary endpoint) | First 30 seconds of the demo |
| 3 | **Journey Recovery Graph** (backend): explicit nodes/edges, delay propagation, recovery and rights re-evaluation; new **Bhopal → Delhi → Chandigarh** scenario | The core innovation the round asks for |
| 4 | **Disruption Centre + graph timeline UI**: what happened, when updated, affected legs, consequence, urgency, next steps | Makes the graph visible |
| 5 | **What-If side-by-side comparison** | Asked explicitly |
| 6 | **Grounded railway knowledge (RAG):** curated source documents, chunking with metadata, retrieval behind a pluggable store, citation-only answers, "no reliable source" refusal | Real, testable AI |
| 7 | **Controlled Copilot:** strict tool allowlist, schema-validated arguments, deterministic planner fallback, optional LLM planner, injection defences, numbers checked against tool results; natural-language What-If | Real, safe AI |
| 8 | **Provider interfaces, `/api/v1` alias, TTL cache, idempotent claims** | Proportional scalability |
| 9 | Tests for all of the above, then the full suites | No claim without a test |
| 10 | Docs (AI architecture, data trust and privacy, product strategy), real screenshots, commit, final zip | Deliverables |

## Constraints that change the brief (stated honestly)

- **No embedding model can be downloaded** in this workspace (model hubs are blocked). Retrieval uses BM25 lexical
  ranking behind a `Retriever` interface. An embedding or pgvector implementation can be swapped in later without
  changing callers.
- **Official PDFs cannot be downloaded here.** The knowledge base is a small curated set of documents written in our
  own words, each with its official source URL, effective date, version and verification status. Unverified items
  are marked as such and are never presented as confirmed.
- **No LLM key is configured.** The Copilot's deterministic planner is the default and is fully tested. The LLM
  planner is implemented and tested with fake models, but not against a real provider.
- **I can't write to your Mac's Downloads folder or push to GitHub from this workspace.** The final zip is delivered
  here with a one-line command to move it into `~/Downloads/agla-kadam 4.zip`, and the commit is made locally for
  you to review and push.
