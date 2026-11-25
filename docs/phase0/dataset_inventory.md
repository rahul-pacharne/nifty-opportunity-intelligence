# Historical dataset inventory

No market history is stored in this repository. The inventory is the schema the collectors must fill.

| Dataset | Index scope | Required fields | Point-in-time fields |
|---|---|---|---|
| Spot OHLC | Nifty, Bank Nifty | open, high, low, close, volume if published | market date, observation time, source, retrieved time, quality, version |
| Futures | Both | price, open interest, basis | publication time when the file is delayed |
| Option chain | Both | strike, expiry, type, bid, ask, IV, OI, volume, Greeks when computed here | quote time, expiry from the instrument master |
| India VIX | Shared | level and computed changes | session date, source |
| FII / participant derivatives | Shared, applied per model | long, short, net, change | publication timestamp. Unavailable until published |
| Global markets | Shared features | close or last, return | observation time in the source timezone, converted and stored in UTC |
| GIFT Nifty | Nifty feature | last and return | same |
| Breadth | Per index | advance/decline, percent above EMAs, new highs and lows | constituent set as of that date |
| Macro events | Shared | name, category, window | scheduled time. No direction flag |

Coverage report fields, produced by the data audit once a store is loaded:

- first and last market date
- missing sessions inside the calendar
- duplicate keys
- quarantined rows and the reason
- fraction of rows with a publication timestamp

Current coverage: empty. That limitation is explicit.
