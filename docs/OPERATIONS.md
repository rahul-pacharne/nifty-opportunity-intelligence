# Operations

NOI does not place orders. A restart must reload configuration from the environment and continue from stored observations. It must not replay a notification that was already delivered.

When the database or scheduler is down, health is `down` and the orchestrator emits no recommendation. When a market-data provider is down, health is `degraded` and the orchestrator still emits no recommendation.

Database backups are a deployment responsibility. This repository ships the schema in `migrations/` and a Postgres service in `docker-compose.yml`. Do not commit `.env`.

Recovery check:

1. Start Postgres and apply pending files in `migrations/` with `python3 scripts/check_database.py`. The script uses `NOI_DATABASE_URL` and writes one audit row.
2. Run `python3 -m pytest`.
3. Confirm health is `degraded` or `down` until the required provider is connected.
4. Confirm a second delivery of the same signal id and category is suppressed.

Quote check:

```bash
python3 scripts/fetch_quotes.py
```

The script stores Nifty, Bank Nifty, and India VIX. It does not send a message and does not place an order. A quote older than 20 minutes is stored as stale.

Clock check:

```bash
python3 scripts/run_scheduled_check.py
```

Outside an entry window the command prints the activity and `sent: none`. It does not fetch and it does not send Telegram. Buy and sell stay off.
