# Data-source audit

Official or licensed sources are required. Undocumented APIs and uncontrolled page scraping are out of scope.

| Source | Data | Priority | Access status in this repository | Limitation |
|---|---|---|---|---|
| NSE India | Index history, F&O, participant data, option reports | Critical | Not connected. No credentials or licensed dump are in git | Publication time must be stored. Aggregate OI is not directional exposure |
| Upstox | Live quotes, instrument master, futures and options | Critical | Interface only. Tokens stay in the environment | Market-data access only. No order placement |
| NSE Indices | Constituents and index history | High | Not connected | Constituent changes must be point-in-time |
| India VIX / NSE | Volatility history | Critical | Not connected | Needed for both indices as a shared feature |
| GIFT Nifty provider | Overnight futures | Critical | Provider not selected | Longest reliable history must be audited before a model depends on it |
| Global market provider | Indices, futures, yields, USD/INR, crude, gold | High | Provider not selected | Licensing must allow storage for research |
| Macro calendar | RBI, Fed, CPI, GDP, Budget, elections | High | Static injectable calendar in code | A scheduled event does not create a direction |
| SEBI | Research and market studies | Medium | Manual reading only | Not an automated feed |

Preferred history, to be audited when a source is connected:

| Dataset | Target |
|---|---|
| Nifty and Bank Nifty OHLC | 10–15 years |
| India VIX | 10–15 years |
| Index futures and OI | 8–10 years |
| FII derivatives positioning | 8–10 years |
| Options prices and IV | 5–8 years |
| Global indices | 8–10 years |
| GIFT Nifty | Longest reliable history |
| Breadth | Longest reconstructable history |
| Economic calendar | 8–10 years |

Until that audit exists, research code runs on caller-supplied observations and reports coverage instead of inventing history.
