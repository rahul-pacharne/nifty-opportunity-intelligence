"""Environment settings. Tokens are optional until a provider is connected."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from app.core.constants import (
    DEFAULT_MAX_OVERNIGHT_POSITIONS,
    DEFAULT_MAX_RISK_FRACTION,
    DEFAULT_STRONG_GAP_PERCENT,
)


def _decimal(name: str, default: Decimal) -> Decimal:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return Decimal(raw)


@dataclass(frozen=True)
class Settings:
    database_url: str
    log_level: str
    strong_gap_percent: Decimal
    max_overnight_positions: int
    max_risk_fraction: Decimal
    strategy_capital: Decimal | None
    telegram_allowed_user_ids: tuple[str, ...]
    upstox_access_token: str | None

    @classmethod
    def from_env(cls) -> Settings:
        capital_raw = os.environ.get("NOI_STRATEGY_CAPITAL", "").strip()
        allowed = tuple(
            part.strip()
            for part in os.environ.get("NOI_TELEGRAM_ALLOWED_USER_IDS", "").split(",")
            if part.strip()
        )
        token = os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip() or None
        return cls(
            database_url=os.environ.get(
                "NOI_DATABASE_URL",
                "postgresql://noi:noi@localhost:5432/noi",
            ),
            log_level=os.environ.get("NOI_LOG_LEVEL", "INFO"),
            strong_gap_percent=_decimal("NOI_STRONG_GAP_PERCENT", DEFAULT_STRONG_GAP_PERCENT),
            max_overnight_positions=int(
                os.environ.get("NOI_MAX_OVERNIGHT_POSITIONS", DEFAULT_MAX_OVERNIGHT_POSITIONS)
            ),
            max_risk_fraction=_decimal("NOI_MAX_RISK_FRACTION", DEFAULT_MAX_RISK_FRACTION),
            strategy_capital=Decimal(capital_raw) if capital_raw else None,
            telegram_allowed_user_ids=allowed,
            upstox_access_token=token,
        )
