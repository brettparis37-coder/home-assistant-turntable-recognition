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

