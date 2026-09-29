# Home Assistant Turntable Recognition

This public repository contains two installable pieces for Home Assistant:

- **Turntable Recognition app** in [`turntable_recognition/`](turntable_recognition/): captures the Behringer UFO202 USB audio input, recognizes records with AudD, publishes sensors, and keeps recent-play metadata.
- **Turntable Now Playing dashboard card** in [`dist/`](dist/): a HACS-managed custom card that displays album art, title, artist, album, and year from the app's now-playing sensor.

## Install the app

In Home Assistant, open **Settings → Apps → App store → Repositories** and add:

```text
https://github.com/brettparis37-coder/home-assistant-turntable-recognition
```

Install **Turntable Recognition**. Configure the AudD token, use `usb_auto` for automatic listening, and leave `audio_source` set to `auto` unless the UFO202 needs to be selected by its PulseAudio source name.

## Install the dashboard card through HACS

1. Make sure HACS is installed.
2. In HACS, open the three-dot menu and choose **Custom repositories**.
3. Add the repository URL above and choose **Dashboard** as the category.
4. Find **Turntable Now Playing Card** in HACS and download it.
5. Refresh Home Assistant. In a dashboard, choose **Edit dashboard → Add card** and search for **Turntable Now Playing**. It defaults to `sensor.turntable_now_playing`.

The card renders the app's `artwork_url` (with release/master artwork fallbacks), title, artist, album, and year. It shows a quiet “Nothing playing” state when the app has no current track. If HACS does not register the resource automatically, add the resource `/hacsfiles/home-assistant-turntable-recognition/home-assistant-turntable-recognition.js` as a JavaScript module under **Settings → Dashboards → Resources**.

If Home Assistant is 2026.6 or newer, the card can also be suggested when selecting the now-playing entity in the card picker.

See [`turntable_recognition/DOCS.md`](turntable_recognition/DOCS.md) for app options, sensors, diagnostics, and dashboard YAML examples.
