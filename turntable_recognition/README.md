# Turntable Recognition

Version 0.13.0 adds ShazamIO as the first-pass recognizer, with AudD as a fallback. Shazam attempts do not use AudD quota. The app supports the Behringer UFO202 USB input, automatic recognition, a USB meter/manual diagnostic mode, Discogs collection matching, timestamped diagnostics, a five-sample failed-audio cache, persistent history for the latest three plays, and live album-art color on the Now Playing card.

## Install and configure

Install this Home Assistant app from the repository. In its Configuration page:

- Select `usb_auto` for normal automatic playback detection. `usb_meter` is the USB diagnostic/manual-recognition mode.
- Enter the AudD API token.
- Leave `shazam_enabled` on to try Shazam first and use AudD only when Shazam cannot identify a track. Turn it off to use AudD directly.
- Leave `audio_source` as `auto` to find the UFO202 by USB identity. Only set an explicit PulseAudio input name if auto-detection fails.
- Set `sample_seconds` from 5 to 20; it defaults to 15.
- Keep the request caps and failed-sample retention at their defaults unless you want different limits.
- Enable `discogs_enabled` when the Discogs Connector has filled `/share/home_apps.sqlite3`.

The app publishes its sensor entities automatically. The repository also includes HACS dashboard cards for Now Playing (with album artwork) and recognition diagnostics; install the repository in HACS as a **Dashboard** custom repository, then search for their names in the card picker. A complete view example is in [`examples/turntable-view.yaml`](examples/turntable-view.yaml).

For all options, entity IDs, audio capture details, play-history behavior, and troubleshooting, see [Documentation](DOCS.md).

