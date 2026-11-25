# Risk policy

Parameters are configuration. Nothing here is hardcoded into a signal as a permanent market rule.

Initial research limits:

- Maximum planned premium risk per trade: 1 percent of configured strategy capital.
- Maximum overnight recommendations in the MVP: 1.
- No averaging down.
- No automatic re-entry after a loss.
- No recommendation when the contract fails the liquidity check.
- No recommendation when expected net value is below the configured minimum. Negative expected value is always a no-trade.
- No recommendation when required data is missing, stale, or quarantined.
- Capital is configured per deployment. It is not stored in source.

Premium at risk and a stop-loss amount are different numbers. An overnight gap can pass through a stop. The notification must say so.

Recommendations are manual. Telegram commands record an acknowledgement or a reported fill. They do not send broker orders.

Hypothetical P&L on an ignored signal stays separate from P&L on a user-reported trade.
