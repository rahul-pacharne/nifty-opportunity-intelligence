"""Breadth features. A ratio is not a trade direction."""

from __future__ import annotations

from decimal import Decimal


def advance_decline_ratio(advances: int, declines: int) -> Decimal | None:
    if declines < 0 or advances < 0:
        raise ValueError("counts cannot be negative")
    if declines == 0:
        return None
    return (Decimal(advances) / Decimal(declines)).quantize(Decimal("0.0001"))
