# NOI roadmap

Approved baseline: 23 November 2026. Captured 25 November 2026 IST.

NOI is a market-intelligence platform for Nifty 50 and Bank Nifty gap opportunities. It recommends manual CALL or PUT buys. It does not place broker orders and it does not change the intraday trading bot.

| Phase | Objective | Commit scope |
|---|---|---|
| 0 | Research foundation | Requirements, hypotheses, data audit, targets, backtest method, risk policy |
| 1 | Data foundation | Point-in-time observations, validation, calendar, repositories |
| 2 | Historical research engine | Gap labels, distributions, horizon snapshots, no look-ahead |
| 3 | Feature and regime engines | Causal indicators and regime labels that do not create trades |
| 4 | Prediction engine | Baseline and walk-forward forecasts per index and horizon |
| 5 | Options and risk | Contract selection, Greeks, scenario value, eligibility |
| 6 | Signals and notifications | Lifecycle, dedup, channel dispatcher, acknowledgement commands |
| 7 | Outcomes and paper tracking | Predicted vs actual gaps, hypothetical and reported trades |
| 8 | Runtime and deployment | Health, market-aware schedule, Docker, recovery rules |

Live provider credentials, a multi-year licensed history, and 2–3 months of paper observation are operational gates. They are not simulated in this repository.

Task IDs NOI-001 through NOI-084 in the master document map onto these phases:

- NOI-001–006 foundation: phases 0–1 and 8
- NOI-007–018 data: phase 1
- NOI-019–029 research: phase 2
- NOI-030–037 features: phase 3
- NOI-038–047 prediction: phase 4
- NOI-048–055 options and risk: phase 5
- NOI-056–069 signals and notifications: phase 6
- NOI-070–076 outcomes: phase 7
- NOI-077–084 runtime: phase 8
