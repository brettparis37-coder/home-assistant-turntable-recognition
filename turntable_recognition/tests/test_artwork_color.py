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


if __name__ == "__main__":
    unittest.main()

