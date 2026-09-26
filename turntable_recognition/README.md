# Turntable Recognition

Version 0.4.0 supports automatic recognition from live USB audio.

Set `input_mode: usb_auto` and `audio_source: auto`, save and restart. Keep your existing AudD token and request limits.

- Local RMS and peak audio monitoring with automatic USB reconnection.
- Playback starts above -30 dBFS for 2 seconds and ends below -35 dBFS for 15 seconds (configurable).
- Initial recognition captures a short sample. New matches schedule the next check near estimated song completion using duration and match position.
- Same-song matches retry after 15 seconds; missing timing falls back to 60 seconds. No-match/error retries back off from 30 to 300 seconds.
- Idle sessions clear now-playing metadata. Late responses cannot revive ended sessions.
- Bounded audio samples, one request at a time, temporary-file cleanup, and daily/monthly request limits.
- Artist, title, album, year, artwork, playback state, and next-check time for dashboards.

See Documentation for options. Legacy manual USB, mock, URL, file, and simulated USB modes remain available. Automatic Tidbyt takeover is a separate future step.

Use LINE on the UFO202 when feeding it from an external phono preamp. dBFS measures the captured signal, not room loudness or Sonos volume. A 15-minute graph window does not change Home Assistant Recorder retention.
