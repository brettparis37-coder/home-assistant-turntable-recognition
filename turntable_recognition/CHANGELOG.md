# 0.4.0

- Add usb_auto playback sessions with configurable start/stop thresholds and hold times.
- Recognize automatically, estimate the next check from song duration and match position, and retry same-song matches after a configurable delay.
- Clear now-playing metadata on quiet input or USB disconnect; ignore stale responses from ended sessions.
- Bound capture memory, prevent overlapping requests, back off failures, and honor daily/monthly limits.
- Publish playback state and next recognition time for dashboards. No Tidbyt changes.

# 0.3.1

- Add manual recognition from live USB with a bounded sample and temporary WAV cleanup.
- Accept one recognize command through Home Assistant app stdin; prevent overlapping requests.
- Keep the meter running during recognition; no automatic recognition or retries.

# 0.3.0

- Add local live USB audio meter with RMS, peak, signal threshold, and input status.
- Select UFO202 through Home Assistant PulseAudio by device identity.
- Retry disconnected input automatically and mark stale levels unavailable.
- Add a dashboard graph example; USB meter mode does not call AudD.

# 0.2.0

- Add simulated USB capture from a Media file with FFmpeg.
