# USB audio meter (0.3.0)

Use this mode to test the UFO202 line input locally before enabling recognition.
Set the UFO202 to LINE when feeding it from a separate phono preamp.

In the app Configuration, set `input_mode: usb_meter`, `audio_source: auto`,
`audio_threshold_dbfs: -50`, and `audio_update_seconds: 1`. Save and restart.
The automatic source selector requires one Burr-Brown USB Audio CODEC capture
source. It never chooses speaker playback monitor sources or onboard audio.
If selection fails, Log lists available input names; paste the desired full
PulseAudio source name into `audio_source`, save, and restart.

This mode makes no AudD calls, does not publish track metadata, and consumes no
recognition quota. Audio is processed locally in memory and discarded.

Entities (with the default `turntable` prefix):

- `sensor.turntable_audio_level`: stereo RMS over each update window, in dBFS.
- `sensor.turntable_audio_peak`: maximum sample magnitude in that window, in dBFS.
- `sensor.turntable_audio_signal`: `audio` when RMS meets the threshold, otherwise `quiet`.
- `sensor.turntable_audio_input_status`: `monitoring` or `error`, with input/error attributes.

0 dBFS is full scale. Smaller negative numbers are louder. The display floor is
-100 dBFS. This measures the electrical audio input, not acoustic room loudness.
The signal sensor detects level only; it cannot distinguish music from noise.
Observe quiet and music levels before choosing a threshold. On capture failure,
level sensors become unavailable and the input reconnects automatically.

For a dashboard, add a Manual card using `examples/usb-audio-dashboard.yaml`.
The graph shows the last 15 minutes; the entities below it show live readings.

Other input modes continue to work as in 0.2.0. Continuous recognition and
Tidbyt takeover based on this signal threshold are a later step.
