# Test report

## Station Intelligence + product audit (24 Nov 2026)

| Suite | Count | Result |
| --- | --- | --- |
| Backend (pytest) | **314** = 279 before + 35 new (`tests/test_station_intelligence.py`) | **314 passed, 0 failed, 0 skipped** |
| End-to-end (Playwright, phone size, 1 worker) | **31** = 25 before + 6 new (`e2e/station.spec.ts` 26–30, `e2e/decide.spec.ts` 31) | **31 passed** |
| TypeScript check / production build | — | pass / pass |

No existing test was changed, skipped or deleted.

| Area | Tests |
| --- | --- |
| Station graph built from YAML, every element has a verification level | graph tests in `test_station_intelligence.py` |
| Dijkstra routes, three profiles, step-free uses lifts only, lift status always unknown | route tests |
| Platform statuses Confirmed / Reported / Scheduled / Predicted (5 of last 7) / Unknown, stale after 45 min, platform change | platform tests |
| Feasibility classes, unknown platform → Cannot assess (no invented route), capping when not confirmed, recalculation after a change | feasibility tests + E2E 26, 27 |
| Station API: input validation, unknown station, bad node, passenger platform entry checked against the journey | API tests + E2E 28 |
| Unavailable message shown exactly | `test_...unavailable...` + E2E 29 |
| Find mode: QR-style link, search, empty result | E2E 30 |
| Copilot station questions (9, EN + HI); LLM cannot invent a platform | Copilot tests |
| Screens agree (Journey/Disruption show the Decide outlook); What-If marks repeated results | E2E 31 |
| Directions never say "towards Platform 16" while on Platform 16 | `test_platform_walk_never_says_towards_the_same_platform` |

Bugs found and fixed: see [PRODUCT_AUDIT.md](PRODUCT_AUDIT.md) §2.

Not tested here: any live platform feed (none exists publicly), real station geometry (schematic only), real lift status, real walking times.

---

## Decision upgrade (24 Nov 2026)

| Suite | Count | Result |
| --- | --- | --- |
| Backend (pytest) | **279** = 231 before + 48 new (`tests/test_decision_engines.py`) | **279 passed, 0 failed, 0 skipped** |
| End-to-end (Playwright, phone size, 1 worker) | **25** = 20 before + 5 new (`e2e/decide.spec.ts`) | **25 passed** |
| TypeScript check / production build | — | pass / pass |

No existing test was changed, skipped or deleted.

| Area asked for | Tests |
| --- | --- |
| Delay trend calculations | `test_trend_recovering_growing_and_steady`, `test_baseline_model_rules_are_transparent`, `test_a_sudden_jump_is_not_extrapolated_as_a_trend` |
| Missing observations / stale train data | `test_missing_observations_give_insufficient_evidence_not_a_guess`, `test_stale_running_data_gives_no_range` |
| Shared-route matching / false congestion correlations | `test_shared_section_matching_counts_only_trains_just_ahead`, `test_false_congestion_correlations_are_rejected` (behind us, on time, old reading, other corridor, opposite direction) |
| Fog warning expiry / weather provider unavailable | `test_fog_warning_applies_only_on_route_ahead_and_while_valid`, `test_weather_provider_unavailable_is_reported_not_crashing` |
| Connection feasibility / transfer buffers | `test_connection_feasibility_uses_the_whole_range` (5 scenarios), `test_transfer_buffer_depends_on_passenger_needs` |
| Alternative ranking / duplicate trains / none available | `test_ranking_is_explained_and_follows_priority`, `test_no_duplicate_or_dominated_trains`, `test_no_alternative_available_gives_a_clear_reason` |
| Seat availability unknown / provider failures | `test_seat_availability_and_fares_are_never_invented`, `test_buses_only_from_a_configured_provider` |
| Unreserved travel eligibility | `test_unreserved_eligibility_rules` |
| Refund comparison / missing ticket info / not every missed connection qualifies | `test_refund_comparison_cancel_now_vs_later`, `test_dont_cancel_when_a_claim_is_worth_more`, `test_missing_ticket_information_is_explained`, `test_missed_connection_does_not_automatically_qualify` |
| Never a blank section | `test_every_card_is_filled_never_blank` (all 13 demo journeys × 6 cards) |
| Six demo scenarios end to end | `test_six_demo_scenarios_end_to_end` + E2E 21–25 |
| AI hallucinated train data / invalid tool calls / no RAG source | `test_copilot_rejects_hallucinated_train_data`, `test_invalid_tool_calls_are_refused`, `test_rag_cites_unreserved_and_tatkal_guidance_or_says_no_source`, `test_copilot_decision_questions` (8 questions) |
| Evaluation maths (no model evaluated) | `test_evaluation_maths_on_hand_made_numbers` |

Bugs found and fixed during this work:
- **Two delay readings 5 min apart were read as a huge trend.** Fixed with a 30-minute minimum span and a ±60 min cap, and a test was added.
- **The mobile section tabs scrolled sideways and hid "Wallet".** Fixed: two rows on phones.
- **A new translation key replaced the Options screen's "Why this is first" heading.** Fixed by renaming the key.
- **A backup train's boarding station was shown as New Delhi when it leaves from Nizamuddin.** Fixed.

Not tested here: real IMD, NTES, availability or bus data (not available); calibrated probabilities (no history);
a real paid LLM (tested with fake LLMs).

---

## Next round (24 Nov 2026)

Environment: Linux workspace, Python 3.13, Node 22, system Chrome for Playwright (phone size, 1 worker).

| Suite | Count | Result |
| --- | --- | --- |
| Backend (pytest) | **231** = 192 before + 39 new | **231 passed, 0 failed, 0 skipped** |
| End-to-end (Playwright) | **20** = 15 before + 5 new | **20 passed** |
| TypeScript check / production build | — | pass / pass |

No existing test was deleted, skipped or changed (all new tests are in new files:
`test_journey_graph.py`, `test_knowledge_copilot.py`, `test_reliability.py`, `e2e/nextround.spec.ts`).

New coverage:

| Area | Tests |
| --- | --- |
| Journey graph and delay propagation (2- and 3-train journeys, cancelled, stale, conflicting events, passenger profile) | `test_journey_graph.py` (7) |
| Disruption Centre: urgency, rights, no advice on stale data | `test_recovery_rights_and_urgency`, `test_recovery_stale_gives_no_advice` |
| RAG: provenance on every chunk, EN/HI/Hinglish retrieval, expired rules filtered, no-source refusal, injection dropped at ingestion, LLM rewording validated | `test_knowledge_copilot.py` |
| Copilot: tool allow-list and argument validation, hypothetical tools never store events, natural-language What-If (parametrised), out-of-range asks back, prompt injection, stale refusal, unsafe LLM plans rejected, PNR/phone/email removed before any LLM call | `test_knowledge_copilot.py` |
| Reliability: provider stubs refuse, TTL cache, idempotent claims, health | `test_reliability.py` |
| E2E 16 home dashboard (only journey ids stored, never the PNR) · 17 central Bhopal→Delhi→Chandigarh flow (twin → disruption → options → What-If compare → Wallet) · 18 Copilot natural-language What-If with tools and source · 19 Copilot ignores an instruction to invent a refund · 20 accessibility settings persist | `e2e/nextround.spec.ts` |

Bugs found during this round and fixed: translation keys from the new screens overwrote older ones
(e.g. "deadline not yet officially confirmed" in Hindi) — caught by E2E 4, keys renamed; Copilot marked a
rules-engine answer as "no reliable source" — fixed and tested; Copilot "open family" link pointed to a
non-existent page — now opens the journey's More page; mobile and desktop navigation shared test ids — split.

Not tested here: a real paid LLM (tested with a fake LLM), real IRCTC/NTES data (not available),
screen-reader software (labels, landmarks and keyboard order were added but not checked with NVDA/VoiceOver).

---

## Earlier: final audit (13 Nov 2026)

Environment: Linux workspace, Python 3.13, Node 20+, system Chrome for Playwright.
The user's MacBook Air also ran the suite before the audit fixes: **181 backend + 14 E2E passed** (after the
one-worker fix). Re-run on the Mac after unzipping this version.

## Final results

| Suite | Count | Result |
| --- | --- | --- |
| Backend (pytest) | **192** = 119 original + 62 upgrade + 11 audit | **192 passed, 0 failed, 0 skipped** |
| End-to-end (Playwright, phone size, 1 worker) | **15** = 6 original + 8 upgrade + 1 audit | **15 passed** |
| TypeScript check / production build | — | pass / pass |
| Real HTTP server check (curl, `DEMO_TOKEN` set) | traversal URLs, demo token, headers | traversal returns the app page; demo 403 without token, 200 with; headers present |

No existing test was deleted, skipped or weakened (`git diff` on old test files shows additions only).

## Bugs found and fixed

| # | Severity | Bug | Fix | Guarded by |
| --- | --- | --- | --- | --- |
| 1 | **Critical** | `GET /..%2F..%2FREADME.md` read any file on the server, including `backend/.env` | Serve only files inside `frontend/dist` | `test_no_file_outside_the_frontend_can_be_read` (4 URL forms) + curl |
| 2 | High | Behind Render's proxy every user shared one rate limit → lockout during judging (found by reading code; not testable without Render) | `--proxy-headers` in Dockerfile; forget quiet addresses | `test_rate_limiter_forgets_quiet_addresses` |
| 3 | High | Presenter endpoints open to anyone on a public link | Optional `DEMO_TOKEN` header; token box on presenter page | `test_demo_token_protects_presenter_endpoints` + curl |
| 4 | High | Refund from an announced (not notified) rule shown as "Automatic"; assistant gave it without warning, added a TDR note to cancellations, and showed raw codes | "Estimate: rule not yet confirmed" pill; assistant warnings and plain words | 2 backend tests + E2E 15 |
| 5 | Medium | One person could fake many station reporters with a header → "HIGH confidence" | One caller = one reporter | `test_one_caller_cannot_pretend_to_be_many_reporters` |
| 6 | Medium | Core rule cited a Scribd upload | Statute text (Rule 13(1), 2015 Rules); govt publication for 2026 slabs | `test_rule_sources_are_not_file_sharing_sites_for_core_rules` |
| 7 | Medium | No security headers; `render.yaml` CORS `*` | Headers on every response; CORS removed from render.yaml | `test_security_headers_on_every_response` |
| 8 | Low | 0.74rem text; polling while tab hidden | Larger text; polling pauses when hidden | manual check (no test) |
| 9 | (upgrade) | Cancellation known days early hidden as "not watching yet" | Report immediately | `test_cancellation_known_days_early_is_shown_immediately` |
| 10 | (upgrade) | E2E tests clashed when run in parallel on the Mac | `workers: 1` | full E2E run |

## Core passenger scenarios (Phase 2)

| # | Scenario | Detection | Rights / money | Deadline | Ranking + why | Stale / missing data | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | > 3 h late | LATE_OVER_3H | TDR ₹1,180 if approved (Rule 13(1)) | before actual departure 17:10 | TDR plans first for money | 170 min → TDR removed | E2E 2, 8, 11; backend TDR tests |
| 2 | Missed connection | CONNECTION_AT_RISK, twin BROKEN | ₹455 if approved | 09:15, marked unverified | 90205+90601 first; why + counterfactuals | — | E2E 4, 7 |
| 3 | WL after chart | WAITLISTED_AFTER_CHART | ₹2,140 automatic (₹60 clerkage × 4) | none needed | auto refund + alternative | — | E2E 3 |
| 4 | Train cancelled | TRAIN_CANCELLED (even days early) | full refund automatic | — | alternatives | — | API tests |
| 5 | Family on 2 PNRs | divergence | ₹4,830 together / ₹3,180 split | — | together first under FAMILY | — | E2E 9, backend family tests |
| 6 | Wait vs cancel vs alternative | — | each from rules engine | per option | What-If 7 scenarios | — | E2E 7 |
| 7 | Near a deadline | Rights Clock windows | — | decide-by time | — | — | Rights Clock tests |
| 8 | Stale data | STALE_DATA | no TDR asserted | — | only "use official channel" | assistant refuses, What-If NO_SAFE_ADVICE | E2E 6, backend tests |
| 9 | Offline card | — | masked snapshot | — | top 3 plans | labelled "not live" | E2E 10 |
| 10 | Hindi/Hinglish | — | same numbers | — | — | — | E2E 11, 14; intent tests |

## Not tested / cannot be tested here

- **Render deployment and Docker build** (no Docker daemon in this workspace; not deployed).
- **Rate limiting behind a real proxy** (logic tested; proxy behaviour needs Render).
- **Real microphone voice input and spoken output** (needs a phone/browser with mic). Text path is tested.
- **Cold reload of the whole app while offline** (service worker). Saving and viewing the card offline is tested.
- **Screen readers and real users** (no usability study was done).
