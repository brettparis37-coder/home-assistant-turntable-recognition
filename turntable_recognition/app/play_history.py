"""Persist the current and two most recent distinct play events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from diagnostics import log_event


class PlayHistory:
    def __init__(self, path: str | Path = "/data/play_history.json") -> None:
        self.path = Path(path)
        self.entries = self._load()

    @staticmethod
    def _key(track: dict[str, Any]) -> tuple[str, str, str]:
        return tuple(" ".join(str(value or "").casefold().split()) for value in (
            track.get("artist"), track.get("title"),
            track.get("discogs_release_id") or track.get("album"),
        ))

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            entries = data.get("plays", []) if isinstance(data, dict) else []
            return [entry for entry in entries if isinstance(entry, dict)][:3]
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            log_event("play_history_load_failed", level="WARNING", path=str(self.path),
                      error_type=type(exc).__name__, error=str(exc))
            return []

    def record(self, track: dict[str, Any], session_id: str) -> list[dict[str, Any]]:
        if not track.get("artist") and not track.get("title"):
            return self.entries
        if self.entries:
            latest = self.entries[0]
            if (latest.get("play_session_id") == session_id
                    and self._key(latest) == self._key(track)):
                return self.entries
        entry = dict(track)
        entry["played_at"] = datetime.now(timezone.utc).isoformat()
        entry["play_session_id"] = session_id
        self.entries = [entry, *self.entries[:2]]
        self._persist()
        return self.entries

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps({"plays": self.entries}, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            temporary.replace(self.path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            log_event("play_history_persist_failed", level="ERROR", path=str(self.path),
                      error_type=type(exc).__name__, error=str(exc))


