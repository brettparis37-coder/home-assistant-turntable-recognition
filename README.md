# Home Assistant Turntable Recognition

A Home Assistant app that recognizes music captured from a turntable and
publishes structured now-playing entities for dashboards, automations, and
Tidbyt displays.

## Current features

- Pluggable recognition-provider interface.
- AudD provider.
- Mock metadata mode.
- Public audio URL recognition.
- Home Assistant Media file recognition.
- Simulated USB capture using FFmpeg.
- Artist, title, album, year, artwork, provider, and usage entities.
- Daily and monthly request limits.

See [`turntable_recognition/DOCS.md`](turntable_recognition/DOCS.md) for setup
and testing instructions.

## Install in Home Assistant

In **Settings → Apps → App store → Repositories**, add:

```text
https://github.com/brettparis37-coder/home-assistant-turntable-recognition
```

Install **Turntable Recognition** from the app store. Start with `input_mode:
mock` to check the entities without using AudD requests. The default AudD URL
test and simulated USB modes each make one recognition request when the app
starts.

