# Turntable Recognition documentation

## What the app does

The app monitors the Behringer UFO202 input through Home Assistant's PulseAudio source, detects playback, captures a bounded WAV, asks AudD to identify it, enriches matched metadata, optionally checks the local Discogs collection, and publishes sensors through the Home Assistant API. It also publishes audio-level and AudD usage sensors, logs timestamped diagnostics, archives a bounded number of failed samples, and stores the latest three play events.

The app does not edit your existing dashboard or install Tidbyt automations. Its entities are available to the standard Lovelace entity picker. Hue dial and Tidbyt scripts/automations remain separate Home Assistant configuration.

## App configuration

### Input and capture

| Option | Default | Purpose |
| --- | --- | --- |
| `input_mode` | `usb_auto` | `usb_auto` detects and recognizes automatically. `usb_meter` monitors the input and supports a one-shot manual recognition command. Both modes use the UFO202 USB capture source. |
| `audio_source` | `auto` | Finds the single Burr-Brown USB Audio CODEC source and ignores playback-monitor inputs. Use an exact PulseAudio source name only if auto-detection cannot choose the device. |
| `sample_seconds` | `15` | Contiguous recognition sample length; allowed range is 5–20 seconds. |
| `audio_update_seconds` | `1` | Length of each level-meter update window. |
| `audio_threshold_dbfs` | `-50` | Threshold for the diagnostic `audio_signal` sensor; it does not control the playback session detector. |

### Playback detection and retries

| Option | Default | Purpose |
| --- | --- | --- |
| `playback_start_dbfs` | `-30` | Signal must exceed this level to start or resume a capture. |
| `playback_start_seconds` | `2` | How long the start level must hold before playback is active. |
| `playback_stop_dbfs` | `-35` | Lower hysteresis threshold used to identify quiet input. |
| `playback_stop_seconds` | `15` | Quiet hold time before returning to idle and clearing now-playing. |
| `song_end_buffer_seconds` | `3` | Wait after estimated track end before checking for another song. |
| `same_song_retry_seconds` | `15` | Retry delay when the next recognition is still the same track. |
| `fallback_check_seconds` | `60` | Check delay when duration or position is unavailable. |
| `no_match_retry_seconds` | `30` | Base delay for no-match and request errors; the app backs off up to 300 seconds. |

### AudD request limits

| Option | Default | Purpose |
| --- | --- | --- |
| `audd_api_token` | empty | Your private AudD token. Never place it in repository files. |
| `max_requests_per_day` | `100` | Local safety cap. |
| `max_requests_per_month` | `1000` | Local safety cap for the current billing cycle. |
| `billing_cycle_day` | `25` | First day of the configured monthly cycle. |

### Discogs and artwork/year choices

| Option | Default | Purpose |
| --- | --- | --- |
| `discogs_enabled` | `false` | Match AudD artist/title against the locally cached Discogs collection. |
| `discogs_database_path` | `/share/home_apps.sqlite3` | Shared database created by Discogs Connector. |
| `discogs_artwork_preference` | `master` | Choose master or specific-release artwork for the familiar `artwork_url`; both values remain in attributes. |
| `discogs_year_preference` | `master` | Choose original master year or specific-release year for `year`; both values remain in attributes. |

### Failed sample cache and entities

| Option | Default | Purpose |
| --- | --- | --- |
| `failed_sample_retention` | `5` | Keep up to this many submitted automatic WAV requests that AudD fails to recognize or rejects. Range 0–20; 0 disables archiving. Successful captures are discarded. |
| `entity_prefix` | `turntable` | Prefix for published entity IDs. Keep this unchanged after adding dashboards or automations. |

Failed WAVs and timestamped JSON sidecars live under `/media/turntable_recognition/failed_samples`. Browse them in **Media → My media → turntable_recognition → failed_samples**. The media folder is authenticated in Home Assistant. The archive contains audio from your records; oldest samples are evicted when retention is exceeded.

The latest three plays are persisted in the app's `/data/play_history.json`. The newest entry backs `sensor.turntable_now_playing`; the next two entries back `sensor.turntable_previous_track` and `sensor.turntable_two_plays_ago`. Each history sensor exposes full Track metadata, including artwork/year selections, Discogs IDs, and `played_at`. Repeated same-song checks during one playback session do not count as new plays. Playing the same song in a later session does.

## Home Assistant entities

With the default `entity_prefix: turntable`, the app publishes:

- `sensor.turntable_now_playing`, `sensor.turntable_artist`, `sensor.turntable_title`, `sensor.turntable_album`, `sensor.turntable_year`
- `sensor.turntable_previous_track`, `sensor.turntable_two_plays_ago`
- `sensor.turntable_playback_state`, `sensor.turntable_recognition_status`
- `sensor.turntable_audio_level`, `sensor.turntable_audio_peak`, `sensor.turntable_audio_signal`, `sensor.turntable_audio_input_status`
- `sensor.turntable_audd_usage`, `sensor.turntable_audd_requests_remaining`

Add built-in **Entities**, **Tile**, or **History graph** cards and search these names. The example view in [`examples/turntable-view.yaml`](examples/turntable-view.yaml) is optional and must be added to a dashboard by the user.

### Why the app YAML does not add a custom card to the picker

An app's `config.yaml` configures the app container and its options. Lovelace card types are separate frontend resources. A searchable custom card needs JavaScript registered as a dashboard resource and a `window.customCards` entry; installing this app alone cannot register that frontend resource. See [Home Assistant's custom card documentation](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/) and [resource registration instructions](https://developers.home-assistant.io/docs/frontend/custom-ui/registering-resources/).

The no-extra-install option is to use the built-in cards above. To get a dedicated **Turntable Recognition** card or dashboard strategy in the picker, this project would need a separately installed custom integration/frontend resource (commonly distributed through HACS). The app repository can provide those files, but the app install itself cannot make Home Assistant load them.

## USB source selection

Automatic selection looks for one non-monitor input whose PulseAudio name/properties identify the Burr-Brown USB Audio CODEC (UFO202). It does not select speakers, monitor sources, or the host's built-in microphone. The log event `recording_inputs_discovered` lists available inputs. If more than one UFO202-like input is found or none is found, set `audio_source` to the exact capture source name from that log. Do not use `/dev/snd/controlC*` or `/dev/input/event*`; those are device/control nodes, not PulseAudio recording sources.

## Diagnostics and manual recognition

Open **Settings → Apps → Turntable Recognition → Log**. The logs use UTC timestamps and include selected source, input dBFS, capture length/level range, AudD response, Discogs match diagnostics, retry timing, and detailed errors. No-match is a successful API response with `result: null`; it is not an authentication failure.

In `usb_meter` mode, a `recognize` command through `hassio.app_stdin` captures one sample and sends one AudD request. Duplicate requests while capture is active are ignored. Use `usb_auto` for the normal playback workflow.

## Dashboard examples and app testing

The production image copies only `app/`; automated unit tests are in the repository's `tests/` folder and are not included in the running app container. Run them from the repository root with:

```sh
python -m unittest discover -v
```

Dashboard YAML is an optional view example, not an automatically installed custom card. Installing the app publishes entities; it does not change dashboard storage or add cards to existing views.

