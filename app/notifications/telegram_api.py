"""Send one Telegram message with the bot token from the environment."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def load_env_file(path: Path) -> None:
    """Fill empty environment keys from a local .env file. Never prints values."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def send_message(token: str, chat_id: str, text: str, opener=urlopen) -> dict:
    if not token or not chat_id:
        raise ValueError("telegram token and chat id are required")
    payload = urlencode({"chat_id": chat_id, "text": text}).encode()
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        method="POST",
    )
    try:
        with opener(request, timeout=20) as response:
            body = response.read().decode()
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(_safe_error(detail)) from None
    except URLError as exc:
        raise RuntimeError("telegram network error") from exc
    parsed = json.loads(body)
    if not parsed.get("ok"):
        raise RuntimeError(_safe_error(body))
    return parsed


def _safe_error(body: str) -> str:
    try:
        description = json.loads(body).get("description", "telegram rejected the message")
    except json.JSONDecodeError:
        description = "telegram rejected the message"
    return str(description)
