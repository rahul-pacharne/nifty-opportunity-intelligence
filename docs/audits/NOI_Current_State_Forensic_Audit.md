# NOI Current-State Forensic Audit

**Audit date:** 27 Nov 2026 (Asia/Calcutta)  
**Method:** Code-first reconstruction. Docs treated as claims only.  
**Scope:** Read-only. No project files modified.  
**Repo:** `github.com/rahul-pacharne/nifty-opportunity-intelligence`  
**Local path:** `/agent/repos/nifty-opportunity-intelligence`

---

## 1. Executive Summary

**What NOI actually does:** It is a **CLI toolkit**, not a continuous decision-support platform. Four one-shot scripts exist. Only `scripts/run_scheduled_check.py` makes decisions — and only during three IST windows. It fetches Upstox quotes (Nifty, Bank Nifty, India VIX), stores them in Postgres, computes a **T+1 historical gap base-rate**, and may send Telegram **NO_TRADE** or **WATCH** messages. BUY/SELL alerts are skipped. No broker orders are placed.

**What it does well:** Modular layout; Upstox quote client; OHLC quarantine + 20-minute stale gate on ingest; Postgres persistence with delivery dedupe; IST clock labels; explicit “no broker order” disclaimers; substantial unit/acceptance test surface.

**What it does poorly / not at all:** No daemon/API/scheduler process; no option-chain profitability on the live path; “ML” class names are stubs; probabilities are unconditional historical frequencies; regime/breadth/FII/global/macro mostly schema or unwired libraries; signal FSM not driven in production; WhatsApp/email do not send; no outcome learning loop.

**Functional today?** Partially — as quote ingest + optional Telegram watch/no-trade ticks, if env vars, Postgres, and an external cron exist.

**Ready for paper alerts?** No.  
**Ready for real decision-support alerts?** No.

---

## 2. Verdict in One Paragraph

NOI today is **not** the product described in `docs/PROJECT_MASTER.md`. The live path is: CLI script → IST activity check → Upstox GET quotes → Postgres → `BaseRateModel` (historical gap frequencies, T+1 only) → eligibility with `quote=None` → almost always NO_TRADE or WATCHLIST → Telegram for those two only. Everything that looks like a full intelligence platform (regime, options BS, research gate, paper mode, signal lifecycle, WhatsApp, email, FastAPI, APScheduler) is mostly **library or schema theater**, unused by the production scripts.

---

## 3. Repository Inventory

| Component | File/Directory | Purpose | Status |
|---|---|---|---|
| Entry scripts | `scripts/*.py` | Only runnable entry points | FULLY / PARTIAL |
| Config | `app/core/config.py` | Env Settings | PARTIAL (risk fields unused by decision path) |
| Constants | `app/core/constants.py` | Enums/defaults | FULLY IMPLEMENTED |
| Logging | `app/core/logging.py` | Logging helpers | UNUSED by scripts |
| Upstox quotes | `app/data/upstox_quotes.py` | Only live market API | FULLY IMPLEMENTED |
| Validation | `app/data/validation.py` | OHLC + optional stale | FULLY IMPLEMENTED |
| Calendar | `app/data/calendar.py` | Weekends; holidays empty by default | PARTIAL |
| Repository | `app/data/repository.py` | In-memory observation store | FULLY IMPLEMENTED |
| Schedule | `app/runtime/schedule.py` | IST activity labels | FULLY IMPLEMENTED |
| Scheduled check | `app/runtime/scheduled_check.py` | Production tick path | PARTIAL |
| Decision loop | `app/runtime/decision_loop.py` | Base-rate → recommendation | FULLY (BUY unreachable live) |
| Session | `app/runtime/session.py` | Wire store/loop/gateway | FULLY |
| Persistence | `app/runtime/persistence.py` | Postgres I/O | FULLY |
| Live runner | `app/runtime/live_runner.py` | Clock with buy flag | UNUSED by scripts |
| Research gate | `app/runtime/research_gate.py` | Brier vs baseline | UNUSED |
| Orchestrator | `app/runtime/orchestrator.py` | 9-line gate | PLACEHOLDER / UNUSED |
| Health | `app/runtime/health.py` | Pure status function | UNUSED by scripts |
| Paper | `app/runtime/paper.py` | Paper publish helper | UNUSED |
| Exits | `app/runtime/exits.py` | Position book / sell reasons | IDLE on script path |
| Telegram gateway | `app/runtime/telegram_gateway.py` | Outbound + command stubs | PARTIAL |
| Prediction | `app/intelligence/prediction.py` | Base-rate + stub “ML” | PARTIAL / PLACEHOLDER |
| Regime | `app/intelligence/regime.py` | Rule classifier | UNWIRED |
| Features | `app/features/*` | EMA/RSI/ADX/BB/breadth/events | MOSTLY DEAD CODE |
| Gaps research | `app/research/gaps.py` | Gap labeling T+1/T+2/T+3 | FULLY (research math) |
| Options pricing | `app/options/pricing.py` | Black–Scholes | LIBRARY UNWIRED |
| Options eligibility | `app/options/eligibility.py` | BUY/NO_TRADE filters | HALF-WIRED |
| Signals lifecycle | `app/signals/lifecycle.py` | FSM | LIBRARY UNWIRED |
| Notifications | `app/notifications/*` | Templates + Telegram API | PARTIAL |
| Tracking | `app/tracking/outcomes.py` | Scorecard helpers | UNWIRED |
| Migrations | `migrations/*.sql` | Schema | PARTIAL (many tables unwritten) |
| Docker | `Dockerfile` | CMD = pytest | NOT an app runner |
| Compose | `docker-compose.yml` | Postgres 16 only | PARTIAL |
| Docs | `docs/*` | Vision / samples | SUPPORTING CONTEXT ONLY |
| Tests | `tests/**` | ~139 named tests | PRESENT (not run in this env) |

**Dependencies (`pyproject.toml`):** `psycopg[binary]` only. Optional `pytest`. No FastAPI, APScheduler, pandas, scikit-learn in declared deps.

**Env (`.env.example`):**
- `NOI_DATABASE_URL`
- `NOI_LOG_LEVEL`
- `NOI_STRONG_GAP_PERCENT`
- `NOI_MAX_OVERNIGHT_POSITIONS`
- `NOI_MAX_RISK_FRACTION`
- `NOI_STRATEGY_CAPITAL`
- `NOI_TELEGRAM_ALLOWED_USER_IDS`
- `NOI_TELEGRAM_BOT_TOKEN`
- `UPSTOX_ACCESS_TOKEN`

---

## 4. Architecture as Implemented

```text
[External cron / human]
        |
        v
scripts/run_scheduled_check.py   (also: fetch_quotes, check_database, send_telegram_test)
        |
        +--> schedule.scheduled_activity (IST labels)
        |
        +--> Upstox GET /v2/market-quote/quotes
        |
        +--> Postgres (market_observations, predictions, signals, deliveries)
        |
        +--> DecisionLoop.decide
                |
                +--> gap_observations (T+1 only)
                +--> BaseRateModel.fit/predict
                +--> eligibility.decide (quote=None => NO_TRADE)
        |
        +--> TelegramGateway.deliver (NO_TRADE / WATCHLIST only)
```

**Not in the live call graph:** FastAPI, APScheduler, regime, BS pricing, research_gate, paper, orchestrator, health probes, WhatsApp HTTP, email SMTP, Telegram inbound poller, option chain collectors, FII/DII/global/macro collectors.

---

## 5. Actual Runtime Execution Flow

### Entry points

| Entry | What it does |
|---|---|
| `scripts/check_database.py` | Migrate DB; audit row; print counts |
| `scripts/fetch_quotes.py` | Fetch Upstox quotes → Postgres |
| `scripts/run_scheduled_check.py` | One IST tick; maybe decide + Telegram |
| `scripts/send_telegram_test.py` | One Telegram smoke message |
| Docker CMD | `python -m pytest` — tests only |
| docker-compose | Postgres only — no app service |

### `run_scheduled_check.py` flow

```text
Application Start (CLI)
    ↓
Load .env → Settings
    ↓
now = UTC now
    ↓
scheduled_activity(now)  [Asia/Kolkata]
    ↓
If activity NOT in {premarket_collection, prediction_refresh, final_trade_eligibility}
    → print activity / sent: none → EXIT
    ↓
Require UPSTOX_ACCESS_TOKEN + Telegram token + allow-list
    ↓
open_runtime → Postgres migrate; load decisions/positions/sent
    ↓
fetch_index_quotes → store with max_age=20 minutes
    ↓
Require NIFTY + BANKNIFTY + INDIA_VIX quality OK else degraded → EXIT
    ↓
DecisionLoop.decide(NIFTY) and decide(BANKNIFTY)
    [quote=None, capital=None]
    ↓
If NO_TRADE → Telegram no_trade(...)
If WATCHLIST → Telegram early_warning(...)
Else (BUY_*) → continue (skip send)
    ↓
Close store; print activity/action/sent → EXIT
```

**Continuous daemon?** No.  
**Broker orders?** No.

---

## 6. Scheduling and Runtime Behaviour

| Job label | IST window | Script acts? | Status |
|---|---|---|---|
| overnight_global_analysis | 06:30–08:00 | No | PLACEHOLDER (label only) |
| premarket_collection | 08:00–09:15 | Yes | PARTIAL |
| opening_assessment | 09:15 exact | No | UNUSED by script |
| live_monitoring | 09:15–12:00 | No | PLACEHOLDER |
| midsession_assessment | 12:00–14:00 | No | PLACEHOLDER |
| overnight_opportunity_evaluation | 14:00–14:30 | No | PLACEHOLDER |
| prediction_refresh | 14:30–15:00 | Yes | PARTIAL |
| final_trade_eligibility | 15:00–15:20 | Yes | PARTIAL |
| post_close_derivatives | 15:20–16:00 | No | PLACEHOLDER |
| evening_forecast | 16:00–22:00 | No | PLACEHOLDER |
| maintenance / holiday | else / weekend | No | PARTIAL (no NSE holiday list) |

**Answers:**
1. Continuous? **No**
2. Market hours only? **No daemon** — external cron must call the script
3. Overnight analysis? **Label only**
4. Premarket? **Yes**, if cron hits 08:00–09:15 IST
5. After close? **prediction_refresh / final_trade_eligibility** yes; evening no
6. Monitor signals after create? **Not on script path**
7. Can signals be updated? **Not in production**
8. Can signals be invalidated? **Library only**
9. Missed-job recovery? **No** — one-shot; no catch-up

**Restart:** Process dies. Postgres retains bars, decisions, deliveries, manual_trades. `open_runtime` reloads decisions/positions/sent. Dedup prevents re-Telegram of same `(signal_id, alert_type)`.

---

## 7. Data Sources

| Data Category | Actual Provider | Data Retrieved | Frequency | Used By | Status |
|---|---|---|---|---|---|
| Nifty / Bank Nifty | Upstox v2 quotes | LTP-derived OHLC bars | On script invoke | DecisionLoop | LIVE |
| India VIX | Upstox | Index quote | On invoke | Freshness gate only | COLLECTED, UNUSED IN MODEL |
| Intraday candles | — | — | — | — | NOT IMPLEMENTED |
| Option chain / OI / IV | — | DDL `option_snapshots` | — | — | SCHEMA ONLY |
| FII / DII | — | DDL `derivatives_positions` | — | — | SCHEMA ONLY |
| Global / GIFT | — | DDL `global_market_data` | — | — | SCHEMA ONLY |
| Macro / events | — | DDL `macro_events` | — | — | SCHEMA ONLY |
| Holidays | MarketCalendar | Empty frozenset by default | — | schedule | PARTIAL |

**Only live market HTTP API in app data layer:**  
`https://api.upstox.com/v2/market-quote/quotes` with Bearer `UPSTOX_ACCESS_TOKEN`  
Instruments: `NSE_INDEX|Nifty 50`, `NSE_INDEX|Nifty Bank`, `NSE_INDEX|India VIX`

---

## 8. Data Quality

| Check | Implemented? | Enforced on live path? | Risk |
|---|---|---|---|
| Non-positive / bad OHLC | Yes | Yes | Medium |
| Naive timestamps / lineage | Yes | Yes | Medium |
| Stale > 20 min | Yes if `max_age` passed | Yes in scheduled_check/fetch_quotes | Low on live; HIGH if `decide()` alone |
| Jump vs prior close | Code exists | Never passed from ingest | HIGH |
| NSE holidays | Mechanism | Default empty | HIGH |
| OHLC invented from LTP | Parser fills O/H/L from close | Always | HIGH |
| Incomplete required set | NIFTY+BN+VIX OK required | Yes | OK |

**Can stale/incomplete data drive decisions?** Live scheduled path refuses incomplete/stale *new* quotes. Core `DecisionLoop` alone will forecast from older OK bars if invoked without that gate.

---

## 9. Feature Engineering

| Feature | Formula/Method | Used in decisions? | Status |
|---|---|---|---|
| EMA(5) | α=2/6 EWMA of closes | Stored only — not causal for direction | PARTIAL |
| EMA(20) | For regime | No | UNUSED |
| ATR(14) | Wilder via true range | Regime only | UNUSED |
| ADX / RSI / Bollinger width | Standard | No runtime callers | DEAD CODE |
| advance_decline_ratio | adv/dec | No | DEAD CODE |
| event_proximity_days | abs days | No | DEAD CODE |
| Gap % | 100×(next_open−prior_close)/prior_close | Yes — base-rate inputs | FULLY |

---

## 10. Market Regime Engine

**Status:** IMPLEMENTED LIBRARY, UNWIRED.

`classify_regime` in `app/intelligence/regime.py`:
- Need ≥20 closes
- ATR percentile → VOL_COMPRESSION / VOL_EXPANSION
- Else EMA5 vs EMA20 → BULLISH / BEARISH / SIDEWAYS

Never imported by `DecisionLoop`. `market_regimes` table has **zero writers** in `app/`. Does not affect prediction, options, or risk on the live path.

---

## 11. Opportunity Detection

**No separate OpportunityDetector.**

Gap classes (`app/research/gaps.py`), defaults:
- `gap > 0.75%` → STRONG_UP
- `gap ≥ 0.30%` → MODERATE_UP
- `gap < −0.75%` → STRONG_DOWN
- `gap ≤ −0.30%` → MODERATE_DOWN
- else → FLAT

Live path: historical T+1 gap frequencies → argmax(up/down/flat) → WATCHLIST if flat wins, else eligibility.  
DB `opportunities` rows are persistence of the recommendation, not an independent detector.

---

## 12. Prediction Engine

**Live model:** `BaseRateModel` only.

1. Collect historical T+1 opening gaps from usable bars published ≤ decision_at  
2. Bucket each gap vs θ=0.75%: up / down / flat  
3. Probabilities = counts/N (rounded; remainder forced onto largest bucket)  
4. expected_gap = mean; lower/upper ≈ 25th/75th order stats  
5. Direction = argmax; flat → WATCHLIST; else eligibility  

**Not real ML:** `LogisticGapModel` / `RandomForestGapModel` / `GradientBoostGapModel` are stubs (`fit` ≈ fraction of positive gaps). No `.pkl`/`.joblib` artifacts.

**alerts_approved:** `return len(folds) >= minimum_folds and False` — **always False**.

**Probabilities:** meaningful as sample frequencies; **not** calibrated P(tomorrow | today).  
**Confidence:** not calculated (`data_sufficient` = non-empty history).  
**T+2/T+3:** labeling helpers exist; **live hardcodes T+1**.

---

## 13. Options Evaluation

| Capability | Code | Live path | Status |
|---|---|---|---|
| Black–Scholes price/Greeks | `options/pricing.py` | Never imported by runtime | LIBRARY |
| Implied vol solver | Absent | — | NOT IMPLEMENTED |
| Expiry selection | Absent | — | NOT IMPLEMENTED |
| select_by_delta | `eligibility.py` | Tests only | UNWIRED |
| Delta bands 0.45–0.55 / 0.60–0.70 | Hardcoded | If quote present | HARDCODED |
| Spread ≤ 5%, volume ≥ 1 | `decide()` | If quote present | IMPLEMENTED |
| Premium × qty ≤ 1% capital | `decide()` | capital=None live → NO_TRADE | UNREACHABLE LIVE |
| EV = P(win)×… | `expected_value()` | Unused; gate uses gross−costs=0 | UNUSED |
| Option quote feed | Absent | quote=None in scheduled_check | NOT IMPLEMENTED |

**Does it evaluate option profitability today?** **No** on the live path.

---

## 14. Risk Management

| Risk Rule | Actual Logic | Threshold | Enforced? | Location |
|---|---|---|---|---|
| Missing data | no bars → NO_TRADE | — | Yes | decision_loop.py |
| Insufficient history | !data_sufficient | — | Yes | decision_loop.py |
| No option quote | quote is None | — | Yes (blocks BUY) | eligibility.py |
| Max positions | open ≥ max | 1 hardcoded | Hardcoded 0 open / max 1 | decision_loop |
| Max risk fraction | premium×qty > capital×f | 0.01 hardcoded | Ignores Settings | decision_loop |
| Delta band | abs(delta) in bands | 0.45–0.55, 0.60–0.70 | If quote | eligibility |
| Spread / volume | width ≤ 5%; vol ≥ 1 | defaults | If quote | eligibility |
| Min net EV | gross−costs > 0 | 0; live gross=0 | Would fail if reached | eligibility |
| Probability floor | only `is None` check | none | No magnitude floor | eligibility |
| Exit stops | ±premium / time | 20/30 / 6h in script | Book created but unused | exits.py |

---

## 15. Signal Lifecycle

**Library FSM (`app/signals/lifecycle.py`):**
```text
DETECTED → WATCHLIST → CONFIRMED → TRADE_RECOMMENDED → NOTIFIED
  → MANUALLY_ACCEPTED / IGNORED / POSITION_REPORTED → CLOSED → EVALUATED
(+ INVALIDATED / EXPIRED from open states)
```

**Production reality:**
- `save_decision` maps BUY_* → TRADE_RECOMMENDED, WATCHLIST → WATCHLIST, else → DETECTED
- `ON CONFLICT DO NOTHING` — no status updates
- `transition` / `expire_due` / `duplicate_of` never called from runtime scripts
- Actual flow: decide → maybe Telegram → done

---

## 16. Notification System

| Channel | Integration | Functional | Current Usage |
|---|---|---|---|
| Telegram | api.telegram.org sendMessage | Yes (outbound) | NO_TRADE / WATCH on entry ticks |
| WhatsApp | In-memory list + opt-in | No HTTP | Stub / tests |
| Email | String builders only | No SMTP | Format-only |
| SMS / Push | — | — | NOT IMPLEMENTED |

Dedup + 1 retry exist on `TelegramGateway`. L1–L5 priority levels are **not** implemented.

---

## 17. Actual Alert Examples (from code, not SAMPLE_ALERTS fiction)

### Implemented on live path — Early warning
```text
Alert type: Early warning
Signal ID: {signal_id}
Market: {NIFTY|BANKNIFTY}
Recommendation: WATCH
No trade recommended at this stage.
```

### Implemented on live path — NO TRADE
```text
Signal ID: {signal_id}
Action: NO TRADE
Reason: {data_quality}
A no-trade decision is a successful risk-management outcome.
```

### Telegram test
```text
NOI test. No broker order has been placed.
```

### Template exists but SKIPPED / unreachable live — Trade opportunity
```text
NOI | TRADE OPPORTUNITY
Signal ID: {id}
Action: {action}
Model probability: {p}
Expected gap: {gap}
Maximum entry premium: {premium|not supplied}
Generated at: {IST}
This is a manually executed trade recommendation.
No broker order has been placed.
```

### NOT CURRENTLY IMPLEMENTED as live scheduled alerts
- Signal strengthening
- Premarket confirmation (template only)
- Invalidation (template / library only)
- Daily intelligence report (template only; not scheduled)
- Weekly performance report (email prose invents metrics; not calculated/sent)

---

## 18. Database and Persistence

**DB:** PostgreSQL (via `psycopg`)

| Entity/Table | Purpose | Currently Used |
|---|---|---|
| instruments / market_observations | Bars | Yes |
| predictions / signals / opportunities / features | Decision snapshot | Yes (via save_decision) |
| notification_deliveries | Telegram dedupe | Yes |
| manual_trades | Reported entries/exits | Only if /entered used (no poller) |
| audit_logs | Ops events | check_database |
| option_snapshots, derivatives_positions, global_market_data, macro_events, market_regimes, prediction_outcomes, performance_metrics, option_evaluations | Vision schema | No writers in app/ |

**Lost on process restart (if not in DB):** in-memory paper/live_runner export_state, health, schedule position.

---

## 19. Outcome Tracking / Performance Analytics

`tracking/outcomes.py` can compute: direction_hit, magnitude error, trade PnL, scorecard (winners, avg win/loss, profit factor), drift_detected (≥15% hit-rate drop).

**Not wired into live runtime.** No automatic learning. No Brier/calibration loop in production. `alerts_approved` permanently False. Weekly email text claims metrics it does not calculate.

---

## 20. Testing and Verification

| Test Area | Tests Exist | Tests Run (this audit) | Notes |
|---|---|---|---|
| Unit (data, features, gaps, options, prediction, runtime, signals, telegram, upstox, packages A–F) | Yes (~100+) | NOT RUN | pytest not installed in audit env |
| Acceptance | Yes (~50) | NOT RUN | Requirement existence checks |
| Integration (Postgres) | Yes (4) | NOT RUN | Needs DB |
| End-to-end live market | No true E2E with live APIs | — | — |
| Backtests as runnable product | Helpers only | — | — |

**Named test functions counted:** ~139  
**This environment:** no `.env`, no Docker, no Postgres process, no NOI process.  
**RUNTIME STATUS COULD NOT BE VERIFIED** for a production deployment.  
Clock probe at audit time: activity `evening_forecast` (idle for entry script).

---

## 21. Product Vision Comparison (condensed)

| ID | Requirement | Current Behaviour | Status | Severity |
|---|---|---|---|---|
| V01 | Monitor Nifty/Bank Nifty | On-demand Upstox quotes | PARTIALLY MATCHES | HIGH |
| V02 | Gap-up/down opportunities | Base-rate frequencies; no detector | PARTIALLY MATCHES | HIGH |
| V03 | T+1/T+2/T+3 | T+1 live only | PARTIALLY MATCHES | HIGH |
| V04 | Early warnings | WATCH Telegram if flat wins | PARTIALLY MATCHES | MEDIUM |
| V05 | Global intelligence | Schedule label + empty table | NOT IMPLEMENTED | HIGH |
| V06 | Institutional positioning | Schema only | NOT IMPLEMENTED | HIGH |
| V07 | Market breadth | Helper unused | NOT IMPLEMENTED | HIGH |
| V08 | Technical structure | EMA stored; others dead | PARTIALLY MATCHES | MEDIUM |
| V09 | Derivatives data | No collector | NOT IMPLEMENTED | CRITICAL |
| V10 | India VIX analysis | Fetched for freshness only | PARTIALLY MATCHES | MEDIUM |
| V11 | Macro / events | Schema + unused helper | NOT IMPLEMENTED | HIGH |
| V12 | Market regimes | Unwired classifier | NOT IMPLEMENTED | HIGH |
| V13 | Evidence-based predictions | Unconditional base-rate | PARTIALLY MATCHES | CRITICAL |
| V14 | Gap direction probabilities | Historical frequencies | PARTIALLY MATCHES | HIGH |
| V15 | Expected movement/ranges | Mean + order stats | PARTIALLY MATCHES | MEDIUM |
| V16 | Confidence | Absent | NOT IMPLEMENTED | HIGH |
| V17 | Option profitability | Unreachable live | DOES NOT MATCH | CRITICAL |
| V18 | IV/Greeks/liquidity/costs | BS unused; no IV | DOES NOT MATCH | CRITICAL |
| V19 | Reject bad options | Filters exist; no quotes | PARTIALLY MATCHES | CRITICAL |
| V20 | Risk evaluation | Hardcoded; capital unused | PARTIALLY MATCHES | HIGH |
| V21 | WATCH alerts | Yes via Telegram | MATCH | LOW |
| V22 | Trade recommendations | Gated off / unreachable | DOES NOT MATCH | CRITICAL |
| V23 | NO TRADE decisions | Yes | MATCH | LOW |
| V24 | Update signals | No | NOT IMPLEMENTED | HIGH |
| V25 | Invalidate signals | Library only | NOT IMPLEMENTED | HIGH |
| V26 | Telegram | Outbound yes | PARTIALLY MATCHES | MEDIUM |
| V27 | WhatsApp | Stub | NOT IMPLEMENTED | MEDIUM |
| V28 | Email | Format only | NOT IMPLEMENTED | MEDIUM |
| V29 | Market-aware schedule | Labels; no daemon | PARTIALLY MATCHES | HIGH |
| V30 | Track outcomes | Library unwired | NOT IMPLEMENTED | HIGH |
| V31 | Prediction performance | Helpers; not live | NOT IMPLEMENTED | HIGH |
| V32 | Paper trading | paper.py unused | NOT IMPLEMENTED | HIGH |
| V33 | Failure analysis | Absent | NOT IMPLEMENTED | MEDIUM |
| V34 | Research support | Gaps/walk-forward helpers | PARTIALLY MATCHES | MEDIUM |
| V35 | Never auto-place orders | Confirmed nowhere | MATCH | — |

---

## 22. Critical Issues (P0)

1. **No continuous runtime / no in-repo scheduler** — “platform” is manual/cron CLI  
2. **Live BUY path unreachable** — no option quotes; capital=None; buys skipped; `alerts_approved and False`  
3. **Probabilities are unconditional historical frequencies** — unsafe to treat as trade odds  
4. **Quote OHLC synthesized from LTP** — not true session bars for gap research quality  
5. **Empty holiday calendar** — session logic treats holidays as trading days  

---

## 23. What Is Actually Working Today?

### A. Verified Working (in code)
- Upstox index quote fetch  
- OHLC quarantine + 20m stale gate on ingest  
- Postgres observation + decision + delivery persistence  
- IST activity clock labels  
- T+1 gap base-rate probabilities from stored bars  
- Telegram outbound with dedupe + 1 retry  
- Explicit “no broker order” on trade-shaped paths  
- NO_TRADE and WATCH Telegram on entry ticks (when env/DB/cron present)

### B. Implemented but Unverified / Unwired
- Regime classifier  
- Black–Scholes Greeks  
- Research gate / walk-forward / Brier helpers  
- Signal FSM transitions  
- Exit/position book logic  
- Outcome scorecard  
- `live_runner.run_clock` / paper helpers  

### C. Partially Working
- Scheduled check (idle outside windows; buy skipped)  
- Settings (many risk fields ignored by decision_loop)  
- Calendar (weekends only)  
- Feature EMA (stored, not causal)

### D. Simulated / Placeholder
- Logistic / RandomForest / GradientBoost “models”  
- WhatsApp / Email send  
- Schedule labels without jobs  
- `alerts_approved ... and False`  
- Orchestrator 9-line gate  

### E. Missing
- Daemon/API  
- Official daily OHLCV pipeline  
- Option chain ingest + IV  
- FII/DII, global, macro, breadth in decisions  
- T+2/T+3 live forecasts  
- Confidence  
- Signal update/invalidation jobs  
- Outcome learning loop  
- Paper trading period as an operated mode  

---

## 24. Scorecard (0–10)

| Area | Score | Justification |
|---|---:|---|
| Architecture | 5 | Clean modular layout; no daemon/API; many libraries unwired |
| Data Infrastructure | 4 | Only Upstox quotes live; rich schema mostly empty |
| Data Quality | 5 | OHLC + 20m stale gate; holidays empty; OHLC invented from LTP |
| Market Intelligence | 2 | No FII/DII, global, breadth, derivatives OI in path |
| Feature Engineering | 3 | EMA5 stored; RSI/ADX/BB/breadth exist unused |
| Regime Detection | 2 | Rule function exists; never called; never persisted |
| Opportunity Detection | 3 | Gap labeling real; no separate opportunity detector |
| Prediction Methodology | 3 | T+1 historical base-rate only; ML names are stubs |
| Statistical Validation | 3 | Walk-forward + Brier helpers exist; alerts hard-off |
| Options Evaluation | 2 | BS library real; live path has no option quote → NO_TRADE |
| Risk Management | 4 | Eligibility filters real; Settings risk ignored; no prob floor |
| Signal Management | 2 | FSM library real; runtime collapses statuses; no updates |
| Notifications | 4 | Telegram outbound real; WA/email stubs; buy alerts skipped |
| Outcome Tracking | 2 | Scorecard library; PredictionOutcome unwired |
| Testing | 7 | 139 named tests; pytest missing in this audit env |
| Reliability | 3 | No continuous process; external cron assumed; empty holidays |
| Product Completeness | 2 | Decision-support vision largely unimplemented |

---

## 25. Remediation Roadmap

**Retain:** modular layout, Upstox client, validation/quarantine, Postgres PIT store, IST clock labels, BaseRateModel as explicit benchmark, eligibility skeleton, TelegramGateway outbound+dedupe, disclaimer strings, test structure. Do **not** rewrite from scratch.

| Task ID | Priority | Component | Task | Acceptance Criteria |
|---|---|---|---|---|
| A1 | P0 | Runtime | Real process or documented cron + health | Daemon or ops runbook with heartbeats |
| A2 | P0 | Calendar | Load NSE holiday list | Known holidays → market_holiday |
| A3 | P0 | Data | True daily OHLCV (not LTP-invented) | Gaps use prior official close |
| A4 | P0 | Prediction | Never present base-rate as calibrated odds | Alerts label benchmark |
| B1 | P1 | Data | Option chain + VIX into features | Stored snapshots used in decide |
| B2 | P1 | Features | Wire regime + selected technicals | Regime persisted and gates risk |
| B3 | P1 | Data | Global/GIFT + event calendar | Premarket job writes rows |
| C1 | P1 | Prediction | Conditional model + walk-forward gate | alerts_approved can become True |
| C2 | P1 | Validation | Calibration + OOS vs base-rate | Beat Brier before live BUY |
| D1 | P1 | Options | Strike/expiry selection + IV + costs | EV uses real scenario math |
| D2 | P1 | Risk | Honor Settings capital/risk; prob floor | Config drives decide() |
| E1 | P1 | Signals | Drive FSM; update/invalidate/expire | DB status transitions |
| F1 | P2 | Notify | Wire rich templates; WA/email later | BUY uses buy_call template |
| F2 | P2 | Telegram | Inbound poller or webhook | /entered updates lifecycle |
| G1 | P1 | Tracking | Record actual gaps vs forecasts | Scorecard from live data |
| H1 | P1 | Paper | Paper mode for 2–3 months | Gate before real alerts |

**Suggested next slice:** (1) NSE holidays + official daily bars, (2) wire research_gate so promotion is evidence-based, (3) option snapshot ingest + eligibility with real capital, (4) signal status updates + invalidation, (5) paper Telegram path with outcome recording — still no broker orders.

---

## 26. Final Questions — Direct Answers

1. **What does the NOI bot actually do when started?**  
   Runs a one-shot script. Only in three IST windows does it fetch quotes, compute T+1 base-rates, and maybe Telegram NO_TRADE/WATCH. Otherwise idle print.

2. **What data does it currently collect?**  
   Upstox quotes for Nifty 50, Bank Nifty, India VIX — stored as market_observations.

3. **What data does it currently ignore?**  
   Option chains, FII/DII, global markets, macro events, breadth, true session OHLC, VIX as a model input (gate only).

4. **What is the actual opportunity detection methodology?**  
   No detector. Gap labels for research; live = argmax of historical gap-bucket frequencies → WATCH or eligibility.

5. **Is it using real prediction models or rule-based logic?**  
   Rule/statistical base-rate. Named ML classes are stubs. No trained artifacts.

6. **Are the probabilities mathematically meaningful?**  
   As historical frequencies yes; as calibrated P(tomorrow) no.

7. **How is confidence calculated?**  
   Not calculated. `data_sufficient` is a non-empty-history flag.

8. **Does it genuinely predict T+1, T+2 and T+3?**  
   T+1 only on live path. T+2/T+3 labeling helpers exist unused.

9. **Does it evaluate CALL/PUT profitability?**  
   No on live path. BS library unused; quote always None → NO_TRADE.

10. **Does it account for IV, theta, Greeks and liquidity?**  
    Greeks in unused BS; no IV solver; liquidity filters only if quote supplied.

11. **Can it correctly decide NO TRADE?**  
    Yes — default outcome on the live path.

12. **Can it generate early warning signals?**  
    Yes — WATCHLIST → early_warning Telegram when flat is the modal bucket.

13. **Can it update and invalidate signals?**  
    FSM library exists; production does not drive updates or invalidations.

14. **What notifications actually work?**  
    Telegram outbound (test + NO_TRADE/WATCH). WhatsApp/email do not send.

15. **Does it track its prediction accuracy?**  
    Helpers exist; not wired into the live loop or DB outcomes writers.

16. **Does it learn from past outcomes?**  
    No. `alerts_approved` permanently False; no model retraining loop.

17. **Is the current system reliable?**  
    Not as a decision-support product. Quote ingest + Telegram plumbing are solid libraries.

18. **What is the biggest weakness?**  
    Product vision implemented as unwired libraries; live “intelligence” is an unconditional base-rate with no options.

19. **What are the five most important missing features?**  
    (1) Daemon/schedule ops, (2) official bars + holidays, (3) conditional validated model, (4) option chain profitability, (5) signal lifecycle + outcomes.

20. **What should we implement next?**  
    Holidays + official daily data; research-gate promotion path; option snapshots into eligibility; paper outcomes.

21. **Is it ready for paper trading?**  
    No — paper.py unused; buy alerts off; no outcome loop.

22. **Is it ready for real-world decision support?**  
    No.

23. **What must be fixed before we trust its alerts?**  
    True data, holidays, validated model that beats base-rate, real option EV, wired lifecycle, paper period with tracked outcomes.

---

## 27. Evidence Ledger (highlights)

| ID | Finding | Evidence | Confidence |
|---|---|---|---|
| F01 | No continuous daemon | No APScheduler/FastAPI/`while True`; scripts exit after main | HIGH |
| F02 | Docker does not run the trading app | Dockerfile CMD=pytest; compose=Postgres only | HIGH |
| F05 | Script only acts in 3 entry windows | ENTRY_ACTIVITIES in live_runner.py; early return in run_scheduled_check.py | HIGH |
| F06 | Buy/sell alerts off on production path | scheduled_check.py continues past BUY_*; docstring | HIGH |
| F08 | No broker orders | Upstox GET quotes only; no place_order | HIGH |
| F09 | BUY unreachable without option quote | decide(..., quote=None) → eligibility NO_TRADE | HIGH |
| F13 | Holiday calendar empty by default | MarketCalendar holidays=frozenset() | HIGH |
| F14 | alerts_approved always False | prediction.py: `and False` | HIGH |
| F15 | run_clock / paper / orchestrator unused by scripts | Import graph | HIGH |

---

*End of forensic audit report.*
