# Backtesting methodology

1. Split only in time. Training rows end before test rows start.
2. Walk forward: fit on a trailing window, predict the next block, then roll forward.
3. When horizons overlap, purge training rows whose label window intersects the test decision times.
4. Keep an untouched final out-of-sample block.
5. Compare every model with the historical base-rate model on the same folds.
6. Report Brier score, precision and recall for strong gaps, magnitude error, and false-positive rate.
7. Report the same metrics inside bull, bear, sideways, high-VIX, and low-VIX slices when the slice has enough rows.
8. Report expiry sessions separately from other sessions.
9. Apply a multiple-testing control before calling a feature "meaningful".
10. Option backtests use historical contract prices when those rows exist. Otherwise the run is marked research-incomplete.
11. Costs include spread, brokerage, exchange charges, taxes, and slippage. A positive gross move is not a passing trade.
12. If no model beats the base rate with a stable out-of-sample expectancy, the phase ends in a research report. No model is forced into alerts.

Look-ahead is a test failure: a feature timestamp after the decision timestamp cannot enter that row.
