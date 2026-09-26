"""Bounded live capture, playback sessions, and provider-independent scheduling."""
import math
import queue
import tempfile
import threading
import time
import wave
from datetime import datetime, timezone


def timing(duration_ms, timecode):
    try:
        duration = float(duration_ms) / 1000
        parts = str(timecode).split(":")
        position = 0.0
        for part in parts:
            position = position * 60 + float(part)
        if not all(math.isfinite(v) for v in (duration, position)):
            return None, None
        if not 0 <= position < duration <= 7200:
            return None, None
        return duration, position
    except (ValueError, TypeError):
        return None, None


class SessionDetector:
    def __init__(self, options):
        self.start_db = float(options.get("playback_start_dbfs", -30))
        self.stop_db = float(options.get("playback_stop_dbfs", -35))
        if self.start_db <= self.stop_db:
            raise ValueError("playback_start_dbfs must be higher than playback_stop_dbfs")
        self.start_seconds = float(options.get("playback_start_seconds", 2))
        self.stop_seconds = float(options.get("playback_stop_seconds", 15))
        self.active = False
        self.elapsed = 0.0
        self.quiet = False

    def update(self, db, seconds):
        self.quiet = db < self.stop_db
        qualifies = self.quiet if self.active else db > self.start_db
        self.elapsed = self.elapsed + seconds if qualifies else 0.0
        threshold = self.stop_seconds if self.active else self.start_seconds
        if self.elapsed >= threshold:
            self.active = not self.active
            self.elapsed = 0.0
            return "start" if self.active else "stop"
        return None


class AutomaticRecognition:
    def __init__(self, options, publisher, limiter, provider_factory, clock=time.monotonic):
        self.options, self.publisher, self.limiter = options, publisher, limiter
        self.provider_factory, self.clock = provider_factory, clock
        self.wall_offset = time.time() - clock()
        self.last_session = None
        self.detector = SessionDetector(options)
        self.generation = 0
        self.results = queue.Queue(maxsize=1)
        self.busy = False
        self.data = None
        self.target = int(options.get("sample_seconds", 12)) * 64000
        self.capture_start = 0
        self.due = None
        self.identity = None
        self.failures = 0
        self.reason = "idle"
        self.retry = int(options.get("same_song_retry_seconds", 15))
        self.fallback = int(options.get("fallback_check_seconds", 60))

    def status(self, status, error=""):
        self.publisher.publish_status(status, *self.limiter.counts(), error)

    def start(self):
        self.publisher.clear_track()
        self.status("idle")
        self.publish_session()

    def publish_session(self):
        attributes = {
            "friendly_name": "Turntable Playback", "icon": "mdi:record-player",
            "active": self.detector.active, "quiet": self.detector.quiet,
            "next_check_at": datetime.fromtimestamp(self.wall_offset + self.due, timezone.utc).isoformat() if self.due is not None else None,
            "check_reason": self.reason, "request_active": self.busy,
            "start_threshold_dbfs": self.detector.start_db,
            "stop_threshold_dbfs": self.detector.stop_db,
            "same_song_retry_seconds": self.retry,
        }
        if attributes != self.last_session:
            self.publisher.set_state("playback_state", "playing" if self.detector.active else "idle", attributes)
            self.last_session = attributes

    def end(self):
        self.generation += 1
        self.data, self.due, self.identity = None, None, None
        self.failures = 0
        self.reason = "idle"
        self.publisher.clear_track()
        self.status("idle")

    def disconnect(self):
        self.detector.active = False
        self.detector.elapsed = 0
        self.end()
        self.reason = "input_disconnected"
        self.status("input_unavailable")
        self.publish_session()

    def feed(self, pcm, rms):
        now = self.clock()
        transition = self.detector.update(rms, len(pcm) / 64000)
        if transition == "stop":
            self.end()
        elif transition == "start":
            self.generation += 1
            self.due = now
            self.reason = "new_session"
            self.status("listening")
        self.drain_result(now)
        if self.detector.active and not self.detector.quiet:
            if self.data is None and not self.busy and self.due is not None and now >= self.due:
                day, month = self.limiter.counts()
                if day >= self.limiter.daily_limit or month >= self.limiter.monthly_limit:
                    self.due = now + 60
                    self.reason = "request_limit"
                    self.status("request_limit")
                else:
                    self.data = bytearray()
                    self.capture_start = now - len(pcm) / 64000
                    self.due = None
                    self.reason = "capturing"
                    self.status("capturing")
            if self.data is not None:
                self.data.extend(pcm[:self.target - len(self.data)])
                if len(self.data) == self.target:
                    sample = bytes(self.data)
                    self.data = None
                    self.busy = True
                    self.reason = "recognizing"
                    self.status("recognizing")
                    threading.Thread(target=self.recognize, args=(sample, self.generation, self.capture_start), daemon=True).start()
        elif self.data is not None:
            # Restart a full contiguous sample after a quiet passage.
            self.data = None
            self.due = now
        self.publish_session()

    def recognize(self, pcm, generation, started):
        track, error = None, ""
        try:
            provider = self.provider_factory(str(self.options.get("audd_api_token", "")))
            with tempfile.TemporaryDirectory(prefix="turntable-auto-") as directory:
                path = directory + "/sample.wav"
                with wave.open(path, "wb") as output:
                    output.setnchannels(2)
                    output.setsampwidth(2)
                    output.setframerate(16000)
                    output.writeframes(pcm)
                self.limiter.consume()
                track = provider.recognize(path, False)
        except Exception as exc:
            error = str(exc)
        self.results.put((generation, started, track, error))

    def drain_result(self, now):
        try:
            generation, started, track, error = self.results.get_nowait()
        except queue.Empty:
            return
        self.busy = False
        if generation != self.generation or not self.detector.active:
            return
        if error:
            self.failures += 1
            delay = min(300, int(self.options.get("no_match_retry_seconds", 30)) * 2 ** min(self.failures - 1, 4))
            self.due = now + delay
            self.reason = "retry_after_no_match" if "No song was recognized" in error else "retry_after_error"
            self.status("no_match" if "No song was recognized" in error else "error", error)
            return
        self.failures = 0
        identity = tuple(" ".join(value.casefold().split()) for value in (track.artist, track.title))
        if identity == self.identity:
            self.due = now + self.retry
            self.reason = "same_song_retry"
        elif track.duration_seconds is not None and track.position_seconds is not None:
            self.due = max(now + self.retry, started + track.duration_seconds - track.position_seconds + 3)
            self.reason = "estimated_song_end"
        else:
            self.due = now + self.fallback
            self.reason = "missing_timing_fallback"
        self.identity = identity
        self.publisher.publish_track(track, "recognized", *self.limiter.counts())
        print(f"Automatic recognition: {track.artist} - {track.title}; {self.reason}; next check in {round(self.due - now)}s", flush=True)
