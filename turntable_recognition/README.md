# Turntable Recognition

Recognizes music and publishes structured now-playing data to Home Assistant.

Version 0.3.1 supports:

- Live UFO202 USB Audio CODEC monitoring with average and peak dBFS sensors and automatic input reconnection.
- Manual live USB recognition: send `{"command":"recognize"}` through Home Assistant app stdin. Each accepted command captures the next short sample and makes one AudD request. Overlapping commands are ignored and temporary samples are removed.
- Artist, song, album, year, artwork, recognition status, and request-count entities for dashboards and Tidbyt.
- Mock metadata, public audio URL recognition, Media-file recognition, and simulated USB samples from Media files.
- Daily and monthly request limits.

Use `input_mode: usb_meter` and `audio_source: auto` for live input. Monitoring alone makes no AudD requests. Automatic recognition and retry scheduling are not enabled.

See the Documentation tab for the Recognize now button and options. `examples/usb-audio-dashboard.yaml` contains a meter and graph card.

Use LINE on the UFO202 when feeding it from an external phono preamp. dBFS measures the captured signal, not room loudness or Sonos volume. The graph displays 15 minutes while detailed numeric history follows Home Assistant Recorder settings.

Automatic playback detection, track-change scheduling, and continuous Tidbyt takeover are future work.
