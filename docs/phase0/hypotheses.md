# Research hypotheses

Each hypothesis has a measurable definition. None of these statements is treated as a market fact.

Thresholds are experimental. Strong gap means an opening gap beyond 0.75 percent. Research also evaluates 0.50, 1.00, and 1.50 percent, plus an ATR-scaled threshold. Nifty and Bank Nifty are measured separately.

| ID | Hypothesis | Measurement | Fail condition |
|---|---|---|---|
| H1 | Consecutive global strength raises the next-session bullish strong-gap rate | P(gap > θ \| global return streak) minus the unconditional base rate, with a confidence interval | Interval includes zero after multiple-testing control |
| H2 | Global weakness raises the bearish strong-gap rate | Same contrast for gap < −θ | Interval includes zero |
| H3 | GIFT Nifty explains a material share of Nifty's next open | Incremental R² of the open gap after a price-only baseline | Incremental fit is indistinguishable from zero |
| H4 | Banking-sector divergence adds information for Bank Nifty | Incremental log-loss reduction versus the Nifty-only feature set | No reduction out of sample |
| H5 | Volatility compression precedes large absolute gaps | P(\|gap\| > θ \| ATR percentile below cutoff) versus base rate | No increase |
| H6 | Rapid VIX expansion marks larger overnight magnitude | Quantile error of magnitude forecasts with and without VIX change | No error reduction |
| H7 | VIX level does not by itself choose direction | Directional accuracy of a VIX-only model versus a coin-flip baseline | It beats the baseline enough to be used alone |
| H8 | Extreme FII shorts followed by a reduction precede bullish gaps | Conditional gap rate using only data published before the decision timestamp | Publication lag is ignored, or the interval includes zero |
| H9 | Rising shorts with falling futures precede bearish gaps | Same point-in-time test | Same |
| H10 | Downside skew rises before bearish gaps | Change in 25-delta skew versus subsequent gap sign | No relationship out of sample |
| H11 | Straddle repricing rises before large absolute gaps | ATM straddle change versus \|gap\| | No relationship |
| H12 | Low IV can make a correct direction profitable, and high IV can make it unprofitable | Net option expectancy split by IV percentile | Sign of expectancy does not flip as stated |
| H13 | Low ATR percentile precedes volatility expansion | Forward ATR versus trailing ATR percentile | No increase |
| H14 | Inside-bar compression precedes large gaps | Gap rate after N inside bars | No increase |
| H15 | Failed breakdowns precede bullish gaps more often than the base rate | Gap-up rate after a failed breakdown definition | Interval includes zero |
| H16 | Breadth improvement during a flat index precedes bullish gaps | Advance/decline or EMA-breadth change while \|index return\| is small | No increase |
| H17 | Breadth deterioration during a stable index precedes bearish gaps | Mirror of H16 | No increase |
| H18 | Banking breadth improves Bank Nifty forecasts | Incremental score versus index-only features | No improvement |
| H19 | A scheduled macro event raises absolute-gap probability but does not set direction | \|gap\| rate inside the event window versus outside; directional accuracy of an event-only flag | Directional accuracy beats the baseline |
| H20 | T+2 and T+3 forecasts are not interchangeable with T+1 | Separate Brier scores; a T+3 hit is not counted as a T+1 hit | Horizons are pooled into one label |

Point-in-time rule: a feature may enter a forecast for date T only when its publication timestamp is at or before the decision timestamp for that forecast.
