#!/usr/bin/env python3
"""Turntable recognition Home Assistant app."""

from __future__ import annotations

import json
import calendar
import os
import re
import subprocess
import sys
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

    def __init__(self, token: str) -> None:
        if not token:
            raise RecognitionError("An AudD API token is required for this input mode")
        self.token = token

    def recognize(self, source: str, source_is_url: bool) -> Track:
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
        if payload.get("status") != "success":
            error = payload.get("error") or {}
            raise RecognitionError(error.get("error_message") or "AudD request failed")
        result = payload.get("result")
        if not result:
            raise RecognitionError("No song was recognized")

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
            print(f"Album metadata: {base.album} ({base.year}); artwork={base.artwork_source}", flush=True)
        except Exception as exc:
            print(f"Album metadata enrichment unavailable; using AudD providers: {exc}", file=sys.stderr, flush=True)
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

    def publish_track(self, track: Track, status: str, day_count: int, month_count: int) -> None:
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
        self.publish_status(status, day_count, month_count)

    def clear_track(self) -> None:
        self.set_state("now_playing", "Nothing playing", {
            "friendly_name": "Turntable Now Playing", "icon": "mdi:album",
            "artist": "", "title": "", "album": "", "year": "", "artwork_url": "",
        })
        for suffix in ("artist", "title", "album", "year"):
            self.set_state(suffix, "unknown", {"friendly_name": "Turntable " + suffix.title()})

    def publish_status(self, status: str, day_count: int, month_count: int, error: str = "") -> None:
        self.set_state(
            "recognition_status",
            status,
            {
                "friendly_name": "Turntable Recognition Status",
                "icon": "mdi:waveform",
                "requests_today": day_count,
                "requests_this_month": month_count,
                "last_error": error,
            },
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


def mock_track(options: dict[str, Any]) -> Track:
    year = str(options.get("mock_year", ""))
    return Track(
        artist=str(options.get("mock_artist", "")),
        title=str(options.get("mock_title", "")),
        album=str(options.get("mock_album", "")),
        release_date=year,
        year=year,
        provider="mock",
    )


def capture_simulated_usb(options: dict[str, Any]) -> str:
    """Create the same short WAV that future USB capture will produce."""
    configured = str(options.get("media_file", "")).lstrip("/")
    source = Path("/media") / configured
    if not source.is_file():
        raise RecognitionError(f"Simulation source does not exist: {source}")
    output = Path("/tmp/turntable-capture.wav")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(int(options.get("simulated_start_seconds", 0))),
        "-i",
        str(source),
        "-t",
        str(int(options.get("sample_seconds", 12))),
        "-ac",
        "1",
        "-ar",
        "44100",
        str(output),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except subprocess.CalledProcessError as exc:
        raise RecognitionError(f"Simulated capture failed: {exc.stderr.strip()}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RecognitionError("Simulated capture timed out") from exc
    if not output.is_file() or output.stat().st_size == 0:
        raise RecognitionError("Simulated capture produced no audio")
    return str(output)


def main() -> int:
    options = load_options()
    mode = options.get("input_mode", "mock")
    limiter = UsageLimiter(
        int(options.get("max_requests_per_day", 100)),
        int(options.get("max_requests_per_month", 1000)),
        int(options.get("billing_cycle_day", 1)),
    )
    publisher = HomeAssistantPublisher(options.get("entity_prefix", "turntable"), limiter)
    day_count, month_count = limiter.counts()
    if mode == "usb_auto":
        automatic = AutomaticRecognition(options, publisher, limiter, AudDProvider)
        automatic.start()
        run_meter(options, publisher, automatic=automatic)
        return 0
    if mode == "usb_meter":
        manual = ManualRecognition(options, publisher, limiter, AudDProvider)
        manual.start()
        run_meter(options, publisher, manual)
        return 0

    try:
        if mode == "mock":
            publisher.publish_track(mock_track(options), "mock", day_count, month_count)
            print("Published mock turntable metadata", flush=True)
        else:
            if options.get("provider") != "audd":
                raise RecognitionError(f"Unsupported provider: {options.get('provider')}")
            provider = AudDProvider(str(options.get("audd_api_token", "")))
            if mode == "audio_url":
                source = str(options.get("test_audio_url", ""))
                source_is_url = True
            elif mode == "media_file":
                configured = str(options.get("media_file", "")).lstrip("/")
                source = str(Path("/media") / configured)
                source_is_url = False
            elif mode == "simulated_usb":
                publisher.publish_status("capturing", day_count, month_count)
                source = capture_simulated_usb(options)
                source_is_url = False
            else:
                raise RecognitionError(f"Unsupported input mode: {mode}")

            day_count, month_count = limiter.consume()
            publisher.publish_status("recognizing", day_count, month_count)
            track = provider.recognize(source, source_is_url)
            publisher.publish_track(track, "recognized", day_count, month_count)
            print(f"Recognized: {track.artist} - {track.title}", flush=True)
    except Exception as exc:
        day_count, month_count = limiter.counts()
        message = str(exc)
        print(f"Recognition error: {message}", file=sys.stderr, flush=True)
        try:
            status = "api_limit_reached" if "AudD API limit reached" in message else "error"
            publisher.publish_status(status, day_count, month_count, message)
        except Exception as publish_exc:
            print(f"Could not publish error status: {publish_exc}", file=sys.stderr, flush=True)

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    raise SystemExit(main())

