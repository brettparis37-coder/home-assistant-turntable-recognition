"""Resolve an AudD match to an original official album and usable cover URL."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path


USER_AGENT = "TurntableRecognition/0.4.0 (https://github.com/brettparis37-coder/home-assistant-turntable-recognition)"
EDITION_WORDS = ("deluxe", "expanded", "anniversary", "remaster", "bonus", "super deluxe")


@dataclass
class ResolvedMetadata:
    artist: str
    title: str
    recognized_version: str
    album: str
    album_year: str
    album_release_date: str
    album_type: str
    album_release_group_id: str
    album_release_id: str
    artwork_url: str
    artwork_source: str
    duration_seconds: float | None
    position_seconds: float | None
    timing_source: str
    isrc: str
    musicbrainz_recording_id: str
    selection_reason: str

    def to_dict(self):
        return asdict(self)


class JsonClient:
    def __init__(self):
        self.last_call = 0.0

    def get(self, url: str, musicbrainz: bool = False):
        if musicbrainz:
            delay = 1.05 - (time.monotonic() - self.last_call)
            if delay > 0:
                time.sleep(delay)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
        if musicbrainz:
            self.last_call = time.monotonic()
        return value


def parse_timecode(value):
    try:
        total = 0.0
        for part in str(value).split(":"):
            total = total * 60 + float(part)
        return total if total >= 0 else None
    except (TypeError, ValueError):
        return None


def first_value(*values):
    return next((value for value in values if value not in (None, "", [])), None)


def choose_recording(result):
    entries = result.get("musicbrainz") or []
    return max(entries, key=lambda item: float(item.get("score") or 0), default={})


def choose_album_group(recording):
    groups = {}
    for release in recording.get("releases") or []:
        group = release.get("release-group") or {}
        secondary = group.get("secondary-types") or []
        if release.get("status") == "Official" and group.get("primary-type") == "Album" and not secondary:
            groups[group.get("id")] = group
    return next(iter(groups.values()), {})


def standard_release_rank(release, group_date):
    text = f"{release.get('title', '')} {release.get('disambiguation', '')}".casefold()
    special = any(word in text for word in EDITION_WORDS)
    date = release.get("date") or "9999-99-99"
    original_year = str(group_date or "")[:4]
    same_original_year = bool(original_year and date.startswith(original_year))
    has_front = bool((release.get("cover-art-archive") or {}).get("front"))
    # Prefer original-year standard editions, then one with a verified front cover.
    return (special, not same_original_year, not has_front, date, release.get("id", ""))


def browse_official_releases(client, group_id):
    releases, offset = [], 0
    while True:
        query = urllib.parse.urlencode({
            "release-group": group_id, "status": "official", "inc": "artist-credits+media",
            "limit": 100, "offset": offset, "fmt": "json",
        })
        page = client.get(f"https://musicbrainz.org/ws/2/release?{query}", musicbrainz=True)
        batch = page.get("releases") or []
        releases.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(page.get("release-count") or 0):
            break
    return releases


def archive_front_url(client, release_id):
    identifier = f"mbid-{release_id}"
    metadata = client.get(f"https://archive.org/metadata/{identifier}")
    pattern = re.compile(rf"^{re.escape(identifier)}-(\d+)\.jpg$")
    originals = []
    for item in metadata.get("files") or []:
        match = pattern.match(item.get("name", ""))
        if match and item.get("source") == "original":
            originals.append((int(match.group(1)), item["name"]))
    if not originals:
        return ""
    # Cover Art Archive stores the curated front image first in the release item.
    artwork_id, _ = min(originals)
    filename = f"{identifier}-{artwork_id}_thumb500.jpg"
    return f"https://archive.org/download/{identifier}/{filename}"


def normalized_name(value):
    value = re.sub(r"\([^)]*(deluxe|expanded|anniversary|remaster|bonus)[^)]*\)", "", str(value), flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def apple_album_art(client, artist, album, album_year):
    query = urllib.parse.urlencode({
        "term": f"{artist} {album}", "entity": "album", "limit": 25, "country": "US",
    })
    results = client.get(f"https://itunes.apple.com/search?{query}").get("results") or []
    wanted_artist, wanted_album = normalized_name(artist), normalized_name(album)
    candidates = []
    for item in results:
        item_artist, item_album = normalized_name(item.get("artistName")), normalized_name(item.get("collectionName"))
        text = str(item.get("collectionName", "")).casefold()
        if item_artist == wanted_artist and item_album == wanted_album and not any(word in text for word in EDITION_WORDS):
            same_year = str(item.get("releaseDate", "")).startswith(str(album_year))
            candidates.append((not same_year, str(item.get("releaseDate", "")), str(item.get("collectionId", "")), item))
    if not candidates:
        return ""
    item = min(candidates)[3]
    artwork = str(item.get("artworkUrl100") or "")
    return artwork.replace("/100x100bb.", "/600x600bb.")


def resolve_audd_payload(payload, client=None, cache_path=None):
    client = client or JsonClient()
    result = payload.get("result") or {}
    spotify = result.get("spotify") or {}
    apple = result.get("apple_music") or {}
    recording = choose_recording(result)
    group = choose_album_group(recording)

    spotify_isrc = (spotify.get("external_ids") or {}).get("isrc")
    apple_isrc = apple.get("isrc")
    mb_isrcs = recording.get("isrcs") or []
    isrc = first_value(spotify_isrc, apple_isrc, mb_isrcs[0] if mb_isrcs else "") or ""
    cache_key = recording.get("id") or isrc
    cache_file = Path(cache_path) if cache_path else None
    cache = {}
    if cache_file:
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    cached = cache.get(cache_key, {}) if cache_key else {}

    release_group_id = group.get("id", "")
    group_detail, release = {}, {}
    if cached:
        release_group_id = cached.get("album_release_group_id", release_group_id)
        release = {"id": cached.get("album_release_id", ""), "title": cached.get("album", "")}
        group_detail = {
            "title": cached.get("album", ""),
            "first-release-date": cached.get("album_release_date", ""),
        }
    elif release_group_id:
        group_detail = client.get(
            f"https://musicbrainz.org/ws/2/release-group/{release_group_id}?fmt=json",
            musicbrainz=True,
        )
        candidates = browse_official_releases(client, release_group_id)
        if candidates:
            release = min(candidates, key=lambda value: standard_release_rank(value, group_detail.get("first-release-date")))

    release_id = release.get("id", "")
    album_name = first_value(group_detail.get("title"), group.get("title"), release.get("title"), result.get("album")) or ""
    album_date = group_detail.get("first-release-date") or release.get("date") or result.get("release_date") or ""
    artwork = cached.get("artwork_url", "")
    artwork_source = cached.get("artwork_source", "")
    if not artwork and album_name:
        artwork = apple_album_art(client, result.get("artist") or "", album_name, str(album_date)[:4])
        artwork_source = "apple_catalog_exact_original_album" if artwork else ""
    if not artwork and release_id:
        artwork = archive_front_url(client, release_id)
        artwork_source = "musicbrainz_release_via_internet_archive" if artwork else ""
    if not artwork:
        spotify_images = (spotify.get("album") or {}).get("images") or []
        apple_art = (apple.get("artwork") or {}).get("url") or ""
        artwork = first_value(
            spotify_images[0].get("url") if spotify_images else "",
            apple_art.replace("{w}", "600").replace("{h}", "600") if apple_art else "",
            f"{result.get('song_link')}?thumb" if result.get("song_link") else "",
        ) or ""
        artwork_source = "provider_fallback" if artwork else ""

    duration_ms = first_value(spotify.get("duration_ms"), apple.get("durationInMillis"), recording.get("length"))
    duration = float(duration_ms) / 1000 if duration_ms else None
    position = parse_timecode(result.get("timecode"))
    if duration is not None and position is not None and position >= duration:
        position = None

    resolved = ResolvedMetadata(
        artist=result.get("artist") or "",
        title=result.get("title") or "",
        recognized_version=first_value(recording.get("title"), spotify.get("name"), apple.get("name"), result.get("title")) or "",
        album=album_name,
        album_year=str(album_date)[:4], album_release_date=str(album_date), album_type="Album" if release_group_id else "",
        album_release_group_id=release_group_id, album_release_id=release_id,
        artwork_url=artwork, artwork_source=artwork_source,
        duration_seconds=duration, position_seconds=position,
        timing_source="spotify" if spotify.get("duration_ms") else "apple_music" if apple.get("durationInMillis") else "musicbrainz" if recording.get("length") else "",
        isrc=isrc, musicbrainz_recording_id=recording.get("id") or "",
        selection_reason="official original album; standard original-year edition with front art preferred" if release_id else "provider metadata fallback",
    )
    if cache_file and cache_key and not cached and release_id:
        cache[cache_key] = {
            key: value for key, value in resolved.to_dict().items()
            if key in {"album", "album_year", "album_release_date", "album_type",
                       "album_release_group_id", "album_release_id", "artwork_url",
                       "artwork_source", "selection_reason"}
        }
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        temporary.replace(cache_file)
    return resolved
