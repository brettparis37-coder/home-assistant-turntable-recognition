"""Read-only matching against tracks cached from the Discogs collection app."""
from __future__ import annotations

import re
import sqlite3
from difflib import get_close_matches
from pathlib import Path


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


class DiscogsMatcher:
    def __init__(self, database_path: str = "/share/home_apps.sqlite3") -> None:
        self.database_path = Path(database_path)
        self.last_diagnostics = {"status": "not_run"}
        self.last_prediction_diagnostics = {"status": "not_run"}

    def match(self, artist: str, title: str) -> dict | None:
        wanted_title = normalize(title)
        wanted_artist = normalize(artist)
        self.last_diagnostics = {"artist": artist, "title": title}
        if not wanted_title:
            self.last_diagnostics["status"] = "empty_recognized_title"
            return None
        if not self.database_path.is_file():
            self.last_diagnostics.update(status="database_missing", database_path=str(self.database_path))
            return None
        # Open the shared app database in read-only mode. The app configuration
        # grants the share mount for SQLite WAL reads; this client never writes.
        uri = self.database_path.resolve().as_uri() + "?mode=ro"
        connection = None
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=3)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            track_columns = {row[1] for row in connection.execute("PRAGMA table_info(discogs_tracks)")}
            duration_expression = "t.duration_ms" if "duration_ms" in track_columns else "NULL AS duration_ms"
            rows = connection.execute(
                f"""SELECT t.title AS track_title, t.position, t.sequence,
                          {duration_expression},
                          r.release_id, r.master_id, r.title AS album,
                          r.year AS release_year,
                          COALESCE(NULLIF(r.cover_image, ''), r.thumb) AS release_artwork_url,
                          r.thumb AS release_thumb_url,
                          m.year AS master_year,
                          COALESCE(NULLIF(m.artwork_url, ''), m.thumb_url) AS master_artwork_url,
                          m.thumb_url AS master_thumb_url,
                          GROUP_CONCAT(DISTINCT a.name) AS album_artists,
                          (SELECT GROUP_CONCAT(DISTINCT ta.name)
                             FROM discogs_track_credits tc
                             JOIN discogs_artists ta USING (artist_key)
                            WHERE tc.track_key = t.track_key) AS track_artists
                     FROM discogs_tracks t
                     JOIN discogs_collection_entries e USING (release_id)
                     JOIN discogs_releases r USING (release_id)
                     LEFT JOIN discogs_masters m ON m.master_id = r.master_id
                     LEFT JOIN discogs_release_artists ra USING (release_id)
                     LEFT JOIN discogs_artists a USING (artist_key)
                    WHERE t.track_type = 'track'
                    GROUP BY t.track_key
                    ORDER BY r.release_id, t.sequence"""
            ).fetchall()
        except (sqlite3.Error, OSError) as exc:
            self.last_diagnostics.update(status="database_query_failed", error_type=type(exc).__name__, error=str(exc))
            return None
        finally:
            if connection is not None:
                connection.close()

        candidates = []
        title_matches = []
        for row in rows:
            if normalize(row["track_title"]) != wanted_title:
                continue
            credits = normalize(" ".join(filter(None, (row["album_artists"], row["track_artists"]))))
            artist_match = bool(wanted_artist and wanted_artist in credits)
            candidates.append((not artist_match, row["release_id"], row["sequence"], row))
            title_matches.append({
                "release_id": row["release_id"], "album": row["album"],
                "track_title": row["track_title"],
                "album_artists": row["album_artists"] or "",
                "track_artists": row["track_artists"] or "",
                "artist_match": artist_match,
            })
        if not candidates:
            unique_titles = sorted({normalize(str(row["track_title"])): str(row["track_title"])
                                    for row in rows if row["track_title"]}.values())
            title_map = {normalize(value): value for value in unique_titles}
            suggestions = get_close_matches(wanted_title, list(title_map), n=3, cutoff=0.5)
            closest = []
            for normalized in suggestions:
                suggestion = title_map[normalized]
                related = [row for row in rows if normalize(str(row["track_title"])) == normalized]
                closest.append({
                    "track_title": suggestion,
                    "albums": list(dict.fromkeys(str(row["album"] or "") for row in related))[:3],
                    "release_ids": list(dict.fromkeys(int(row["release_id"]) for row in related))[:3],
                })
            self.last_diagnostics.update(
                status="no_exact_track_title", collection_track_count=len(rows),
                closest_track_titles=closest,
            )
            return None
        # Prefer a matching artist credit; otherwise use the first stable release
        # and track order. This is intentionally simple and deterministic.
        row = min(candidates, key=lambda value: value[:3])[3]
        self.last_diagnostics.update(
            status="matched", collection_track_count=len(rows),
            exact_title_candidate_count=len(title_matches),
            selected_release_id=row["release_id"],
            artist_match=next(item["artist_match"] for item in title_matches
                              if item["release_id"] == row["release_id"]),
            candidates=title_matches[:5],
        )
        return dict(row)

    def next_track(self, release_id: int | str, sequence: int | str) -> dict | None:
        """Return the next playable track on this exact Discogs release."""
        if not release_id or sequence in (None, "") or not self.database_path.is_file():
            return None
        uri = self.database_path.resolve().as_uri() + "?mode=ro"
        connection = None
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=3)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            track_columns = {row[1] for row in connection.execute("PRAGMA table_info(discogs_tracks)")}
            duration_expression = "t.duration_ms" if "duration_ms" in track_columns else "NULL AS duration_ms"
            row = connection.execute(
                f"""SELECT t.title AS track_title, t.position, t.sequence,
                          {duration_expression}, r.release_id, r.master_id,
                          r.title AS album, r.year AS release_year,
                          COALESCE(NULLIF(r.cover_image, ''), r.thumb) AS release_artwork_url,
                          r.thumb AS release_thumb_url, m.year AS master_year,
                          COALESCE(NULLIF(m.artwork_url, ''), m.thumb_url) AS master_artwork_url,
                          m.thumb_url AS master_thumb_url,
                          GROUP_CONCAT(DISTINCT a.name) AS album_artists,
                          (SELECT GROUP_CONCAT(DISTINCT ta.name)
                             FROM discogs_track_credits tc
                             JOIN discogs_artists ta USING (artist_key)
                            WHERE tc.track_key = t.track_key) AS track_artists
                     FROM discogs_tracks t
                     JOIN discogs_releases r USING (release_id)
                     LEFT JOIN discogs_masters m ON m.master_id = r.master_id
                     LEFT JOIN discogs_release_artists ra USING (release_id)
                     LEFT JOIN discogs_artists a USING (artist_key)
                    WHERE t.release_id = ? AND t.sequence > ? AND t.track_type = 'track'
                    GROUP BY t.track_key
                    ORDER BY t.sequence LIMIT 1""",
                (release_id, sequence),
            ).fetchone()
            self.last_prediction_diagnostics = {
                "status": "next_track_found" if row else "end_of_release",
                "release_id": release_id,
                "after_sequence": sequence,
            }
            return dict(row) if row else None
        except (sqlite3.Error, OSError, ValueError) as exc:
            self.last_prediction_diagnostics = {
                "status": "query_failed", "release_id": release_id,
                "after_sequence": sequence, "error_type": type(exc).__name__, "error": str(exc),
            }
            return None
        finally:
            if connection is not None:
                connection.close()

    def average_duration_seconds(self, release_id: int | str) -> float | None:
        """Estimate timing from known song durations on the same release."""
        if not release_id or not self.database_path.is_file():
            return None
        uri = self.database_path.resolve().as_uri() + "?mode=ro"
        connection = None
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=3)
            row = connection.execute(
                """SELECT AVG(duration_ms) FROM discogs_tracks
                    WHERE release_id = ? AND track_type = 'track' AND duration_ms > 0""",
                (release_id,),
            ).fetchone()
            return float(row[0]) / 1000 if row and row[0] else None
        except (sqlite3.Error, OSError, ValueError):
            return None
        finally:
            if connection is not None:
                connection.close()


def apply_match(track, match: dict, options: dict) -> None:
    """Apply cached release/master fields while retaining provider fallback values."""
    track.discogs_release_id = str(match.get("release_id") or "")
    track.discogs_master_id = str(match.get("master_id") or "")
    track.discogs_track_sequence = match.get("sequence")
    track.title = match.get("track_title") or track.title
    track.artist = match.get("track_artists") or match.get("album_artists") or track.artist
    track.album = match.get("album") or track.album
    track.release_year = str(match.get("release_year") or "")
    track.master_year = str(match.get("master_year") or "")
    track.release_artwork_url = match.get("release_artwork_url") or ""
    track.master_artwork_url = match.get("master_artwork_url") or ""

    year_preference = options.get("discogs_year_preference", "master")
    art_preference = options.get("discogs_artwork_preference", "master")
    selected_year = (track.master_year or track.release_year) if year_preference == "master" else (track.release_year or track.master_year)
    selected_art = (track.master_artwork_url or track.release_artwork_url) if art_preference == "master" else (track.release_artwork_url or track.master_artwork_url)
    if selected_year:
        track.year = selected_year
    if selected_art:
        track.artwork_url = selected_art
        track.artwork_source = "discogs_master" if selected_art == track.master_artwork_url else "discogs_release"
    track.selection_reason = "matched an exact track in the cached Discogs collection"
    duration_ms = match.get("duration_ms")
    if duration_ms and not track.duration_seconds:
        track.duration_seconds = float(duration_ms) / 1000
        track.timing_source = "discogs_collection"

