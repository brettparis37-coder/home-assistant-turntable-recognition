import sqlite3
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from discogs_matcher import DiscogsMatcher, apply_match


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "home_apps.sqlite3"
        db = sqlite3.connect(self.path)
        try:
            db.executescript("""
                CREATE TABLE discogs_collection_entries(instance_id INTEGER, release_id INTEGER);
                CREATE TABLE discogs_releases(release_id INTEGER, master_id INTEGER, title TEXT, year INTEGER,
                    cover_image TEXT, thumb TEXT);
                CREATE TABLE discogs_masters(master_id INTEGER, year INTEGER, artwork_url TEXT, thumb_url TEXT);
                CREATE TABLE discogs_tracks(track_key TEXT, release_id INTEGER, sequence INTEGER,
                    title TEXT, position TEXT, track_type TEXT);
                CREATE TABLE discogs_release_artists(release_id INTEGER, artist_key INTEGER);
                CREATE TABLE discogs_artists(artist_key INTEGER, name TEXT);
                CREATE TABLE discogs_track_credits(track_key TEXT, artist_key INTEGER);
                INSERT INTO discogs_collection_entries VALUES (1, 10), (2, 11);
                INSERT INTO discogs_releases VALUES (10, 100, 'Owned Album', 1978, 'https://release/art.jpg', 'https://release/thumb.jpg');
                INSERT INTO discogs_releases VALUES (11, 101, 'Not Owned Match', 1980, 'https://other/art.jpg', '');
                INSERT INTO discogs_releases VALUES (9, 99, 'Unowned Album', 1970, 'https://unowned/art.jpg', '');
                INSERT INTO discogs_masters VALUES (100, 1977, 'https://master/art.jpg', 'https://master/thumb.jpg');
                INSERT INTO discogs_masters VALUES (101, 1979, 'https://other/master.jpg', '');
                INSERT INTO discogs_masters VALUES (99, 1969, 'https://unowned/master.jpg', '');
                INSERT INTO discogs_tracks VALUES ('10:1', 10, 1, 'A Great Song!', 'A1', 'track');
                INSERT INTO discogs_tracks VALUES ('10:2', 10, 2, 'A Great Song!', 'A2', 'track');
                INSERT INTO discogs_tracks VALUES ('11:1', 11, 1, 'A Great Song!', 'A1', 'track');
                INSERT INTO discogs_tracks VALUES ('9:1', 9, 1, 'A Great Song!', 'A1', 'track');
                INSERT INTO discogs_release_artists VALUES (10, 1), (11, 2);
                INSERT INTO discogs_artists VALUES (1, 'The Artist'), (2, 'Different Artist');
                INSERT INTO discogs_track_credits VALUES ('10:1', 1), ('10:2', 1), ('11:1', 2), ('9:1', 1);
            """)
        finally:
            db.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_track_matches_only_collection_and_artist_and_returns_both_images_years(self):
        match = DiscogsMatcher(str(self.path)).match("The Artist", "A Great Song")
        self.assertEqual(match["release_id"], 10)
        self.assertEqual(match["release_year"], 1978)
        self.assertEqual(match["master_year"], 1977)
        self.assertEqual(match["release_artwork_url"], "https://release/art.jpg")
        self.assertEqual(match["master_artwork_url"], "https://master/art.jpg")

    def test_no_track_match_returns_none(self):
        matcher = DiscogsMatcher(str(self.path))
        self.assertIsNone(matcher.match("The Artist", "A Great Sng"))
        self.assertEqual(matcher.last_diagnostics["status"], "no_exact_track_title")
        self.assertEqual(matcher.last_diagnostics["collection_track_count"], 3)
        self.assertEqual(matcher.last_diagnostics["closest_track_titles"][0]["track_title"], "A Great Song!")

    def test_artist_mismatch_is_reported_for_exact_title_candidates(self):
        matcher = DiscogsMatcher(str(self.path))
        result = matcher.match("A Different Artist", "A Great Song")
        self.assertEqual(result["release_id"], 10)
        self.assertFalse(matcher.last_diagnostics["artist_match"])
        self.assertEqual(matcher.last_diagnostics["exact_title_candidate_count"], 3)
        self.assertEqual(matcher.last_diagnostics["status"], "matched")

    def test_apply_match_keeps_both_values_and_selects_configured_defaults(self):
        track = SimpleNamespace(year="1985", title="Provider title", artist="Provider artist",
                                album="Provider album", artwork_url="provider.jpg",
                                artwork_source="provider", selection_reason="provider")
        apply_match(track, {
            "release_id": 10, "master_id": 100, "album": "Owned Album",
            "track_title": "A Great Song!", "track_artists": "The Artist",
            "release_year": 1978, "master_year": 1977,
            "release_artwork_url": "release.jpg", "master_artwork_url": "master.jpg",
        }, {"discogs_year_preference": "master", "discogs_artwork_preference": "release"})
        self.assertEqual(track.release_year, "1978")
        self.assertEqual(track.master_year, "1977")
        self.assertEqual(track.year, "1977")
        self.assertEqual(track.artwork_url, "release.jpg")
        self.assertEqual(track.artwork_source, "discogs_release")
        self.assertEqual(track.title, "A Great Song!")
        self.assertEqual(track.artist, "The Artist")

    def test_audd_match_uses_local_discogs_before_catalog_fallback(self):
        fake_requests = types.ModuleType("requests")
        fake_requests.post = None
        main_path = Path(__file__).with_name("main.py")
        spec = importlib.util.spec_from_file_location("turntable_main_discogs_test", main_path)
        main = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"requests": fake_requests, spec.name: main}):
            spec.loader.exec_module(main)

        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"status": "success", "result": {
                    "artist": "The Artist", "title": "A Great Song!", "album": "Provider album",
                    "release_date": "1985-01-01", "timecode": "00:20",
                    "spotify": {"duration_ms": 180000, "album": {"name": "Provider album"}},
                }}

        match = {
            "release_id": 10, "master_id": 100, "album": "Owned Album",
            "track_title": "A Great Song!", "track_artists": "The Artist",
            "release_year": 1978, "master_year": 1977,
            "release_artwork_url": "release.jpg", "master_artwork_url": "master.jpg",
        }
        with patch.object(main.requests, "post", return_value=Response()), \
             patch.object(main.DiscogsMatcher, "match", return_value=match), \
             patch.object(main, "resolve_audd_payload") as catalog_resolver:
            result = main.AudDProvider("test-token", {
                "discogs_enabled": True, "discogs_artwork_preference": "master",
                "discogs_year_preference": "release",
            }).recognize("https://audio.example/test.wav", True)
        self.assertEqual(result.album, "Owned Album")
        self.assertEqual(result.year, "1978")
        self.assertEqual(result.master_year, "1977")
        self.assertEqual(result.artwork_url, "master.jpg")
        catalog_resolver.assert_not_called()


if __name__ == "__main__":
    unittest.main()

