import os
import queue
import unittest
import wave
from types import SimpleNamespace
from auto_recognition import AutomaticRecognition, SessionDetector, timing


class Publisher:
    def __init__(self):
        self.tracks, self.states, self.statuses = [], {}, []
        self.cleared = 0
    def clear_track(self): self.cleared += 1
    def set_state(self, suffix, state, attrs): self.states[suffix] = (state, attrs)
    def publish_status(self, status, *args): self.statuses.append(status)
    def publish_track(self, track, *args): self.tracks.append(track)


class Limiter:
    daily_limit, monthly_limit, used = 100, 1000, 0
    def counts(self): return self.used, self.used
    def consume(self):
        self.used += 1
        return self.counts()


def track(title="First", duration=240, position=60):
    return SimpleNamespace(artist="Artist", title=title, duration_seconds=duration, position_seconds=position)


class AutoTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.publisher, self.limiter = Publisher(), Limiter()
        self.worker = AutomaticRecognition({}, self.publisher, self.limiter, lambda token: None, lambda: self.now)

    def result(self, value, error="", generation=None):
        w = self.worker
        w.detector.active = True
        w.results.put((w.generation if generation is None else generation, 80, value, error))
        w.drain_result(self.now)

    def test_continuous_start_stop_and_hysteresis(self):
        d = SessionDetector({})
        self.assertIsNone(d.update(-20, 1))
        d.update(-40, 1)
        self.assertIsNone(d.update(-20, 1))
        self.assertEqual(d.update(-20, 1), "start")
        for _ in range(20): self.assertIsNone(d.update(-32, 1))
        for _ in range(14): self.assertIsNone(d.update(-40, 1))
        self.assertEqual(d.update(-40, 1), "stop")

    def test_idle_never_captures_or_calls(self):
        for _ in range(100): self.worker.feed(bytes(64000), -80)
        self.assertIsNone(self.worker.data)
        self.assertFalse(self.worker.busy)
        self.assertEqual(self.limiter.used, 0)

    def test_new_same_and_new_again_schedule(self):
        self.result(track())
        self.assertEqual(self.worker.due, 263)
        self.now = 265
        self.result(track())
        self.assertEqual(self.worker.due, 280)
        self.result(track("Second", 400, 10))
        self.assertEqual(self.worker.due, 473)

    def test_missing_metadata_and_bad_timing(self):
        self.result(track(duration=None, position=None))
        self.assertEqual(self.worker.due, 160)
        self.assertEqual(timing(240000, "01:30"), (240, 90))
        for duration, position in [(None, "1:00"), (10, "bad"), (10, "1:00"), (float('nan'), "0")]:
            self.assertEqual(timing(duration, position), (None, None))

    def test_error_backoff_bounded(self):
        for expected in (30, 60, 120, 240, 300, 300):
            self.result(None, "No song was recognized")
            self.assertEqual(self.worker.due, self.now + expected)

    def test_session_end_discards_late_response(self):
        old = self.worker.generation
        self.worker.end()
        self.result(track(), generation=old)
        self.assertFalse(self.publisher.tracks)
        self.assertIsNone(self.worker.due)

    def test_quiet_cancels_partial_capture_and_stop_clears(self):
        self.worker.feed(bytes(64000), -20)
        self.worker.feed(bytes(64000), -20)
        self.assertEqual(len(self.worker.data), 64000)
        self.worker.feed(bytes(64000), -40)
        self.assertIsNone(self.worker.data)
        for _ in range(14): self.worker.feed(bytes(64000), -40)
        self.assertFalse(self.worker.detector.active)
        self.assertEqual(self.publisher.cleared, 1)
        self.assertIsNone(self.worker.due)

    def test_quota_stops_capture(self):
        self.limiter.used = 100
        self.worker.feed(bytes(64000), -20)
        self.worker.feed(bytes(64000), -20)
        self.assertIsNone(self.worker.data)
        self.assertEqual(self.worker.reason, "request_limit")

    def test_worker_wav_cleanup_and_bounded_result(self):
        paths = []
        class Provider:
            def recognize(self, path, is_url):
                paths.append(path)
                with wave.open(path) as audio:
                    assert audio.getnframes() == 16000
                    assert audio.getnchannels() == 2
                return track()
        self.worker.provider_factory = lambda token: Provider()
        self.worker.recognize(bytes(64000), 0, 80)
        self.assertEqual(self.limiter.used, 1)
        self.assertEqual(self.worker.results.qsize(), 1)
        self.assertFalse(os.path.exists(paths[0]))


if __name__ == '__main__': unittest.main()
