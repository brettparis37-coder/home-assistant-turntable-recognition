# Turntable Recognition

Recognizes music and publishes structured now-playing data to Home Assistant.

Version 0.2.0 supports:

- Mock metadata for dashboard and Tidbyt development.
- AudD recognition from a public audio URL.
- AudD recognition from an audio file in Home Assistant's Media directory.
- Simulated USB capture that uses FFmpeg to cut and convert a Media file into
  the same short WAV format that the future USB input will create.
- Daily and monthly request limits.
- A provider interface that allows SongRec or another provider to be added later.

Physical USB line-input recording and continuous track-change detection are
planned for the next version.

