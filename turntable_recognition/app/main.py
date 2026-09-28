#!/usr/bin/env python3
"""Turntable recognition Home Assistant app."""

from __future__ import annotations

import json
import calendar
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from audio_meter import run_meter
from manual_recognition import ManualRecognition
from auto_recognition import AutomaticRecognition, timing
from album_resolver import resolve_audd_payload
from discogs_matcher import DiscogsMatcher, apply_match
from diagnostics import exception_details, log_event
from play_history import PlayHistory


OPTIONS_PATH = Path("/data/options.json")
USAGE_PATH = Path("/data/usage.json")
ALBUM_CACHE_PATH = Path("/data/album_cache.json")
HA_API = "http://supervisor/core/api"


@dataclass
class Track:
    artist: str = ""
    title: str = ""
    album: str = ""
    release_date: str = ""
    year: str = ""
    label: str = ""
    timecode: str = ""
    song_link: str = ""
    artwork_url: str = ""
    release_artwork_url: str = ""
    master_artwork_url: str = ""
    release_year: str = ""
    master_year: str = ""
    discogs_release_id: str = ""
    discogs_master_id: str = ""
    spotify_url: str = ""
    apple_music_url: str = ""
    provider: str = ""
    duration_seconds: float | None = None
    position_seconds: float | None = None
    recognized_version: str = ""
    album_type: str = ""
    album_release_group_id: str = ""
    album_release_id: str = ""
    artwork_source: str = ""
    timing_source: str = ""
    isrc: str = ""
    musicbrainz_recording_id: str = ""
    selection_reason: str = ""


class RecognitionError(RuntimeError):
    pass


class Provider:
    name = "base"

    def recognize(self, source: str, source_is_url: bool) -> Track:
        raise NotImplementedError


class AudDProvider(Provider):
    name = "audd"

    def __init__(self, token: str, options: dict[str, Any] | None = None) -> None:
        if not token:
            raise RecognitionError("An AudD API token is required for this input mode")
        self.token = token
        self.options = options or {}

    def recognize(self, source: str, source_is_url: bool) -> Track:
        request_started = time.monotonic()
        data = {
            "api_token": self.token,
            "return": "spotify,apple_music,musicbrainz",
        }
        if source_is_url:
            data["url"] = source
            response = requests.post("https://api.audd.io/", data=data, timeout=45)
        else:
            source_path = Path(source)
            if not source_path.is_file():
                raise RecognitionError(f"Audio file does not exist: {source_path}")
            with source_path.open("rb") as audio_file:
                response = requests.post(
                    "https://api.audd.io/",
                    data=data,
                    files={"file": (source_path.name, audio_file)},
                    timeout=45,
                )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") or {}
        log_event("audd_response_received", status=payload.get("status"),
                  latency_seconds=round(time.monotonic() - request_started, 3),
                  has_match=bool(result), request_kind="url" if source_is_url else "audio_upload",
                  recognized_artist=result.get("artist"), recognized_title=result.get("title"),
                  timecode=result.get("timecode"),
                  response_fields=sorted(payload.keys()))
        if payload.get("status") != "success":
            error = payload.get("error") or {}
            error_message = str(error.get("error_message") or "no message")
            if self.token:
                error_message = error_message.replace(self.token, "[redacted]")
            log_event("audd_api_rejected_request", level="ERROR",
                      status=payload.get("status"), error_code=error.get("error_code"),
                      error_message=error_message,
                      note="API token and audio payload are intentionally omitted")
            raise RecognitionError(
                f"AudD API status={payload.get('status')!r}; "
                f"code={error.get('error_code')!r}; message={error_message}"
            )
        if not result:
            log_event("audd_no_match", level="WARNING", result="null",
                      explanation="AudD returned no track match and does not return alternate candidate matches")
            raise RecognitionError("No song was recognized (AudD returned result=null; no alternatives were provided)")

        release_date = str(result.get("release_date") or "")
        spotify = result.get("spotify") or {}
        apple_music = result.get("apple_music") or {}
        spotify_album = spotify.get("album") or {}
        spotify_images = spotify_album.get("images") or []
        apple_artwork = (apple_music.get("artwork") or {}).get("url") or ""
        artwork_url = ""
        if spotify_images:
            artwork_url = spotify_images[0].get("url") or ""
        elif apple_artwork:
            artwork_url = apple_artwork.replace("{w}", "600").replace("{h}", "600")

        year_match = re.match(r"^(\d{4})", release_date)
        duration, position = timing(spotify.get("duration_ms") or apple_music.get("durationInMillis"), result.get("timecode"))
        base = Track(
            artist=str(result.get("artist") or ""),
            title=str(result.get("title") or ""),
            album=str(result.get("album") or spotify_album.get("name") or ""),
            release_date=release_date,
            year=year_match.group(1) if year_match else "",
            label=str(result.get("label") or ""),
            timecode=str(result.get("timecode") or ""),
            song_link=str(result.get("song_link") or ""),
            artwork_url=artwork_url,
            spotify_url=str((spotify.get("external_urls") or {}).get("spotify") or ""),
            apple_music_url=str(apple_music.get("url") or ""),
            provider=self.name,
            duration_seconds=duration,
            position_seconds=position,
        )
        discogs_match = None
        if self.options.get("discogs_enabled", False):
            matcher = DiscogsMatcher(str(self.options.get("discogs_database_path") or "/share/home_apps.sqlite3"))
            try:
                discogs_match = matcher.match(base.artist, base.title)
            except Exception as exc:
                log_event("discogs_match_failed", level="ERROR", artist=base.artist, title=base.title,
                          **exception_details(exc))
            if not discogs_match:
                log_event("discogs_match_not_found", level="WARNING", artist=base.artist, title=base.title,
                          diagnostics=matcher.last_diagnostics,
                          fallback="continue with AudD and catalog metadata")
        if discogs_match:
            apply_match(base, discogs_match, self.options)
            base.release_date = base.release_year or base.release_date
            base.recognized_version = base.title
            base.album_type = "Album"
            base.isrc = str(((spotify.get("external_ids") or {}).get("isrc")) or apple_music.get("isrc") or "")
            base.timing_source = "spotify" if spotify.get("duration_ms") else "apple_music" if apple_music.get("durationInMillis") else ""
            log_event("discogs_match_selected", artist=base.artist, title=base.title,
                      album=base.album, release_year=base.release_year, master_year=base.master_year,
                      release_id=base.discogs_release_id, master_id=base.discogs_master_id,
                      artwork_source=base.artwork_source,
                      selection_reason=base.selection_reason,
                      match_diagnostics=matcher.last_diagnostics)
        else:
            try:
                resolved = resolve_audd_payload(payload, cache_path=ALBUM_CACHE_PATH)
                base.album = resolved.album or base.album
                base.release_date = resolved.album_release_date or base.release_date
                base.year = resolved.album_year or base.year
                base.artwork_url = resolved.artwork_url or base.artwork_url
                for field in ("recognized_version", "album_type", "album_release_group_id",
                              "album_release_id", "artwork_source", "timing_source", "isrc",
                              "musicbrainz_recording_id", "selection_reason", "duration_seconds",
                              "position_seconds"):
                    value = getattr(resolved, field)
                    if value not in (None, ""):
                        setattr(base, field, value)
                log_event("album_metadata_resolved", album=base.album, year=base.year,
                          artwork_source=base.artwork_source, timing_source=base.timing_source,
                          duration_seconds=base.duration_seconds, selection_reason=base.selection_reason)
            except Exception as exc:
                log_event("album_metadata_enrichment_failed", level="WARNING",
                          fallback="use AudD provider metadata",
                          **exception_details(exc))
            base.release_year = base.year
            base.release_artwork_url = base.artwork_url
        return base


class UsageLimiter:
    def __init__(self, daily_limit: int, monthly_limit: int, billing_cycle_day: int = 1) -> None:
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit
        self.billing_cycle_day = max(1, min(28, billing_cycle_day))

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(USAGE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def cycle(self, now: datetime | None = None) -> tuple[str, datetime, datetime]:
        now = now or datetime.now(timezone.utc)
        if now.day >= self.billing_cycle_day:
            start = now.replace(day=self.billing_cycle_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            year, month = now.year, now.month - 1
            if month == 0:
                year, month = year - 1, 12
            start = now.replace(year=year, month=month, day=self.billing_cycle_day,
                                hour=0, minute=0, second=0, microsecond=0)
        year, month = start.year, start.month + 1
        if month == 13:
            year, month = year + 1, 1
        end_day = min(self.billing_cycle_day, calendar.monthrange(year, month)[1])
        end = start.replace(year=year, month=month, day=end_day)
        return start.date().isoformat(), start, end

    def counts(self) -> tuple[int, int]:
        usage = self._read()
        now = datetime.now(timezone.utc)
        cycle_key, _, _ = self.cycle(now)
        cycles = usage.get("cycles") or {}
        cycle_count = cycles.get(cycle_key)
        if cycle_count is None:
            cycle_count = usage.get(now.strftime("%Y-%m"), 0)
        return int(usage.get(now.date().isoformat(), 0)), int(cycle_count)

    def details(self) -> dict[str, Any]:
        day_count, cycle_count = self.counts()
        _, cycle_start, cycle_end = self.cycle()
        remaining = max(0, self.monthly_limit - cycle_count)
        return {
            "requests_today": day_count,
            "requests_this_cycle": cycle_count,
            "allowance": self.monthly_limit,
            "remaining": remaining,
            "usage_percent": round(cycle_count * 100 / self.monthly_limit, 1),
            "cycle_start": cycle_start.date().isoformat(),
            "cycle_end": cycle_end.date().isoformat(),
            "limit_reached": cycle_count >= self.monthly_limit,
            "source": "local_request_guard",
        }

    def consume(self) -> tuple[int, int]:
        usage = self._read()
        now = datetime.now(timezone.utc)
        day_key = now.date().isoformat()
        cycle_key, _, cycle_end = self.cycle(now)
        day_count = int(usage.get(day_key, 0))
        cycles = usage.get("cycles") or {}
        cycle_count = cycles.get(cycle_key)
        if cycle_count is None:
            cycle_count = int(usage.get(now.strftime("%Y-%m"), 0))
        cycle_count = int(cycle_count)
        if day_count >= self.daily_limit:
            raise RecognitionError(f"Daily request limit reached ({self.daily_limit})")
        if cycle_count >= self.monthly_limit:
            raise RecognitionError(
                f"AudD API limit reached ({self.monthly_limit}); refreshes {cycle_end.date().isoformat()}"
            )
        day_count += 1
        cycle_count += 1
        usage = {key: value for key, value in usage.items() if key == day_key}
        usage[day_key] = day_count
        usage["cycles"] = {cycle_key: cycle_count}
        USAGE_PATH.write_text(json.dumps(usage, indent=2), encoding="utf-8")
        return day_count, cycle_count


class HomeAssistantPublisher:
    def __init__(self, prefix: str, limiter: UsageLimiter | None = None) -> None:
        self.prefix = prefix
        self.limiter = limiter
        self.play_history = PlayHistory()
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def set_state(self, suffix: str, state: str, attributes: dict[str, Any]) -> None:
        entity_id = f"sensor.{self.prefix}_{suffix}"
        response = requests.post(
            f"{HA_API}/states/{entity_id}",
            headers=self.headers,
            json={"state": state or "unknown", "attributes": attributes},
            timeout=15,
        )
        response.raise_for_status()

    def publish_track(self, track: Track, status: str, day_count: int, month_count: int,
                      diagnostics: dict[str, Any] | None = None) -> None:
        attributes = asdict(track)
        attributes.update(
            {
                "friendly_name": "Turntable Now Playing",
                "icon": "mdi:album",
                "recognition_status": status,
                "recognized_at": datetime.now(timezone.utc).isoformat(),
                "requests_today": day_count,
                "requests_this_month": month_count,
            }
        )
        self.set_state("now_playing", track.title or "unknown", attributes)
        simple = {
            "artist": (track.artist, "Turntable Artist", "mdi:account-music"),
            "title": (track.title, "Turntable Song", "mdi:music-note"),
            "album": (track.album, "Turntable Album", "mdi:album"),
            "year": (track.year, "Turntable Year", "mdi:calendar"),
        }
        for suffix, (state, name, icon) in simple.items():
            self.set_state(suffix, state, {"friendly_name": name, "icon": icon})
        self.publish_status(status, day_count, month_count, details=diagnostics)

    def record_play(self, track: Track, session_id: str) -> None:
        entries = self.play_history.record(asdict(track), session_id)
        try:
            self.publish_play_history(entries)
        except Exception as exc:
            log_event("play_history_publish_failed", level="WARNING",
                      **exception_details(exc))

    def publish_play_history(self, entries: list[dict[str, Any]] | None = None) -> None:
        entries = entries if entries is not None else self.play_history.entries
        for index, suffix in ((1, "previous_track"), (2, "two_plays_ago")):
            # entries[0] is the current/recent recognized play; history sensors
            # show the two plays before it, matching their entity names.
            if len(entries) > index:
                entry = dict(entries[index])
                state = entry.get("title") or "Unknown track"
                entry.update({"friendly_name": "Turntable Previous Play" if index == 1
                              else "Turntable Two Plays Ago", "icon": "mdi:record-circle"})
            else:
                state = "Nothing recorded"
                entry = {
                    "friendly_name": "Turntable Previous Play" if index == 1
                    else "Turntable Two Plays Ago",
                    "icon": "mdi:record-circle",
                }
            self.set_state(suffix, state, entry)

    def clear_track(self) -> None:
        self.set_state("now_playing", "Nothing playing", {
            "friendly_name": "Turntable Now Playing", "icon": "mdi:album",
            "artist": "", "title": "", "album": "", "year": "", "artwork_url": "",
            "release_year": "", "master_year": "", "release_artwork_url": "",
            "master_artwork_url": "", "discogs_release_id": "", "discogs_master_id": "",
        })
        for suffix in ("artist", "title", "album", "year"):
            self.set_state(suffix, "unknown", {"friendly_name": "Turntable " + suffix.title()})

    def publish_status(self, status: str, day_count: int, month_count: int, error: str = "",
                       details: dict[str, Any] | None = None) -> None:
        attributes = {
            "friendly_name": "Turntable Recognition Status",
            "icon": "mdi:waveform",
            "requests_today": day_count,
            "requests_this_month": month_count,
            "last_error": error,
        }
        attributes.update(details or {})
        self.set_state(
            "recognition_status",
            status,
            attributes,
        )
        if self.limiter:
            details = self.limiter.details()
            display_status = "limit reached" if details["limit_reached"] else "available"
            self.set_state(
                "audd_usage",
                str(details["requests_this_cycle"]),
                {
                    "friendly_name": "AudD Requests This Billing Cycle",
                    "icon": "mdi:chart-donut",
                    "unit_of_measurement": "requests",
                    "state_class": "total",
                    "status": display_status,
                    **details,
                },
            )
            self.set_state(
                "audd_requests_remaining",
                str(details["remaining"]),
                {
                    "friendly_name": "AudD Requests Remaining",
                    "icon": "mdi:counter",
                    "unit_of_measurement": "requests",
                    "state_class": "measurement",
                    "cycle_end": details["cycle_end"],
                    "status": display_status,
                },
            )


def load_options() -> dict[str, Any]:
    return json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))


def main() -> int:
    options = load_options()
    mode = options.get("input_mode", "usb_auto")
    log_event("app_starting", input_mode=mode, provider="audd",
              audio_source=options.get("audio_source", "auto") if mode in {"usb_auto", "usb_meter"} else None,
              discogs_enabled=bool(options.get("discogs_enabled", False)),
              discogs_database_path=options.get("discogs_database_path", "/share/home_apps.sqlite3")
              if options.get("discogs_enabled", False) else None,
              sample_seconds=options.get("sample_seconds", 15),
              audd_token_configured=bool(options.get("audd_api_token")))
    limiter = UsageLimiter(
        int(options.get("max_requests_per_day", 100)),
        int(options.get("max_requests_per_month", 1000)),
        int(options.get("billing_cycle_day", 1)),
    )
    publisher = HomeAssistantPublisher(options.get("entity_prefix", "turntable"), limiter)
    publisher.publish_play_history()
    provider_factory = lambda token: AudDProvider(token, options)
    if mode == "usb_auto":
        automatic = AutomaticRecognition(options, publisher, limiter, provider_factory)
        automatic.start()
        run_meter(options, publisher, automatic=automatic)
        return 0
    if mode == "usb_meter":
        manual = ManualRecognition(options, publisher, limiter, provider_factory)
        manual.start()
        run_meter(options, publisher, manual)
        return 0

    raise RuntimeError(f"Unsupported input mode: {mode}. Use usb_auto or usb_meter.")


if __name__ == "__main__":
    raise SystemExit(main())

