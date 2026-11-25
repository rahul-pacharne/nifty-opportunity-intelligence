# Scope to make NOI live

**Status:** Packages A–F are implemented in code. The 2–3 month paper window and a real Telegram, WhatsApp, and email provider are still operations, not a fast test.  
**Goal of this scope:** The owner receives a message when to buy a Nifty or Bank Nifty call or put, and a later message when to sell that option. The owner places every order. NOI never sends an order to a broker.

Live here means release 1.0 in `docs/PROJECT_MASTER.md`: validated alerts on Telegram, with WhatsApp and email as the other channels. Paper alerts come first. A model that has not beaten the historical base rate must not send a buy or a sell.

## What already exists

These pieces are libraries and templates. They do not run on a clock and they do not deliver a message.

- Gap labels for T+1, T+2, and T+3, and the default gap classes.
- Causal indicators, including EMA, ATR, RSI, ADX, advance/decline, and event proximity.
- A regime label. A regime is not a buy or a sell.
- A base-rate forecast, plus research stubs for logistic, forest, boosting, and volatility. Alerts stay off.
- An option check: probability required, delta band, spread, premium times quantity, one open recommendation.
- Signal statuses from detected through evaluated. Invalidation cancels an entry. It does not say "sell".
- Alert text for watch, buy call, buy put, no trade, and cancellation.
- WhatsApp refuses a recipient who has not opted in. Email can render a weekly report. Neither sends.
- A Postgres schema, an in-memory store, health fields, and the IST schedule function.

## Out of scope

- Placing, modifying, or cancelling broker orders.
- Changing the intraday trading bot.
- Option selling, spreads as a live recommendation, single stocks, crypto, or US execution.
- Neural networks.
- A public user base. Recipients are the owner and people they explicitly opt in.

## Work packages

Build them in this order. Do not start a package until the previous package's exit check passes.

### Package A — One closed loop on saved data

**Build**

- Load a caller-supplied history of Nifty and Bank Nifty daily bars into the observation store.
- At a decision timestamp, use only rows available at that time.
- Compute features, a T+1 base-rate forecast, and an option decision.
- Persist the prediction, the option check, and the signal. Do not overwrite a past decision. Write a new version.
- Return one of: buy call, buy put, watch, no trade.

**Exit check**

- A decision at Monday's close cannot see Tuesday's open.
- Missing or quarantined data returns no trade.
- No probability returns no trade.
- Nifty and Bank Nifty each get their own forecast row.

### Package B — Sell recommendation

**Build**

- After the owner reports an entry with `/entered`, track that option as an open position.
- On each later check, decide sell or hold. Sell when any configured rule hits:
  - the invalidation condition on the original signal,
  - premium loss greater than the configured stop,
  - premium gain greater than the configured target,
  - time stop: the session named at entry has opened, or the configured holding time has elapsed.
- A sell message names the same signal id, the instrument, and the reason. It says no broker order was placed.
- `/exit` only records the price the owner already traded. It does not create the sell decision.

**Exit check**

- A position that is not reported never gets a sell alert.
- A buy alert and its sell alert share one signal id.
- Hold is silent unless the owner asks for status.
- A sell is not sent twice for the same position.

### Package C — Telegram delivery

**Build**

- Send the buy, sell, invalidation, and no-trade texts to the Telegram chats in `NOI_TELEGRAM_ALLOWED_USER_IDS`.
- Accept `/start`, `/status`, `/today`, `/signals`, `/performance`, `/accept`, `/ignore`, `/entered`, and `/exit` from those users only.
- Record each delivery attempt. Retry a temporary failure. Do not send a second copy of the same signal id and alert type after a success.
- A failed Telegram send does not create another signal.

**Exit check**

- An unknown user gets no data and cannot change a signal.
- Two calls to send the same buy produce one Telegram message.
- `/entered` stores the premium and arms the sell rules in Package B.

### Package D — Live data and the clock

**Build**

- Connect Upstox for the instrument master and quotes. Use the token only from the environment.
- Ingest Nifty spot, Bank Nifty spot, the option chain, and India VIX. Store publication time when the feed is delayed.
- Run the Package A and B loop on the IST schedule: pre-market, 14:30 refresh, 15:00–15:20 final entry check, and the post-open check that can emit a sell.
- If Upstox or a required series is down, mark health degraded and send no buy and no sell.
- A holiday produces no entry check and no "market is open" sell check.

**Exit check**

- A stale quote is quarantined and cannot create a buy.
- Restarting the process does not resend a delivered alert and does not forget an open position.
- From a finished decision to a successful Telegram send is under 60 seconds when Telegram is up.

### Package E — Research gate before live buys

**Build**

- Walk-forward the T+1 model for Nifty and, separately, for Bank Nifty.
- Compare it with the base rate on the same folds. Record Brier score, strong-gap precision and recall, and magnitude error.
- Turn `alerts_approved` on for one index only when that index beats the base rate on the untouched final block and the option backtest is not negative after costs.
- Until that flag is on, the live loop may send watch and no-trade. It must not send buy or sell.

**Exit check**

- A failing index stays silent on buy and sell while the other index can proceed.
- The report states the sample size and the comparison. It does not hide a loss.

### Package F — Paper, then the other channels

**Build**

- Run Package D in paper mode for 2–3 months. Every buy and sell is still delivered, and every ignored alert is scored.
- Add email for the daily, weekly, and monthly reports, plus a copy of buy, sell, and invalidation.
- Add WhatsApp only for recipients who have opted in. Record delivery and template cost.
- Back up Postgres. Restore once and confirm open positions and sent-message ids survive.

**Exit check**

- Hypothetical P&L and the owner's reported fills are separate, per index.
- A WhatsApp recipient who has not opted in receives nothing.
- After a restore, a delivered buy is not sent again.

## Done when

The owner can receive, on Telegram:

1. A buy-call or buy-put message with signal id, probability, expected gap, contract, and maximum premium.
2. A later sell message for that same signal id, with the reason.
3. A no-trade or cancellation when the data or the model does not justify an entry.

And the research gate for that index is on, paper observation has been recorded, and a restart does not duplicate or drop those alerts.
