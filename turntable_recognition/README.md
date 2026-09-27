# Turntable Recognition

Version 0.9.0 adds optional matching against the local Discogs collection, with distinct release/master artwork and year attributes, plus Tidbyt playback cleanup and resume behavior.

Set `input_mode: usb_auto` and `audio_source: auto`, save and restart. Keep your existing AudD token and request limits.

- Playback sessions start above -30 dBFS for 2 seconds and end below -35 dBFS for 15 seconds by default.
- AudD recognition requests include Spotify, Apple Music, and MusicBrainz metadata.
- The display prefers an official original album over singles, compilations, deluxe editions, and reissues.
- Duration stays tied to the recognized recording; AudD timecode supplies playback position.
- Exact standard-album artwork is resolved through Apple's public catalog, with provider and MusicBrainz/Internet Archive fallbacks.
- Album metadata is cached by MusicBrainz recording ID or ISRC in `/data/album_cache.json`; raw audio samples are temporary and deleted.
- New matches schedule the next check from recognition completion plus a three-second song-end buffer. Quiet input at that point returns to idle without an API request. Same-song matches retry after 15 seconds, missing timing falls back to 60 seconds, and failures back off to 300 seconds.
- Idle sessions clear now-playing metadata. Late responses cannot revive ended sessions.

The now-playing entity exposes artist, title, recognized version, album, original year, artwork and its source, ISRC, MusicBrainz IDs, duration, position, timing source, and selection reason. See Documentation for full options.

Use LINE on the UFO202 when feeding it from an external phono preamp. dBFS measures captured electrical signal, not room loudness or Sonos volume.
