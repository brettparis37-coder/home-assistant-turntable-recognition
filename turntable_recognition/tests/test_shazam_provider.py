import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

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
    def fake_shazam_module(self, payload, legacy_payload=None):
        module = ModuleType("shazamio")
        module.calls = []

        class Shazam:
            async def recognize(self, source):
                module.calls.append(("rust", source))
                return payload

            async def recognize_song(self, audio):
                module.calls.append(("legacy", audio))
                return legacy_payload if legacy_payload is not None else {"track": {}}

        module.Shazam = Shazam
        return module

    @staticmethod
    def fake_pydub_module():
        module = ModuleType("pydub")

        class AudioSegment:
            @staticmethod
            def from_file(source):
                return {"decoded_source": source}

        module.AudioSegment = AudioSegment
        return module

    def test_shazam_match_skips_audd_and_maps_cover(self):
        used = []
        payload = {"track": {"title": "The Sky Is Crying", "subtitle": "George Thorogood",
                             "images": {"coverarthq": "https://img.test/cover.jpg"}}}
        provider = main.HybridProvider("token", {"shazam_enabled": True},
                                       lambda: used.append(True))
        fake = self.fake_shazam_module(payload)
        with patch.dict(sys.modules, {"shazamio": fake}):
            track = provider.recognize("sample.wav", False)
        self.assertEqual(track.provider, "shazamio")
        self.assertEqual(track.artist, "George Thorogood")
        self.assertEqual(track.artwork_url, "https://img.test/cover.jpg")
        self.assertEqual(used, [])
        self.assertEqual([call[0] for call in fake.calls], ["rust"])

    def test_legacy_shazam_match_enriches_discogs_and_skips_audd(self):
        used = []
        legacy_payload = {"track": {"title": "That Same Thing",
                                     "subtitle": "George Thorogood & The Destroyers"}}
        provider = main.HybridProvider("token", {"shazam_enabled": True, "discogs_enabled": True},
                                       lambda: used.append(True))
        provider._enrich_discogs = Mock()
        fake = self.fake_shazam_module({"matches": []}, legacy_payload)
        with patch.dict(sys.modules, {"shazamio": fake, "pydub": self.fake_pydub_module()}):
            track = provider.recognize("sample.wav", False)
        self.assertEqual(track.provider, "shazamio")
        self.assertEqual(track.title, "That Same Thing")
        self.assertEqual(track.artist, "George Thorogood & The Destroyers")
        self.assertEqual([call[0] for call in fake.calls], ["rust", "legacy"])
        provider._enrich_discogs.assert_called_once_with(track)
        self.assertEqual(used, [])

    def test_shazam_no_match_falls_back_and_consumes_audd_quota(self):
        used = []
        provider = main.HybridProvider("token", {"shazam_enabled": True},
                                       lambda: (used.append(True) or (1, 1)))
        fake = self.fake_shazam_module({"track": {}})
        with patch.dict(sys.modules, {"shazamio": fake, "pydub": self.fake_pydub_module()}):
            with patch.object(main.AudDProvider, "recognize",
                              return_value=main.Track(artist="Artist", title="Title", provider="audd")):
                track = provider.recognize("sample.wav", False)
        self.assertEqual(track.provider, "audd")
        self.assertEqual(used, [True])
        self.assertTrue(provider.audd_request_sent)
        self.assertEqual([call[0] for call in fake.calls], ["rust", "legacy"])

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

