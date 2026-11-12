# Test report (upgrade)

Run on 13 Nov 2026 in a Linux workspace: Python 3.13, Node 20+, Chrome (system) for Playwright.

## Summary

| Suite | Before upgrade | After upgrade | Result |
| --- | --- | --- | --- |
| Backend (pytest) | 119 | **181** (119 original + 62 new) | **181 passed, 0 failed** |
| End-to-end (Playwright, Pixel 7 size) | 6 | **14** (6 original + 8 new) | **14 passed, 0 failed** (run 3 times, stable) |
| TypeScript type-check (`tsc --noEmit`) | pass | pass | pass |
| Production build (`vite build`) | pass | pass | pass |

**No existing test was deleted, weakened or skipped.** `git diff` on the old test files shows additions only:
3 new tests in `test_invalid_inputs.py` (rule metadata) and one fixture in `conftest.py` that empties the
rate-limit window before each test (the limiter itself stays on and is still tested by the API).

## Backend tests by file

| File | Tests | Covers |
| --- | --- | --- |
| test_cancellation.py | 33 | refund slabs, exact boundaries, rule sets by date and category |
| test_detector.py | 18 | situations, stale data, thresholds |
| test_invalid_inputs.py | 17 | invalid inputs + **new**: rule metadata, unverified sources flagged |
| test_explainer.py | 15 | LLM failures, validator, templates |
| test_api.py | 12 | original API |
| test_tdr_and_auto.py | 12 | TDR 3-hour rule, automatic refunds |
| test_routing_ranking.py | 8 | Connection Scan, ranking |
| test_scenarios_and_clock.py | 7 | the 4 original scenarios, clock |
| **test_twin_transfer.py** | 14 | transfer class boundaries (−1, 0, 9, 10, 24, 25 min), required time by profile, infeasible alternatives dropped, "fewest changes" priority, twin states for missed / small delay / high-risk / senior / normal / cancelled, stale marking |
| **test_whatif_decisions.py** | 9 | all 7 scenarios, deterministic output, options lost by waiting, hypothetical events never stored, not-applicable reasons, invalid parameters, counterfactuals only from calculated scenarios, resilience transparency |
| **test_wallet_family.py** | 6 | wallet stages and rule metadata, no cancel estimate for an auto-refunded ticket, forward-only claim steps, export never guarantees, family divergence and together-first ranking, money from rules, labels only |
| **test_offline_assistant_community.py** | 16 | masked offline card, 8 intents in EN / HI / Hinglish, answers from backend facts, stale data → no advice, an LLM cannot inject numbers, LLM failure fallback, duplicate reporters, confidence, conflict, expiry, phone/email rejected, **recommendations identical with and without reports** |
| **test_api_upgrade.py** | 14 | every new endpoint, 404s, 422 validation (what-if ranges, priorities, profile, claim steps, assistant text/lang), preferences affect transfers, export download, old assessment fields kept, recommendation hidden when stale, seeded reports labelled, cancelled-train flow, early cancellation shown |

## End-to-end tests

| # | Test | Status |
| --- | --- | --- |
| 1–6 | Original: normal journey, 3-hour edge, waitlisted family, missed connection in Hindi, invalid PNRs, stale data | pass (unchanged) |
| 7 | Twin shows "Change not possible" → Options shows why + counterfactuals → What-If shows ₹455 and options lost after a long wait | pass |
| 8 | Wallet: "You can file", announced-rule warning and version, mark as filed, history, export download | pass |
| 9 | Family group: divergence, "Whole group" option first, split options labelled "Splits the group" | pass |
| 10 | Offline card: masked PNR, save, **network switched off** → offline banner + saved card + 139 | pass |
| 11 | Assistant: Hinglish question → ₹1,180 + TDR-LATE-3H + "rules engine", with no AI key; deadline chip → 17:10 | pass |
| 12 | Community: "never change" notice, conflict shown, phone number rejected, report added, plans unchanged | pass |
| 13 | Step-free + senior saved → transfer badges; resilience "Experimental" | pass |
| 14 | Hindi on What-If and Wallet | pass |

## Problems found while testing (and what was done)

1. **Real bug:** a cancellation known days early showed "not watching yet". Fixed in the detector; regression test added.
2. Many API calls from one IP in E2E tripped the 240/min rate limit. The Playwright server alone now starts with
   `RATE_LIMIT_PER_MIN=5000`; the product default is unchanged.
3. Two of my own new test inputs were wrong (a clock jump larger than the allowed 24 h, and a phrase that
   contained a refund keyword). The tests were corrected, not the product.
4. UI review from screenshots: the What-If column "vs best now" actually compared with the booked arrival, so it
   was renamed; "Arrivals spread 0m" was hidden when some family members don't travel.

## Not tested / not verified

- **Real voice input**: the speech-recognition button needs a real browser with a microphone; E2E covers text input
  and checks the button is disabled where unsupported. Read-aloud uses `speechSynthesis` and was not heard in tests.
- **Service worker reload offline**: E2E checks the saved card when the network drops on an open page. A full
  cold reload while offline (app shell from the service worker) was not automated.
- **Docker image**: `docker build` could not run here (no Docker daemon). Not verified.
- **Deployment**: not deployed. No live URL exists.
- Screen readers were not tested; buttons have labels and sizes ≥ 40–48 px.
