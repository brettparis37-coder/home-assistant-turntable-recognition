# Automatic USB recognition (0.7.0)

## Failed audio samples (0.10.2)

Automatic recognition retains the last five submitted samples that AudD does not recognize or rejects as WAV files under `/media/turntable_recognition/failed_samples`. Each WAV has a JSON sidecar with UTC capture time, attempt ID, failure outcome, measured audio-level summary, and error text. When retention is exceeded, the oldest WAV and sidecar are evicted. Successful recognition samples are discarded after the request. Set `failed_sample_retention` to `0` to disable archiving; supported values are 0 through 20.

Open **Media → My media → turntable_recognition → failed_samples** to browse and play the samples. These files are in Home Assistant's authenticated local media directory, not a public `/local` folder. They may contain copyrighted music from your records; keep the retention limit low and delete files from Media when no longer needed.

## Diagnostics (0.10.0)

Open **Settings → Apps → Turntable Recognition → Log** to see one-line JSON
events with UTC timestamps. Events identify the selected input, playback start
and end, capture duration and RMS range, AudD request start/result/error,
recognition outcome, backoff number, and exact next retry time. HTTP failures
include their status, endpoint, a bounded response excerpt, and the relevant
exception traceback. Credentials and recorded audio are never written to logs.

`sensor.turntable_recognition_status` includes `last_attempt_id`, `last_attempt_at`, `last_attempt_outcome`,
`last_attempt_error`, `last_attempt_duration_seconds`, `consecutive_failures`,
`retry_seconds`, and `check_reason`. The playback-state entity continues to
show whether a request is active and when the next scheduled check is due.

When AudD returns no match, it supplies no alternate candidate list. The log
will say that the response had `result=null`; this is different from an HTTP
or API error. A Discogs no-match log includes whether the database was missing,
the exact recognized-title candidate count, artist-credit mismatches, and up
to three closest cached track titles when available. Metadata-catalog lookup
failures are logged separately from AudD recognition failures.

## Discogs collection matching (0.9.0)

Enable `discogs_enabled` after the Discogs Connector has populated the shared
`/share/home_apps.sqlite3` database. Recognition checks only tracks in your
cached collection. If no exact track-title match is found, the existing AudD
and catalog metadata path remains in use. The database is mounted read/write
for SQLite WAL compatibility, but recognition opens it read-only.

The now-playing entity publishes `release_year`, `master_year`,
`release_artwork_url`, and `master_artwork_url` alongside the selected `year`
and `artwork_url`. The `discogs_year_preference` and
`discogs_artwork_preference` options choose which value fills the familiar
display fields; both source values remain available.

Matching is exact after basic punctuation/case normalization. If several
owned releases contain the same title, it prefers a matching artist credit,
then a stable release/track ordering.

Recognition requests now include Spotify, Apple Music, and MusicBrainz metadata.
The app prefers an official original album for display, ranks deluxe/reissue and
single releases lower, and keeps timing tied to the recognized recording. Exact
standard-album artwork is resolved through Apple's public catalog when possible.
Resolved album metadata is cached under `/data/album_cache.json`; raw audio and
temporary WAV files are not retained. If enrichment fails, recognition continues
with the original AudD/Spotify/Apple metadata.

Set `input_mode: usb_auto` to enable automatic recognition. Keep the existing
audio source, AudD token, and request limits. Save and restart the app.

Defaults (all configurable in Options):

- Start above `playback_start_dbfs: -30` for `playback_start_seconds: 2` seconds.
- End below `playback_stop_dbfs: -35` for `playback_stop_seconds: 15` seconds.
- Capture `sample_seconds` of contiguous audio, then recognize once.
- For a new song, estimate its end from provider duration and match position,
  starting when recognition completes, then wait `song_end_buffer_seconds: 3`.
- If the input is quiet when that timer expires, return to idle without an API
  request. Recognition resumes only after the start threshold is crossed again.
- Same song: retry after `same_song_retry_seconds: 15` seconds.
- Missing timing: check after `fallback_check_seconds: 60` seconds.
- No match/errors: start at `no_match_retry_seconds: 30`, double up to 300 seconds.

Timing is approximate: vinyl versions, speed differences, and provider match
positions can vary. Short quiet passages pause sampling; sustained quiet clears
all current track metadata and cancels pending checks. A request already sent
may complete, but a response from an ended session cannot repopulate the display.
Local level monitoring continues during requests. One bounded sample and one
request are allowed at a time; temporary WAVs are deleted. Limits prevent new
calls and are checked locally once per minute until the UTC counters reset.

`sensor.turntable_playback_state` reports playing/idle and attributes
`next_check_at`, `check_reason`, `quiet`, and `request_active`.
`sensor.turntable_now_playing` contains title, artist, album, artwork, year,
`duration_seconds`, and `position_seconds`, and becomes Nothing playing when idle.
The playback state should gate dashboard metadata during startup/disconnection.
This mode does not consume manual stdin commands or push to Tidbyt.

## USB audio meter and manual recognition

Use this mode to test the UFO202 line input locally before enabling recognition.
Set the UFO202 to LINE when feeding it from a separate phono preamp.

In the app Configuration, set `input_mode: usb_meter`, `audio_source: auto`,
`audio_threshold_dbfs: -50`, and `audio_update_seconds: 1`. Save and restart.
The automatic source selector requires one Burr-Brown USB Audio CODEC capture
source. It never chooses speaker playback monitor sources or onboard audio.
If selection fails, Log lists available input names; paste the desired full
PulseAudio source name into `audio_source`, save, and restart.

Monitoring alone makes no AudD calls. A manual command captures the next
`sample_seconds` of live USB audio and makes one AudD recognition request.
It updates the existing artist, title, album, year, and now-playing entities.
There are no automatic recognition requests or retries. Duplicate presses
while capturing or recognizing are ignored. Disconnecting during sampling
reports an error without sending a recognition request. Temporary audio is
deleted after completion or failure. The meter continues updating.

Use this dashboard button on Home Assistant versions with app action names:

```yaml
type: button
name: Recognize now
icon: mdi:music-note-search
tap_action:
  action: perform-action
  perform_action: hassio.app_stdin
  data:
    app: 2de1fd4c_turntable_recognition
    input:
      command: recognize
```

Replace the app slug if your installation uses a different repository slug.
Earlier Home Assistant versions use `hassio.addon_stdin` with `addon` instead
of `app`. Keep existing AudD credentials in the app configuration.

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
The display window does not control Recorder retention: detailed numeric
history follows your Home Assistant Recorder settings (10 days by default).

Other input modes continue to work. Tidbyt takeover remains a separate step.

