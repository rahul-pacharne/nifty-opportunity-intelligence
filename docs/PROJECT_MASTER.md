# Nifty Opportunity Intelligence — master specification

**Version:** 1.0  
**Baseline date:** 23 November 2026  
**Status:** Approved project baseline  
**Product:** Market intelligence and manual-trading alerts  
**Markets:** Nifty 50 and Bank Nifty  
**Execution:** Human-approved. No broker orders.

## 1. Purpose

The intraday bot showed a different opportunity: significant opening gaps that sometimes develop one to three sessions earlier. NOI collects evidence, estimates gap direction and size at T+1, T+2, and T+3, checks whether a CALL or PUT is still attractive after repricing and costs, and notifies the owner. Prediction accuracy alone does not make a trade.

NOI will not place Upstox orders, manage positions, modify the intraday bot, alert from technicals alone, alert when expected option value fails the threshold, or promise that a gap will occur.

## 2. Scope

Nifty inputs include spot, futures, options, constituents, India VIX, GIFT Nifty, global indices and futures, and Bank Nifty as context. Bank Nifty inputs include its spot, futures, options, constituents, private versus public bank strength, and financial-sector news. Models and scorecards are separate. Data infrastructure may be shared.

Version 1 covers strong gap-up and gap-down detection, early bullish and bearish setups, and overnight long-option pre-positioning. Intraday breakouts, option selling, single stocks, crypto, and US execution are out of scope. Straddles are a research benchmark only.

| Horizon | Use |
|---|---|
| T+1 | Primary overnight decision |
| T+2 | Early positioning research |
| T+3 | Developing-opportunity research |

| Conclusion | Recommendation |
|---|---|
| Strong bullish gap probability | Consider buying a CALL |
| Strong bearish gap probability | Consider buying a PUT |
| Large move, unclear direction | Watchlist; straddle research only |
| Direction likely, options expensive | No trade |
| Insufficient evidence | No trade |
| Signal invalidated | Cancel and notify |
| Forecast realised | Record the outcome |

## 3. Goals and thresholds

Goals: early identification, direction, magnitude, option profitability, timely alerts, an explanation for every recommendation, and a permanent outcome record.

Default gap classes, in percent: strong up > +0.75, moderate up +0.30 to +0.75 including both endpoints, flat strictly between −0.30 and +0.30, moderate down −0.75 to −0.30 including both endpoints, strong down < −0.75. Also test 0.50, 1.00, 1.50, and a volatility-adjusted threshold. The two indices may differ.

Prediction scorecard: directional accuracy, strong-gap precision and recall, calibration, Brier score, magnitude error, false positives, by horizon and by regime.

Trading scorecard: actionable count, percent profitable, average net win and loss, profit factor, drawdown, payoff, return on premium, costs, by instrument and by selection method.

## 4. Research categories

1. Global markets: GIFT Nifty, S&P 500, Nasdaq, Dow, Nikkei, Hang Seng, global futures, US yields, USD/INR, Brent, gold. Bank Nifty also uses global and domestic banking conditions.
2. India VIX and realised volatility, including compression and expansion.
3. FII and participant derivatives, futures basis, and positioning percentiles. Use publication time. Do not treat aggregate open interest as directional exposure.
4. Options: ATM and wing IV, 25-delta skew, put-call OI and volume, ATM straddle, term structure, OI change, volume, spread, and Greeks.
5. Structure: EMA 5/20/50, SMA 20/50/200, ATR 5/14/20, Bollinger width, ADX, RSI, candle location, prior day and week highs and lows, inside bars, failed breakouts, range contraction.
6. Breadth: advance/decline, percent of constituents above 5/20/50 EMA, 20-day highs and lows, banking breadth, private versus public banks, constituent contribution.
7. Macro calendar: RBI, Fed, US CPI and payrolls, India CPI and GDP, Budget, elections, geopolitics, banking events. Proximity is a feature. The calendar does not assign a direction.
8. Index-specific feature groups stay separate from shared features.

Measurable versions of the hypotheses are in `docs/phase0/hypotheses.md`.

## 5. Data

Critical sources: NSE, Upstox, India VIX, GIFT Nifty. High: NSE Indices, global markets, macro calendars. Medium: SEBI research. Comply with licences. No undocumented scraping.

Every row stores observation time, publication time where the feed is delayed, market date, source, retrieval time, quality, and version. Training and live decisions may use only rows published at or before the decision time.

Quarantine missing prices, duplicates, bad identifiers, stale quotes, bad timestamps, bad strikes, inconsistent expiries, impossible OHLC, and unexplained discontinuities. Every prediction stores a data-quality status.

History targets and the current empty inventory are in `docs/phase0/dataset_inventory.md`.

## 6. Modules

Ingestion, normalisation, feature engine, regime engine, opportunity detector, prediction engine, options evaluator, risk validator, signal manager, notification dispatcher, outcome tracker.

Regimes: bullish, bearish, sideways, volatility compression, volatility expansion, high uncertainty, event-driven risk, data-insufficient. A regime is not a trade.

Signal statuses: DETECTED, WATCHLIST, CONFIRMED, TRADE_RECOMMENDED, NOTIFIED, MANUALLY_ACCEPTED, IGNORED, POSITION_REPORTED, INVALIDATED, EXPIRED, CLOSED, EVALUATED. A recommendation is not a position.

Notifications: Telegram, WhatsApp via an official business API, and email. Priorities, dedup, retry, delivery status, daily summary, invalidation, and outcome updates.

## 7. Models

Gap percent is `(next_open - prior_close) / prior_close * 100`.

Direction estimates the three probabilities around threshold θ. Magnitude returns expected gap, median, and a range.

Initial model set: historical base rate, logistic regression, random forest, gradient boosting, a regime model, and a volatility forecast. Neural nets wait until a simpler model shows value. Walk-forward rules are in `docs/phase0/backtesting_methodology.md`.

## 8. Options and risk

Bullish: ATM call, slightly ITM call, bull call debit spread as a benchmark. Bearish: the put equivalents. Research deltas: ATM about 0.45–0.55, ITM about 0.60–0.70. Selection uses the exchange instrument master.

Valuation includes underlying move, delta, gamma, theta, vega, IV, time, spread, liquidity, brokerage, exchange charges, taxes, and slippage. Historical tests prefer actual contract prices.

Expected value is win probability times average profit, minus loss probability times average loss, minus costs. Scenarios cover a strong favourable gap, a moderate gap, a flat open, an opposite gap, and a smaller-than-expected move. Trade only when net expected value clears the configured minimum and risk checks pass.

Risk policy: `docs/phase0/risk_policy.md`.

## 9. Notifications and commands

Telegram is primary. WhatsApp requires opt-in, templates, delivery status, and cost tracking. Email carries early warnings, recommendations, invalidations, and daily, weekly, and monthly reports.

Alert priorities: early warning medium, trade and entry high, invalidation critical, position and exit high, daily and weekly normal.

A live message is filled from model output. Example numbers in the specification are not recommendations. Each message states that no broker order was placed.

Commands `/start`, `/status`, `/today`, `/signals`, `/performance`, `/accept`, `/ignore`, `/entered`, `/exit` update records only.

Fictional formats for watch, prepare, buy call, buy put, no trade, strengthening, invalidation, premarket confirmation, missed entry, and the daily and weekly reports are in `docs/SAMPLE_ALERTS.md`. A buy alert includes the contract, a maximum entry premium, an illustrative current premium, and the entry conditions. A sell or cancel is an invalidation or a no-new-entry alert, not an automatic order.

## 10. Stack and layout

Python 3.10+, FastAPI when the API is served, PostgreSQL, pandas and NumPy when tabular research runs, custom or pandas-ta indicators, scikit-learn and gradient boosting when fitted models are trained, APScheduler, httpx, Docker on AWS, structured logs, pytest, GitHub Actions.

Modular monolith. Layout matches the approved tree under `app/`, `research/`, `tests/`, `migrations/`, and `docker/`.

## 11. Records

Tables: instruments, market_observations, option_snapshots, derivatives_positions, global_market_data, macro_events, features, market_regimes, model_versions, predictions, opportunities, option_evaluations, signals, notifications, notification_deliveries, manual_trades, prediction_outcomes, performance_metrics, audit_logs.

Predictions store index, horizon, timestamps, expected gap, direction, three probabilities, calibration metadata, feature snapshot, model version, quality, and the eventual outcome.

Signals store the prediction link, contract, premium, expected value range, net return, planned risk, invalidation, notification status, acknowledgement, and outcome. Historical decisions are not silently overwritten.

## 12. Non-functional rules

Restarts recover. Failed collection does not create a recommendation. Retries do not duplicate a signal. Jobs are idempotent. Holidays are explicit.

A validated opportunity is notified within 60 seconds of the decision event under normal conditions. Research jobs must not block live monitoring.

Secrets stay in the environment or a secret store. Telegram users are allow-listed. WhatsApp consent is recorded. External calls use TLS. Backups and audit logs are required.

Health covers the app, providers, sockets, scheduler, notifications, predictions, and the database. Degraded mode is visible when a critical provider is down. Monitoring-window target is 99.5 percent, excluding provider outages.

## 13. Releases and gates

0.1 data research, 0.2 prediction research, 0.3 options intelligence, 0.4 Telegram paper alerts, 0.5 multi-channel paper alerts, 1.0 live decision support. Nifty and Bank Nifty can ship separately.

Live alerts require clean data, documented experiments, out-of-sample improvement over the base rate, calibration, tested option economics, risk controls, tested channels, restart tests, 2–3 months of paper observation, and a full audit trail. There is no fixed win-rate that bypasses those gates.

## 14. Product rule

Alert only when early evidence beats the base rate, the expected gap is large enough, the option is not already fully priced, net expectancy is attractive, and the loss is acceptable. No-trade is a successful output.

Interesting market state is not a trading opportunity.
