import os
import threading
import unittest
import wave
from manual_recognition import ManualRecognition


class Publisher:
    def __init__(self):
        self.status = []
        self.done = threading.Event()
    def publish_status(self, status, day, month, error=""):
        self.status.append((status, error))
        if status == "error":
            self.done.set()
    def publish_track(self, track, status, day, month):
        self.status.append((status, ""))
        self.done.set()


class Limiter:
    used = 0
    def counts(self):
        return self.used, self.used
    def consume(self):
        self.used += 1
        return self.counts()


class ManualTests(unittest.TestCase):
    def test_one_request_bounded_sample_and_cleanup(self):
        publisher, limiter = Publisher(), Limiter()
        paths = []
        class Provider:
            def recognize(self, path, is_url):
                paths.append(path)
                with wave.open(path, "rb") as sample:
                    assert sample.getnframes() == 16000
                    assert sample.getnchannels() == 2
                return type("Track", (), {"artist": "Test", "title": "Song"})()
        worker = ManualRecognition({"sample_seconds": 1}, publisher, limiter, lambda token: Provider())
        self.assertEqual(limiter.used, 0)
        self.assertTrue(worker.request())
        self.assertFalse(worker.request())
        worker.feed(bytes(128000))
        self.assertTrue(publisher.done.wait(3))
        for _ in range(100):
            if not worker.busy:
                break
            threading.Event().wait(0.01)
        self.assertEqual(limiter.used, 1)
        self.assertFalse(os.path.exists(paths[0]))
        self.assertEqual(len(worker.data), 0)

    def test_disconnect_does_not_call_provider(self):
        publisher, limiter = Publisher(), Limiter()
        worker = ManualRecognition({"sample_seconds": 1}, publisher, limiter,
                                   lambda token: self.fail("Provider must not be called"))
        worker.request()
        worker.feed(bytes(100))
        worker.disconnect()
        self.assertTrue(publisher.done.wait(3))
        self.assertEqual(limiter.used, 0)
        self.assertIn("disconnected", publisher.status[-1][1])

if __name__ == "__main__":
    unittest.main()
