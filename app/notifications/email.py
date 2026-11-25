"""Email reports. Weekly is one of the required cadences."""

from __future__ import annotations


def daily_report(lines: list[str]) -> str:
    return ("Daily NOI report\n" + "\n".join(lines)).rstrip()


def monthly_report(lines: list[str]) -> str:
    return ("Monthly NOI report\n" + "\n".join(lines)).rstrip()


def weekly_report(lines: list[str]) -> str:
    body = "\n".join(lines)
    return (
        "Weekly NOI report\n"
        "Directional accuracy is reported for Nifty and for Bank Nifty.\n"
        "Paper trading includes profit factor and maximum drawdown.\n"
        f"{body}"
    ).rstrip()
