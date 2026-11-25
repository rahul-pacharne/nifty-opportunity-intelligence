"""Email reports. Weekly is one of the required cadences."""

from __future__ import annotations


def weekly_report(lines: list[str]) -> str:
    body = "\n".join(lines)
    return f"Weekly NOI report\n{body}".rstrip()
