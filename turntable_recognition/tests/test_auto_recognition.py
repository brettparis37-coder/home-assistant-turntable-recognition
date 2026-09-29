import os
import queue
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from auto_recognition import AutomaticRecognition, SessionDetector, timing


class Publisher:
    def __init__(self):
        self.tracks, self.states, self.statuses, self.plays = [], {}, [], []
        self.status_details = []
        self.cleared = 0
        self.predicted_current, self.predicted_next = [], []
    def clear_track(self): self.cleared += 1
    def set_state(self, suffix, state, attrs): self.states[suffix] = (state, attrs)
    def publish_status(self, status, *args, details=None):
        self.statuses.append(status)
        self.status_details.append(details or {})
    def publish_track(self, track, *args, diagnostics=None): self.tracks.append(track)
    def record_play(self, track, session_id): self.plays.append((track, session_id))
    def publish_prediction(self, current, following=None, diagnostics=None):
        self.predicted_current.append((current, following, diagnostics))
    def publish_predicted_next(self, following): self.predicted_next.append(following)


class Limiter:
    daily_limit, monthly_limit, used = 100, 1000, 0
    def counts(self): return self.used, self.used
    def consume(self):
        self.used += 1
        return self.counts()
    def details(self):
        return {"cycle_end": "2026-10-25"}


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
        self.assertEqual(self.worker.due, 283)
        self.now = 265
        self.result(track())
        self.assertEqual(self.worker.due, 280)
        self.result(track("Second", 400, 10))
        self.assertEqual(self.worker.due, 658)

    def test_history_records_track_once_per_session(self):
        self.worker.session_id = "session-1"
        self.result(track())
        self.result(track())
        self.assertEqual(len(self.publisher.plays), 1)
        self.assertEqual(self.publisher.plays[0][1], "session-1")

    def test_quiet_at_estimated_end_returns_to_idle_without_request(self):
        self.worker.detector.active = True
        self.worker.detector.quiet = True
        self.worker.due = self.now
        self.worker.feed(bytes(64000), -40)
        self.assertFalse(self.worker.detector.active)
        self.assertEqual(self.worker.reason, "waiting_for_audio")
        self.assertEqual(self.limiter.used, 0)
        self.assertIsNone(self.worker.due)

    def test_missing_metadata_and_bad_timing(self):
        self.result(track(duration=None, position=None))
        self.assertEqual(self.worker.due, 160)
        self.assertEqual(timing(240000, "01:30"), (240, 90))
        for duration, position in [(None, "1:00"), (10, "bad"), (10, "1:00"), (float('nan'), "0")]:
            self.assertEqual(timing(duration, position), (None, None))

    def test_track_position_estimate_advances_to_estimated_song_end(self):
        first = track(duration=240, position=None)
        first.sample_seconds = 15
        self.result(first)
        self.assertEqual(first.position_seconds, 15)
        self.assertEqual(self.worker.reason, "estimated_song_end")
        self.assertEqual(self.worker.due, self.now + 228)
        self.now += 30
        second = track(duration=240, position=None)
        second.sample_seconds = 15
        self.result(second)
        self.assertEqual(second.position_seconds, 45)
        self.assertEqual(self.worker.reason, "same_song_retry")

    def test_failed_recognition_advances_through_discogs_prediction_then_uses_backoff(self):
        self.worker.options["discogs_enabled"] = True
        second = {"artist": "Artist", "title": "Second", "album": "Album",
                  "discogs_release_id": "10", "discogs_track_sequence": 2,
                  "duration_seconds": 200, "position_seconds": 0}
        third = {**second, "title": "Third", "discogs_track_sequence": 3,
                 "duration_seconds": 210}

        class Matcher:
            def next_track(self, release_id, sequence):
                return {"track_title": "Second", "release_id": 10, "sequence": 2,
                        "duration_ms": 200000, "album_artists": "Artist", "album": "Album"} if sequence == 1 else (
                    {"track_title": "Third", "release_id": 10, "sequence": 3,
                     "duration_ms": 210000, "album_artists": "Artist", "album": "Album"}
                    if sequence == 2 else None)
            def average_duration_seconds(self, release_id): return 200

        self.worker.discogs_matcher = Matcher()
        confirmed = track(duration=240, position=220)
        confirmed.discogs_release_id = "10"
        confirmed.discogs_track_sequence = 1
        self.result(confirmed)
        self.assertEqual(self.worker.predicted_next["title"], "Second")

        self.now = self.worker.due
        self.result(None, "No song was recognized")
        self.assertEqual(self.publisher.predicted_current[-1][0]["title"], "Second")
        self.assertEqual(self.worker.predicted_next["title"], "Third")
        self.assertEqual(self.worker.reason, "predicted_song_end")
        self.assertEqual(self.worker.due, self.now + 188)

        self.now = self.worker.due
        self.result(None, "No song was recognized")
        self.assertEqual(self.publisher.predicted_current[-1][0]["title"], "Third")
        self.assertIsNone(self.worker.predicted_next)
        self.assertEqual(self.worker.due, self.now + 198)

        self.now = self.worker.due
        self.result(None, "No song was recognized")
        self.assertEqual(self.worker.reason, "retry_after_no_match")
        self.assertEqual(self.worker.due, self.now + 120)

    def test_error_backoff_bounded(self):
        for expected in (30, 60, 120, 240, 300, 300):
            self.result(None, "No song was recognized")
            self.assertEqual(self.worker.due, self.now + expected)
        self.assertEqual(self.worker.last_attempt_outcome, "no_match")
        self.assertEqual(self.worker.last_attempt_error, "No song was recognized")
        self.assertEqual(self.publisher.status_details[-1]["retry_seconds"], 300)

    def test_status_includes_last_attempt_diagnostics(self):
        self.worker.attempt_count = 3
        self.worker.last_attempt_id = 3
        self.worker.last_attempt_at = "2026-09-27T21:00:00+00:00"
        self.worker.last_attempt_outcome = "no_match"
        self.worker.last_attempt_error = "No song was recognized"
        self.worker.failures = 2
        self.worker.due = self.now + 60
        self.worker.status("no_match", self.worker.last_attempt_error)
        details = self.publisher.status_details[-1]
        self.assertEqual(details["last_attempt_id"], 3)
        self.assertEqual(details["last_attempt_outcome"], "no_match")
        self.assertEqual(details["consecutive_failures"], 2)
        self.assertEqual(details["retry_seconds"], 60)

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

    def test_partial_capture_waits_for_start_threshold_before_restarting(self):
        self.worker.feed(bytes(64000), -20)
        self.worker.feed(bytes(64000), -20)
        self.assertEqual(len(self.worker.data), 64000)

        # A brief quiet passage discards the partial sample. Hysteresis keeps
        # playback active at -35 to -30 dBFS, but those levels must not restart
        # a recognition sample until clear audio crosses the start threshold.
        self.worker.feed(bytes(64000), -40)
        self.assertIsNone(self.worker.data)
        for level in (-35.0, -34.0, -32.0, -30.0):
            self.worker.feed(bytes(64000), level)
            self.assertIsNone(self.worker.data)

        self.worker.feed(bytes(64000), -29.0)
        self.assertIsNotNone(self.worker.data)
        self.assertEqual(len(self.worker.data), 64000)

    def test_quota_stops_capture(self):
        self.worker.options["shazam_enabled"] = False
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
        self.assertEqual(self.limiter.used, 0)
        self.assertEqual(self.worker.results.qsize(), 1)
        self.assertFalse(os.path.exists(paths[0]))

    def test_failed_request_is_archived_but_success_is_not(self):
        from failed_samples import FailedSampleArchive

        with tempfile.TemporaryDirectory() as directory:
            self.worker.failed_sample_archive = FailedSampleArchive(directory, keep=5)

            class NoMatchProvider:
                def recognize(self, path, is_url):
                    raise RuntimeError("No song was recognized")

            self.worker.provider_factory = lambda token: NoMatchProvider()
            self.worker.recognize(bytes(64000), 0, 80,
                                  {"sample_seconds": 1, "rms_mean_dbfs": -20})
            samples = list(Path(directory).glob("*.wav"))
            self.assertEqual(len(samples), 1)
            self.assertIsNotNone(self.worker.last_failed_sample)
            self.assertEqual(self.worker.last_failed_sample["filename"], samples[0].name)


if __name__ == '__main__': unittest.main()

