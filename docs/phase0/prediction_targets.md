# Prediction targets

Primary target for index i on the next session:

```text
gap = (open[t+1] - close[t]) / close[t] * 100
```

Nifty and Bank Nifty are separate targets. Horizons are separate targets.

| Horizon | Label uses | A forecast may see |
|---|---|---|
| T+1 | Next session open versus the latest completed close | Data published at or before the decision time |
| T+2 | Open two sessions ahead versus the decision-session close | Same. It must not use the T+1 open |
| T+3 | Open three sessions ahead versus the decision-session close | Same. It must not use T+1 or T+2 opens |

Default classification, in percent:

| Class | Gap |
|---|---|
| Strong gap-up | > +0.75 |
| Moderate gap-up | +0.30 to +0.75, including both endpoints |
| Flat | strictly between −0.30 and +0.30 |
| Moderate gap-down | −0.75 to −0.30, including both endpoints |
| Strong gap-down | < −0.75 |

The moderate class owns the shared endpoints. A gap of exactly ±0.30 or exactly ±0.75 is moderate, not flat and not strong.

Direction models estimate P(gap > θ), P(gap < −θ), and P(|gap| ≤ θ). Magnitude models estimate the expected gap, the median, and a lower and upper range.

A T+3 forecast is never counted as a T+1 trade.
