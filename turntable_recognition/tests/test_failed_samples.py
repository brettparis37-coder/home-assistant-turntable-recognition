import json
import tempfile
import unittest
import wave
from pathlib import Path

from failed_samples import FailedSampleArchive


class FailedSampleArchiveTests(unittest.TestCase):
    def test_keeps_newest_five_wavs_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = FailedSampleArchive(directory, keep=5)
            results = [archive.save(bytes(64000), index, "No song was recognized")
                       for index in range(1, 7)]
            wavs = sorted(Path(directory).glob("failed_*.wav"))
            sidecars = sorted(Path(directory).glob("failed_*.json"))
            self.assertEqual(len(wavs), 5)
            self.assertEqual(len(sidecars), 5)
            self.assertFalse(Path(results[0]["path"]).exists())
            self.assertTrue(Path(results[-1]["path"]).exists())
            with wave.open(str(wavs[-1]), "rb") as audio:
                self.assertEqual(audio.getframerate(), 16000)
                self.assertEqual(audio.getnchannels(), 2)
                self.assertEqual(audio.getsampwidth(), 2)
            metadata = json.loads(wavs[-1].with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["outcome"], "no-match")
            self.assertEqual(metadata["attempt_id"], 6)
            self.assertEqual(metadata["sample_seconds"], 1.0)

    def test_zero_retention_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = FailedSampleArchive(directory, keep=0)
            self.assertIsNone(archive.save(bytes(64000), 1, "No song was recognized"))
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()

