import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

# Keep the provider unit tests runnable with the standard-library-only Python
# bundle used in this workspace; the production image installs both packages.
try:
    import requests  # noqa: F401
except ImportError:
    sys.modules["requests"] = ModuleType("requests")
try:
    from PIL import Image  # noqa: F401
except ImportError:
    pil = ModuleType("PIL")
    pil.Image = object()
    sys.modules["PIL"] = pil

import main


class ShazamProviderTests(unittest.TestCase):
    def fake_shazam_module(self, payload):
        module = ModuleType("shazamio")

        class Shazam:
            async def recognize(self, source):
                self.source = source
                return payload

        module.Shazam = Shazam
        return module

    def test_shazam_match_skips_audd_and_maps_cover(self):
        used = []
        payload = {"track": {"title": "The Sky Is Crying", "subtitle": "George Thorogood",
                             "images": {"coverarthq": "https://img.test/cover.jpg"}}}
        provider = main.HybridProvider("token", {"shazam_enabled": True},
                                       lambda: used.append(True))
        with patch.dict(sys.modules, {"shazamio": self.fake_shazam_module(payload)}):
            track = provider.recognize("sample.wav", False)
        self.assertEqual(track.provider, "shazamio")
        self.assertEqual(track.artist, "George Thorogood")
        self.assertEqual(track.artwork_url, "https://img.test/cover.jpg")
        self.assertEqual(used, [])

    def test_shazam_no_match_falls_back_and_consumes_audd_quota(self):
        used = []
        provider = main.HybridProvider("token", {"shazam_enabled": True},
                                       lambda: (used.append(True) or (1, 1)))
        with patch.dict(sys.modules, {"shazamio": self.fake_shazam_module({"track": {}})}):
            with patch.object(main.AudDProvider, "recognize",
                              return_value=main.Track(artist="Artist", title="Title", provider="audd")):
                track = provider.recognize("sample.wav", False)
        self.assertEqual(track.provider, "audd")
        self.assertEqual(used, [True])
        self.assertTrue(provider.audd_request_sent)

    def test_shazam_disabled_uses_audd_directly(self):
        used = []
        provider = main.HybridProvider("token", {"shazam_enabled": False},
                                       lambda: (used.append(True) or (1, 1)))
        with patch.object(main.AudDProvider, "recognize",
                          return_value=main.Track(artist="Artist", title="Title", provider="audd")):
            track = provider.recognize("sample.wav", False)
        self.assertEqual(track.provider, "audd")
        self.assertEqual(used, [True])


if __name__ == "__main__":
    unittest.main()

