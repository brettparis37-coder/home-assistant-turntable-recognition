import json
import tempfile
import unittest
from pathlib import Path
from album_resolver import parse_timecode, normalized_name, standard_release_rank, resolve_audd_payload


class EmptyCatalogClient:
    def get(self, url, musicbrainz=False):
        return {"recordings": [], "results": []}


class AppleTrackClient:
    def get(self, url, musicbrainz=False):
        if "itunes.apple.com" in url and "entity=song" in url:
            return {"results": [
                {"artistName": "Erasmo Carlos", "trackName": "É preciso dar um jeito, meu amigo",
                 "collectionName": "Carlos, Erasmo (Versão Com Bônus)", "collectionType": "Album",
                 "releaseDate": "1971-01-01", "artworkUrl100": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
                 "trackTimeMillis": 210000},
                {"artistName": "Erasmo Carlos", "trackName": "É preciso dar um jeito, meu amigo",
                 "collectionName": "Carlos, Erasmo", "collectionType": "Album",
                 "releaseDate": "1971-01-01", "artworkUrl100": "https://is1-ssl.mzstatic.com/image/original/100x100bb.jpg",
                 "trackTimeMillis": 210000},
                {"artistName": "Erasmo Carlos", "trackName": "É preciso dar um jeito, meu amigo",
                 "collectionName": "É Preciso Dar Um Jeito, Meu Amigo - Single", "collectionType": "Album",
                 "releaseDate": "2025-01-01", "artworkUrl100": "https://wrong.example/single.jpg"},
            ]}
        return {"recordings": [], "results": []}


class RecordingSearchClient:
    def get(self, url, musicbrainz=False):
        return {"recordings": [
            {"id": "matched", "title": "É preciso dar um jeito, meu amigo", "score": "100",
             "artist-credit": [{"name": "Erasmo Carlos"}], "releases": []},
            {"id": "wrong-artist", "title": "É preciso dar um jeito, meu amigo", "score": "100",
             "artist-credit": [{"name": "Other Artist"}], "releases": []},
        ]}


class ResolverTests(unittest.TestCase):
    def test_timecode(self):
        self.assertEqual(parse_timecode("02:32"), 152)
        self.assertIsNone(parse_timecode("bad"))

    def test_normalizes_edition_suffix(self):
        self.assertEqual(normalized_name("Songs From the Big Chair (Super Deluxe Version)"),
                         "songs from the big chair")

    def test_standard_original_release_beats_deluxe(self):
        standard = {"id":"a", "title":"Album", "date":"1985-02-17",
                    "cover-art-archive":{"front":True}}
        deluxe = {"id":"b", "title":"Album (Super Deluxe Edition)", "date":"1985-02-01",
                  "cover-art-archive":{"front":True}}
        self.assertLess(standard_release_rank(standard, "1985-02-01"),
                        standard_release_rank(deluxe, "1985-02-01"))

    def test_song_page_is_not_used_as_album_art(self):
        payload = {"result": {
            "artist": "Erasmo Carlos",
            "title": "É preciso dar um jeito, meu amigo",
            "album": "Carlos, Erasmo...",
            "release_date": "1971-01-01",
            "song_link": "https://youtu.be/FuZ0OdtK3P8",
        }}
        resolved = resolve_audd_payload(payload, client=EmptyCatalogClient())
        self.assertEqual(resolved.artwork_url, "")
        self.assertEqual(resolved.artwork_source, "")

    def test_direct_provider_image_is_preserved(self):
        image = "https://i.scdn.co/image/cover.jpg"
        payload = {"result": {
            "artist": "Artist", "title": "Song", "album": "Album",
            "spotify": {"album": {"images": [{"url": image}]}},
            "song_link": "https://youtu.be/example",
        }}
        resolved = resolve_audd_payload(payload, client=EmptyCatalogClient())
        self.assertEqual(resolved.artwork_url, image)
        self.assertEqual(resolved.artwork_source, "provider_fallback")

    def test_musicbrainz_search_requires_exact_artist_and_title(self):
        from album_resolver import search_recording
        result = search_recording(RecordingSearchClient(), "Erasmo Carlos",
                                  "É preciso dar um jeito, meu amigo")
        self.assertEqual(result.get("id"), "matched")

    def test_track_match_finds_original_album_art_and_duration(self):
        payload = {"result": {
            "artist": "Erasmo Carlos", "title": "É preciso dar um jeito, meu amigo",
            "album": "Carlos, Erasmo...", "release_date": "1971-01-01",
            "song_link": "https://youtu.be/FuZ0OdtK3P8",
        }}
        resolved = resolve_audd_payload(payload, client=AppleTrackClient())
        self.assertEqual(resolved.album, "Carlos, Erasmo")
        self.assertEqual(resolved.artwork_url, "https://is1-ssl.mzstatic.com/image/original/600x600bb.jpg")
        self.assertEqual(resolved.artwork_source, "apple_catalog_exact_track_album")
        self.assertEqual(resolved.duration_seconds, 210)

    def test_replaces_cached_youtube_song_link_with_real_cover_art(self):
        payload = {"result": {
            "artist": "Erasmo Carlos", "title": "É preciso dar um jeito, meu amigo",
            "album": "Carlos, Erasmo...", "release_date": "1971-01-01",
            "song_link": "https://youtu.be/FuZ0OdtK3P8",
            "musicbrainz": [{"id": "recording-id", "score": "100",
                             "title": "É preciso dar um jeito, meu amigo", "releases": []}],
        }}
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "album_cache.json"
            cache_path.write_text(json.dumps({"recording-id": {
                "album": "Carlos, Erasmo...", "album_year": "1971",
                "album_release_date": "1971-01-01", "album_release_id": "release-id",
                "artwork_url": "https://youtu.be/FuZ0OdtK3P8?thumb",
                "artwork_source": "provider_fallback",
            }}), encoding="utf-8")

            resolved = resolve_audd_payload(payload, client=AppleTrackClient(), cache_path=cache_path)
            saved = json.loads(cache_path.read_text(encoding="utf-8"))["recording-id"]

        expected = "https://is1-ssl.mzstatic.com/image/original/600x600bb.jpg"
        self.assertEqual(resolved.artwork_url, expected)
        self.assertEqual(resolved.artwork_source, "apple_catalog_exact_track_album")
        self.assertEqual(saved["artwork_url"], expected)
        self.assertFalse(resolved.artwork_url.startswith("https://youtu.be/"))


if __name__ == "__main__": unittest.main()

