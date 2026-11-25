"""One JSON object per log line, with a correlation id when the caller has one."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, default=str, sort_keys=True))
