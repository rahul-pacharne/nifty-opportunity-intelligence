# Operations

NOI does not place orders. A restart must reload configuration from the environment and continue from stored observations. It must not replay a notification that was already delivered.

When the database or scheduler is down, health is `down` and the orchestrator emits no recommendation. When a market-data provider is down, health is `degraded` and the orchestrator still emits no recommendation.

Database backups are a deployment responsibility. This repository ships the schema in `migrations/` and a Postgres service in `docker-compose.yml`. Do not commit `.env`.

Recovery check:

1. Start Postgres and apply `migrations/001_market_observations.sql` if the volume is new.
2. Run `python3 -m pytest`.
3. Confirm health is `degraded` or `down` until the required provider is connected.
4. Confirm a second delivery of the same signal id and category is suppressed.
