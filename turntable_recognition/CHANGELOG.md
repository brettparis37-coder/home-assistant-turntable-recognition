# Unreleased

# 0.14.2

- Add a HACS Turntable Song Facts card that rotates through cached Discogs track facts every 15 seconds, with source links and an empty state when a track has no facts.
- Publish up to five facts for the exact matched Discogs release track on `sensor.turntable_now_playing`; missing fact tables or rows do not interrupt recognition.

# 0.14.1

- Normalize common trailing version labels in recognized titles and add a conservative fuzzy Discogs collection match as a third fallback, using artist credits to resolve close candidates and reporting unresolved ambiguity.

# 0.14.0

- Publish the next playable track from the exact matched Discogs release and use it as a last-resort now-playing prediction after all recognition providers miss.
- Advance predictions at the predicted track's estimated end, using Discogs duration, the release's average track duration, or a marked three-minute estimate; resume normal retry backoff when no next track is available.
- Add `sensor.turntable_predicted_next`, keep predictions out of play history, and label predicted now-playing data separately from confirmed recognition.
- Show a live `MM:SS` countdown to the next scheduled recognition check on the diagnostics card without polling or changing audio/API timing.

# 0.13.1

- Try the Rust Shazam recognizer first, then the slower legacy Shazam recognizer after a no-match or error, before using AudD.
- Enrich the first Shazam match from the local Discogs collection and log which Shazam method matched plus response match counts.

# 0.13.0

- Add ShazamIO as the first-pass music recognizer, with AudD used only after a Shazam no-match or failure.
- Enrich Shazam matches from the local Discogs collection, including track duration; estimate playback position from the captured sample and elapsed time between same-song checks when no provider timecode exists.
- Count and apply AudD daily/monthly request limits only when an AudD request is actually sent.
- Add a `shazam_enabled` option so Shazam recognition can be turned off without removing AudD.
- Use the official Home Assistant Debian base image so ShazamIO's native recognition wheel can install on amd64 and aarch64.

# 0.12.0

- Sample a vivid album-art color on each recognized track and publish it as `dominant_color` on the Now Playing sensor.
- Apply the sampled color to the full Now Playing card background and rerender when the color changes.

# 0.11.0

- Set USB automatic recognition as the default, remove mock, URL, media-file, and simulated-USB modes and their settings, and keep USB meter/manual recognition as the diagnostic mode.
- Automatically remove saved settings left behind by the retired test modes when the updated app starts.
- Raise the sample setting to a 15-second default with a 5–20-second range.
- Persist the latest three recognized play events and publish the previous two as metadata-rich sensors; repeated polling within one session does not duplicate a play.
- Move unit tests out of the runtime app image, document app options in grouped sections, and add a built-in-card dashboard view example.

# 0.10.2

- Keep a configurable rolling cache of the last five failed automatic recognition WAV samples in Home Assistant media, with timestamped metadata sidecars; successful samples are discarded and the oldest files are evicted.
- Allow Home Assistant Media browser access to the protected local-media files; set retention to 0 to disable sample archiving.

# 0.10.0

- Add UTC-timestamped structured logs for USB monitoring, playback sessions, captures, AudD requests, recognition outcomes, retry timing, and Discogs matching diagnostics.
- Publish last-attempt ID, outcome, error, duration, consecutive failures, retry delay, and next-check details on the recognition status sensor.
- Log HTTP status, endpoint, and a bounded response excerpt on failures; never log API credentials or captured audio.

# 0.9.0

- Optionally match recognized tracks to the local Discogs collection database and expose release/master artwork and years separately.
- Clean up both Tidbyt now-playing pages when playback ends and resume now-playing after the temporary volume override.

# 0.8.1

- Discard cached YouTube song-page URLs that were previously stored as album artwork, then resolve and cache a direct catalog cover URL.

# 0.8.0

- Search MusicBrainz by exact artist and track title when AudD does not return a recording ID, then use the matching recording's official album releases.
- Search Apple's catalog for an exact track match when artwork is missing, prefer its matching original album, and fill duration when available.
- Stop treating AudD song-page links, including YouTube watch URLs, as album artwork.
- Push Tidbyt song details and album views as separate ten-second screens and start the display when recognition completes or playback becomes active.

# 0.7.0

- Start the song-end timer when recognition completes, then wait the configured three-second buffer.
- If the input is quiet when that timer expires, return to idle without making an AudD request.
- Require the normal audio start threshold before recognition resumes from that idle state.

# 0.6.0

- Track recognition requests against the configured AudD billing-cycle day.
- Publish numeric usage and remaining-request sensors for Home Assistant dashboards.
- Stop recognition before the configured allowance and report when access refreshes.

# 0.5.0

- Request MusicBrainz metadata with each AudD match and prefer an official original album over singles, compilations, deluxe editions, and reissues.
- Fill missing duration and recording identity from matching Spotify, Apple Music, or MusicBrainz results while retaining AudD timecode for playback position.
- Resolve artwork for the exact standard album through Apple's public catalog, with provider and MusicBrainz/Internet Archive fallbacks.
- Cache resolved album metadata by MusicBrainz recording ID or ISRC in `/data/album_cache.json`; audio samples remain temporary.
- Publish recording, album-release, artwork-source, timing-source, and selection-reason attributes on the now-playing entity.

# 0.4.0

- Add usb_auto playback sessions with configurable start/stop thresholds and hold times.
- Recognize automatically, estimate the next check from song duration and match position, and retry same-song matches after a configurable delay.
- Clear now-playing metadata on quiet input or USB disconnect; ignore stale responses from ended sessions.
- Bound capture memory, prevent overlapping requests, back off failures, and honor daily/monthly limits.
- Publish playback state and next recognition time for dashboards. No Tidbyt changes.

# 0.3.1

- Add manual recognition from live USB with a bounded sample and temporary WAV cleanup.
- Accept one recognize command through Home Assistant app stdin; prevent overlapping requests.
- Keep the meter running during recognition; no automatic recognition or retries.

# 0.3.0

- Add local live USB audio meter with RMS, peak, signal threshold, and input status.
- Select UFO202 through Home Assistant PulseAudio by device identity.
- Retry disconnected input automatically and mark stale levels unavailable.
- Add a dashboard graph example; USB meter mode does not call AudD.

# 0.2.0

- Add simulated USB capture from a Media file with FFmpeg.

