"""Bounded live capture, playback sessions, and provider-independent scheduling."""
import math
import queue
import tempfile
import threading
import time
import wave
from datetime import datetime, timezone

from diagnostics import exception_details, log_event
from failed_samples import FailedSampleArchive


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
        self.capture_started_at = ""
        self.capture_levels = []
        self.waiting_for_capture_signal = False
        self.failed_sample_archive = FailedSampleArchive(
            keep=int(options.get("failed_sample_retention", 5))
        )
        self.last_failed_sample = None
        self.due = None
        self.identity = None
        self.failures = 0
        self.attempt_count = 0
        self.last_attempt_id = 0
        self.last_attempt_at = ""
        self.last_attempt_finished_at = ""
        self.last_attempt_outcome = "none"
        self.last_attempt_error = ""
        self.last_attempt_duration_seconds = None
        self.reason = "idle"
        self.retry = int(options.get("same_song_retry_seconds", 15))
        self.fallback = int(options.get("fallback_check_seconds", 60))
        self.song_end_buffer = int(options.get("song_end_buffer_seconds", 3))

    def status(self, status, error=""):
        details = {
            "attempt_count": self.attempt_count,
            "last_attempt_id": self.last_attempt_id or None,
            "last_attempt_at": self.last_attempt_at or None,
            "last_attempt_finished_at": self.last_attempt_finished_at or None,
            "last_attempt_outcome": self.last_attempt_outcome,
            "last_attempt_error": self.last_attempt_error,
            "last_attempt_duration_seconds": self.last_attempt_duration_seconds,
            "last_failed_sample": self.last_failed_sample,
            "consecutive_failures": self.failures,
            "retry_seconds": max(0, round(self.due - self.clock())) if self.due is not None else None,
            "check_reason": self.reason,
        }
        self.publisher.publish_status(status, *self.limiter.counts(), error, details=details)

    def start(self):
        log_event("monitor_started", input_mode="usb_auto",
                  start_threshold_dbfs=self.detector.start_db,
                  stop_threshold_dbfs=self.detector.stop_db,
                  start_hold_seconds=self.detector.start_seconds,
                  stop_hold_seconds=self.detector.stop_seconds,
                  sample_seconds=round(self.target / 64000, 2),
                  no_match_retry_base_seconds=int(self.options.get("no_match_retry_seconds", 30)))
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
            "song_end_buffer_seconds": self.song_end_buffer,
        }
        if attributes != self.last_session:
            self.publisher.set_state("playback_state", "playing" if self.detector.active else "idle", attributes)
            self.last_session = attributes

    def end(self):
        was_active = self.detector.active
        had_partial_capture = self.data is not None
        self.generation += 1
        self.data, self.due, self.identity = None, None, None
        self.capture_levels = []
        self.waiting_for_capture_signal = False
        self.failures = 0
        self.reason = "idle"
        self.publisher.clear_track()
        self.status("idle")
        if was_active or had_partial_capture:
            log_event("playback_session_ended", discarded_partial_capture=had_partial_capture)

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
            self.waiting_for_capture_signal = False
            log_event("playback_session_started", input_dbfs=round(rms, 1),
                      threshold_dbfs=self.detector.start_db,
                      sustained_seconds=self.detector.start_seconds)
            self.status("listening")
        self.drain_result(now)
        if (self.detector.active and self.detector.quiet and self.data is None
                and not self.busy and self.due is not None and now >= self.due):
            # The estimated song has ended and the input is quiet. End this
            # session immediately instead of spending a request on silence.
            # A new request now requires the normal start threshold again.
            self.detector.active = False
            self.detector.elapsed = 0.0
            log_event("song_end_check_quiet", input_dbfs=round(rms, 1),
                      stop_threshold_dbfs=self.detector.stop_db,
                      action="return_to_idle_without_a_request")
            self.end()
            self.reason = "waiting_for_audio"
            self.publish_session()
            return
        if self.detector.active and not self.detector.quiet:
            if self.data is None and not self.busy and self.due is not None and now >= self.due:
                # Keep capture start aligned with the playback start threshold.
                # The stop threshold is deliberately lower (hysteresis), so
                # using only `not quiet` here can start a sample on near-silence
                # while an active session is being held open for stop detection.
                if rms <= self.detector.start_db:
                    if not self.waiting_for_capture_signal:
                        log_event("capture_waiting_for_start_threshold", input_dbfs=round(rms, 1),
                                  required_threshold_dbfs=self.detector.start_db,
                                  check_reason=self.reason)
                        self.waiting_for_capture_signal = True
                else:
                    if self.waiting_for_capture_signal:
                        log_event("capture_signal_recovered", input_dbfs=round(rms, 1),
                                  required_threshold_dbfs=self.detector.start_db,
                                  action="begin_fresh_sample")
                    self.waiting_for_capture_signal = False
                    day, month = self.limiter.counts()
                    if day >= self.limiter.daily_limit or month >= self.limiter.monthly_limit:
                        self.due = now + 60
                        self.reason = "request_limit"
                        details = self.limiter.details()
                        if month >= self.limiter.monthly_limit:
                            message = f"AudD API limit reached; refreshes {details['cycle_end']}"
                            self.status("api_limit_reached", message)
                        else:
                            self.status("daily_limit_reached", "Daily safety limit reached")
                    else:
                        self.data = bytearray()
                        self.capture_start = now - len(pcm) / 64000
                        capture_wall_time = datetime.now(timezone.utc).timestamp() - len(pcm) / 64000
                        self.capture_started_at = datetime.fromtimestamp(
                            capture_wall_time, timezone.utc
                        ).isoformat()
                        self.capture_levels = []
                        self.due = None
                        self.reason = "capturing"
                        log_event("capture_started", attempt_id=self.attempt_count + 1,
                                  sample_seconds=round(self.target / 64000, 2),
                                  input_dbfs=round(rms, 1), start_threshold_dbfs=self.detector.start_db,
                                  trigger_reason=self.reason)
                        self.status("capturing")
            if self.data is not None:
                self.capture_levels.append(float(rms))
                self.data.extend(pcm[:self.target - len(self.data)])
                if len(self.data) == self.target:
                    sample = bytes(self.data)
                    self.data = None
                    self.busy = True
                    self.attempt_count += 1
                    self.last_attempt_id = self.attempt_count
                    self.last_attempt_at = self.capture_started_at
                    self.last_attempt_outcome = "in_progress"
                    self.last_attempt_error = ""
                    levels = self.capture_levels or [float(rms)]
                    capture_stats = {
                        "sample_seconds": round(len(sample) / 64000, 2),
                        "sample_bytes": len(sample),
                        "rms_min_dbfs": round(min(levels), 1),
                        "rms_max_dbfs": round(max(levels), 1),
                        "rms_mean_dbfs": round(sum(levels) / len(levels), 1),
                        "windows": len(levels),
                    }
                    self.capture_levels = []
                    self.reason = "recognizing"
                    log_event("capture_completed", attempt_id=self.last_attempt_id,
                              **capture_stats, result="queued_for_recognition")
                    self.status("recognizing")
                    threading.Thread(target=self.recognize,
                                     args=(sample, self.generation, self.capture_start, capture_stats),
                                     daemon=True).start()
        elif self.data is not None:
            # Restart a full contiguous sample after a quiet passage.
            log_event("capture_cancelled_quiet_passage", captured_bytes=len(self.data),
                      target_bytes=self.target, input_dbfs=round(rms, 1),
                      action="discard_partial_sample_and_restart")
            self.data = None
            self.capture_levels = []
            self.due = now
            self.waiting_for_capture_signal = True
            log_event("capture_waiting_for_start_threshold", input_dbfs=round(rms, 1),
                      required_threshold_dbfs=self.detector.start_db,
                      action="wait_for_clear_audio_before_restarting_sample")
        self.publish_session()

    def recognize(self, pcm, generation, started, capture_stats=None):
        track, error = None, ""
        request_started = time.monotonic()
        request_sent = False
        log_event("recognition_attempt_started", attempt_id=self.last_attempt_id,
                  provider="audd", captured_bytes=len(pcm),
                  sample_seconds=round(len(pcm) / 64000, 2))
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
                request_sent = True
                log_event("audd_request_sent", attempt_id=self.last_attempt_id,
                          requests_today=self.limiter.counts()[0],
                          requests_this_cycle=self.limiter.counts()[1])
                track = provider.recognize(path, False)
                log_event("provider_pipeline_completed", attempt_id=self.last_attempt_id,
                          processing_seconds=round(time.monotonic() - request_started, 3),
                          recognized_artist=getattr(track, "artist", ""),
                          recognized_title=getattr(track, "title", ""),
                          provider=getattr(track, "provider", "audd"))
        except Exception as exc:
            error = str(exc)
            log_event("recognition_attempt_failed", level="ERROR", attempt_id=self.last_attempt_id,
                      request_sent=request_sent,
                      latency_seconds=round(time.monotonic() - request_started, 3),
                      **exception_details(exc, secret=str(self.options.get("audd_api_token", ""))))
        self.last_attempt_duration_seconds = round(time.monotonic() - started, 3)
        self.last_attempt_finished_at = datetime.now(timezone.utc).isoformat()
        secret = str(self.options.get("audd_api_token", ""))
        if secret:
            error = error.replace(secret, "[redacted]")
        if request_sent and error:
            try:
                archived = self.failed_sample_archive.save(
                    pcm, self.last_attempt_id, error, capture_stats
                )
                self.last_failed_sample = archived
                if archived:
                    log_event("failed_sample_archived", attempt_id=self.last_attempt_id,
                              outcome="no_match" if "No song was recognized" in error else "error",
                              filename=archived["filename"],
                              media_content_id=archived["media_content_id"],
                              retained_limit=self.failed_sample_archive.keep)
            except Exception as archive_error:
                log_event("failed_sample_archive_failed", level="ERROR",
                          attempt_id=self.last_attempt_id,
                          **exception_details(archive_error, secret=secret))
        self.results.put((generation, started, track, error))

    def drain_result(self, now):
        try:
            generation, started, track, error = self.results.get_nowait()
        except queue.Empty:
            return
        self.busy = False
        if generation != self.generation or not self.detector.active:
            log_event("recognition_result_discarded", level="WARNING",
                      attempt_id=self.last_attempt_id, stale_session=True,
                      playback_active=self.detector.active,
                      result="error" if error else "recognized")
            return
        if error:
            self.failures += 1
            delay = min(300, int(self.options.get("no_match_retry_seconds", 30)) * 2 ** min(self.failures - 1, 4))
            self.due = now + delay
            self.reason = "retry_after_no_match" if "No song was recognized" in error else "retry_after_error"
            if "AudD API limit reached" in error:
                status = "api_limit_reached"
            elif "No song was recognized" in error:
                status = "no_match"
            else:
                status = "error"
            self.last_attempt_outcome = "no_match" if status == "no_match" else "error"
            self.last_attempt_error = error
            retry_at = datetime.fromtimestamp(self.wall_offset + self.due, timezone.utc).isoformat()
            log_event("recognition_retry_scheduled", level="WARNING" if status == "no_match" else "ERROR",
                      attempt_id=self.last_attempt_id, outcome=self.last_attempt_outcome,
                      failure_number=self.failures, error=error,
                      retry_in_seconds=delay, retry_at=retry_at,
                      explanation=("AudD returned no recognized track; it does not provide alternate candidate matches"
                                   if status == "no_match" else "Recognition request failed; inspect error_type, HTTP status and response details"))
            self.status(status, error)
            return
        self.failures = 0
        self.last_attempt_outcome = "recognized"
        self.last_attempt_error = ""
        identity = tuple(" ".join(value.casefold().split()) for value in (track.artist, track.title))
        if identity == self.identity:
            self.due = now + self.retry
            self.reason = "same_song_retry"
        elif track.duration_seconds is not None and track.position_seconds is not None:
            remaining = track.duration_seconds - track.position_seconds
            self.due = now + max(self.retry, remaining + self.song_end_buffer)
            self.reason = "estimated_song_end"
        else:
            self.due = now + self.fallback
            self.reason = "missing_timing_fallback"
        self.identity = identity
        retry_at = datetime.fromtimestamp(self.wall_offset + self.due, timezone.utc).isoformat()
        log_event("recognition_succeeded", attempt_id=self.last_attempt_id,
                  artist=getattr(track, "artist", ""), title=getattr(track, "title", ""),
                  album=getattr(track, "album", ""), provider=getattr(track, "provider", "audd"),
                  discogs_release_id=getattr(track, "discogs_release_id", ""),
                  selection_reason=getattr(track, "selection_reason", ""),
                  timing_source=getattr(track, "timing_source", ""),
                  duration_seconds=getattr(track, "duration_seconds", None),
                  position_seconds=getattr(track, "position_seconds", None),
                  schedule_reason=self.reason, next_check_at=retry_at,
                  next_check_in_seconds=round(self.due - now))
        diagnostics = {
            "attempt_count": self.attempt_count,
            "last_attempt_id": self.last_attempt_id,
            "last_attempt_at": self.last_attempt_at,
            "last_attempt_finished_at": self.last_attempt_finished_at,
            "last_attempt_outcome": self.last_attempt_outcome,
            "last_attempt_error": "",
            "last_attempt_duration_seconds": self.last_attempt_duration_seconds,
            "consecutive_failures": 0,
            "retry_seconds": max(0, round(self.due - now)),
            "check_reason": self.reason,
            "next_check_at": retry_at,
        }
        self.publisher.publish_track(track, "recognized", *self.limiter.counts(), diagnostics=diagnostics)

