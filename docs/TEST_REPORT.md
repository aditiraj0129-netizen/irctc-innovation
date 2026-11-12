# Test report (final audit, 13 Nov 2026)

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
