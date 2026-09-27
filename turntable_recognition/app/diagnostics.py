"""Timestamped, credential-safe diagnostics for the recognition app."""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


def exception_details(error: BaseException, *, secret: str = "") -> dict[str, Any]:
    """Return useful HTTP/process error context without logging request bodies."""
    details: dict[str, Any] = {
        "error_type": type(error).__name__,
        "error": str(error),
        "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__))[-4000:],
    }
    response = getattr(error, "response", None)
    request = getattr(error, "request", None)
    if response is not None:
        details["http_status"] = getattr(response, "status_code", None)
        details["url"] = getattr(response, "url", None) or getattr(request, "url", None)
        body = str(getattr(response, "text", "") or "").strip()
        if body:
            details["response_excerpt"] = body[:500]
    if secret:
        for key, value in tuple(details.items()):
            if isinstance(value, str):
                details[key] = value.replace(secret, "[redacted]")
    return details


def log_event(event: str, *, level: str = "INFO", **fields: Any) -> None:
    """Emit one UTC timestamped JSON log line; never pass audio or credentials."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    payload = json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)
    stream = sys.stderr if level.upper() in {"ERROR", "WARNING"} else sys.stdout
    print(f"{timestamp} {level.upper()} turntable_recognition event={event} {payload}", file=stream, flush=True)

