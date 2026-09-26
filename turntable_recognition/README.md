# Turntable Recognition

Recognizes music and publishes structured now-playing data to Home Assistant.

Version 0.3.0 supports:

- Live USB input monitoring from a UFO202 USB Audio CODEC, with RMS and peak dBFS sensors, a configurable signal threshold, and automatic reconnection.
- A Home Assistant dashboard graph and live readings. Use `input_mode: usb_meter` and `audio_source: auto`; this mode processes audio locally and makes no recognition API requests.
- Mock metadata for dashboard and Tidbyt development.
- AudD recognition from a public audio URL or a file in Home Assistant's Media directory.
- Simulated USB capture that uses FFmpeg to cut a Media file into a short WAV sample.
- Daily and monthly recognition request limits.
- A provider interface that allows another provider to be added later.

See the Documentation tab for USB meter options and `examples/usb-audio-dashboard.yaml` in the repository for a dashboard card.

Use LINE on the UFO202 when its input comes from an external phono preamp. dBFS measures the captured signal, not room sound pressure or Sonos volume.

Automatic recognition from live USB and continuous track-change detection remain future work.
