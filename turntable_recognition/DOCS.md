# Configuration and testing

## Entities

The app publishes:

- `sensor.turntable_now_playing`
- `sensor.turntable_artist`
- `sensor.turntable_title`
- `sensor.turntable_album`
- `sensor.turntable_year`
- `sensor.turntable_recognition_status`

The main `sensor.turntable_now_playing` entity contains artist, title, album,
release date, year, label, timecode, artwork URL, song link, Spotify URL,
Apple Music URL, provider, recognition time, and request counts as attributes.

## Mock test

Keep `input_mode` set to `mock`, edit the four mock metadata fields if desired,
save the configuration, and restart the app. The test entities should appear in
Developer Tools > States.

## AudD URL test

1. Create an AudD API token.
2. Enter the token in `audd_api_token`.
3. Set `input_mode` to `audio_url`.
4. Enter a publicly reachable audio file URL in `test_audio_url`.
5. Save and restart the app.
6. Open the app log and then inspect the entities in Developer Tools > States.

One AudD request is made each time the app starts in `audio_url` mode.

## Home Assistant Media file test

1. Place a short audio file that you own in Home Assistant's Media directory.
2. Set `input_mode` to `media_file`.
3. Set `media_file` to its path relative to Media, such as `turntable/test.mp3`.
4. Save and restart the app.

One AudD request is made each time the app starts in `media_file` mode.

## Simulated USB capture

This mode tests the future capture pipeline without a USB audio interface. It
uses FFmpeg to extract and convert a short section of a Media file, then sends
the generated WAV capture to the configured provider.

1. Put a song in Media, such as `turntable/test.mp3`.
2. Set `input_mode` to `simulated_usb`.
3. Set `media_file` to `turntable/test.mp3`.
4. Set `sample_seconds` between 5 and 12.
5. Optionally set `simulated_start_seconds` to skip a quiet introduction.
6. Save and restart the app.

One recognition request is made per app start. The status progresses through
`capturing`, `recognizing`, and `recognized`.

The app currently runs one capture on startup. It does not yet monitor the
turntable for silence or song changes, so restart it to run another test.

## Spending controls

`max_requests_per_day` and `max_requests_per_month` stop AudD calls after the
configured limit. Request counts are stored in the app's persistent data folder.

