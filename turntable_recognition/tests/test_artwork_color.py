import unittest
import importlib.util
import sys
import types
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import artwork_color


class ArtworkColorTests(unittest.TestCase):
    def test_rejects_unknown_hosts_before_requesting_image(self):
        with patch.object(artwork_color, "_read_image_bytes") as read_image:
            self.assertEqual(artwork_color.dominant_artwork_color("https://example.com/cover.jpg"), "")
        read_image.assert_not_called()

    def test_favors_visible_cover_color_over_dark_blue_shadow(self):
        image = Image.new("RGB", (48, 48), (12, 18, 66))
        for x in range(18, 48):
            for y in range(48):
                image.putpixel((x, y), (245, 120, 20))
        buffer = BytesIO()
        image.save(buffer, format="PNG")

        with patch.object(artwork_color, "_read_image_bytes", return_value=buffer.getvalue()) as read_image:
            color = artwork_color.dominant_artwork_color("https://i.scdn.co/image/cover.png")

        read_image.assert_called_once()
        self.assertRegex(color, r"^#[0-9a-f]{6}$")
        red, green, blue = (int(color[index:index + 2], 16) for index in (1, 3, 5))
        self.assertGreater(red, green)
        self.assertGreater(green, blue)

    def test_recognized_track_publishes_color_with_now_playing_state(self):
        fake_requests = types.ModuleType("requests")
        fake_requests.post = None
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        spec = importlib.util.spec_from_file_location("turntable_main_artwork_test", main_path)
        main = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"requests": fake_requests, spec.name: main}):
            spec.loader.exec_module(main)
        publisher = main.HomeAssistantPublisher("turntable")
        track = main.Track(title="Song", artist="Artist", artwork_url="https://i.scdn.co/image/cover.jpg")
        with patch.object(main, "dominant_artwork_color", return_value="#c06020"), \
             patch.object(publisher, "set_state") as set_state:
            publisher.publish_track(track, "recognized", 1, 2)

        entity, _state, attributes = set_state.call_args_list[0].args
        self.assertEqual(entity, "now_playing")
        self.assertEqual(attributes["recognition_status"], "recognized")
        self.assertEqual(attributes["dominant_color"], "#c06020")

    def test_now_playing_publishes_facts_from_discogs_match(self):
        fake_requests = types.ModuleType("requests")
        fake_requests.post = None
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        spec = importlib.util.spec_from_file_location("turntable_main_track_facts_test", main_path)
        main = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"requests": fake_requests, spec.name: main}):
            spec.loader.exec_module(main)

        fact = {"fact_order": 1, "fact_text": "A researched fact.",
                "source_title": "Source", "source_url": "https://example.com",
                "source_publisher": "Publisher", "fact_set_status": "needs_review"}

        class FactsMatcher:
            def facts_for_track(self, release_id, sequence):
                self.requested = (release_id, sequence)
                return [fact]

        matcher = FactsMatcher()
        publisher = main.HomeAssistantPublisher("turntable", discogs_matcher=matcher)
        track = main.Track(title="Song", artist="Artist", discogs_release_id="123",
                           discogs_track_sequence=4)
        with patch.object(publisher, "set_state") as set_state:
            publisher.publish_track(track, "recognized", 0, 0)

        self.assertEqual(matcher.requested, ("123", 4))
        _entity, _state, attributes = set_state.call_args_list[0].args
        self.assertEqual(attributes["track_facts"], [fact])
        self.assertEqual(attributes["track_facts_count"], 1)

    def test_prediction_is_published_as_tentative_now_playing_and_separate_next_sensor(self):
        fake_requests = types.ModuleType("requests")
        fake_requests.post = None
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        spec = importlib.util.spec_from_file_location("turntable_main_prediction_test", main_path)
        main = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"requests": fake_requests, spec.name: main}):
            spec.loader.exec_module(main)

        class Limiter:
            def counts(self): return 0, 0
            def details(self):
                return {"limit_reached": False, "requests_this_cycle": 0,
                        "allowance": 100, "remaining": 100, "cycle_end": "2026-10-25"}

        publisher = main.HomeAssistantPublisher("turntable", Limiter())
        current = {"title": "Predicted song", "artist": "Artist", "album": "Album",
                   "provider": "discogs_prediction", "artwork_url": "https://i.scdn.co/image/cover.jpg",
                   "discogs_release_id": "123", "discogs_track_sequence": 2}
        following = {**current, "title": "Following song", "discogs_track_sequence": 3}
        with patch.object(main, "dominant_artwork_color", return_value="#c06020"), \
             patch.object(publisher, "set_state") as set_state:
            publisher.publish_prediction(current, following)

        states = {call.args[0]: (call.args[1], call.args[2]) for call in set_state.call_args_list}
        now_title, now_attrs = states["now_playing"]
        next_title, next_attrs = states["predicted_next"]
        self.assertEqual(now_title, "Predicted song")
        self.assertEqual(now_attrs["recognition_status"], "predicted")
        self.assertTrue(now_attrs["is_prediction"])
        self.assertEqual(now_attrs["dominant_color"], "#c06020")
        self.assertEqual(next_title, "Following song")
        self.assertTrue(next_attrs["available"])


if __name__ == "__main__":
    unittest.main()

