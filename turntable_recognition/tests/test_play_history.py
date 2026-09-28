import json
import tempfile
import unittest
from pathlib import Path

from play_history import PlayHistory


def track(title, **attrs):
    return {"artist": "Aretha Franklin", "title": title, "album": "Spirit in the Dark", **attrs}


class PlayHistoryTests(unittest.TestCase):
    def test_rolls_current_and_previous_two_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            history = PlayHistory(path)
            history.record(track("One", artwork_url="cover-one"), "session-1")
            history.record(track("Two", artwork_url="cover-two"), "session-2")
            entries = history.record(track("Three", artwork_url="cover-three"), "session-3")
            self.assertEqual([item["title"] for item in entries], ["Three", "Two", "One"])
            self.assertEqual(entries[1]["artwork_url"], "cover-two")
            entries = history.record(track("Four"), "session-4")
            self.assertEqual([item["title"] for item in entries], ["Four", "Three", "Two"])
            restored = PlayHistory(path)
            self.assertEqual([item["title"] for item in restored.entries], ["Four", "Three", "Two"])
            self.assertTrue(restored.entries[0]["played_at"])

    def test_does_not_count_repeated_poll_for_same_track_in_session(self):
        with tempfile.TemporaryDirectory() as directory:
            history = PlayHistory(Path(directory) / "history.json")
            first = history.record(track("One"), "session-1")
            second = history.record(track("One", timecode="02:00"), "session-1")
            self.assertEqual(len(second), 1)
            self.assertEqual(first[0]["played_at"], second[0]["played_at"])

    def test_same_track_in_a_new_session_counts_as_a_new_play(self):
        with tempfile.TemporaryDirectory() as directory:
            history = PlayHistory(Path(directory) / "history.json")
            history.record(track("One"), "session-1")
            entries = history.record(track("One"), "session-2")
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["play_session_id"], "session-2")
            self.assertEqual(entries[1]["play_session_id"], "session-1")


if __name__ == "__main__":
    unittest.main()

