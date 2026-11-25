"""Service health. A dead database is down. A dead provider is degraded, not a trade."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthReport:
    status: str
    database: str
    scheduler: str
    provider: str
    notifications: str
    predictions: str
    socket: str


def health(
    *,
    database_ok: bool,
    scheduler_ok: bool,
    provider_ok: bool,
    notifications_ok: bool = True,
    predictions_ok: bool = True,
    socket_ok: bool = True,
) -> HealthReport:
    database = "ok" if database_ok else "down"
    scheduler = "ok" if scheduler_ok else "down"
    provider = "ok" if provider_ok else "unavailable"
    notifications = "ok" if notifications_ok else "unavailable"
    predictions = "ok" if predictions_ok else "unavailable"
    socket = "ok" if socket_ok else "unavailable"
    if not database_ok or not scheduler_ok:
        status = "down"
    elif not all((provider_ok, notifications_ok, predictions_ok, socket_ok)):
        status = "degraded"
    else:
        status = "ok"
    return HealthReport(status, database, scheduler, provider, notifications, predictions, socket)
