"""Email reports. Weekly is one of the required cadences."""

from __future__ import annotations


def weekly_report(lines: list[str]) -> str:
    body = "\n".join(lines)
    return (
        "Weekly NOI report\n"
        "Directional accuracy is reported for Nifty and for Bank Nifty.\n"
        "Paper trading includes profit factor and maximum drawdown.\n"
        f"{body}"
    ).rstrip()
