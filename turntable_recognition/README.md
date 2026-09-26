# Turntable Recognition

Version 0.5.0 adds original-album metadata resolution to automatic live USB recognition.

Set `input_mode: usb_auto` and `audio_source: auto`, save and restart. Keep your existing AudD token and request limits.

- Playback sessions start above -30 dBFS for 2 seconds and end below -35 dBFS for 15 seconds by default.
- AudD recognition requests include Spotify, Apple Music, and MusicBrainz metadata.
- The display prefers an official original album over singles, compilations, deluxe editions, and reissues.
- Duration stays tied to the recognized recording; AudD timecode supplies playback position.
- Exact standard-album artwork is resolved through Apple's public catalog, with provider and MusicBrainz/Internet Archive fallbacks.
- Album metadata is cached by MusicBrainz recording ID or ISRC in `/data/album_cache.json`; raw audio samples are temporary and deleted.
- New matches schedule the next check near estimated song completion. Same-song matches retry after 15 seconds, missing timing falls back to 60 seconds, and failures back off to 300 seconds.
- Idle sessions clear now-playing metadata. Late responses cannot revive ended sessions.

The now-playing entity exposes artist, title, recognized version, album, original year, artwork and its source, ISRC, MusicBrainz IDs, duration, position, timing source, and selection reason. See Documentation for full options.

Use LINE on the UFO202 when feeding it from an external phono preamp. dBFS measures captured electrical signal, not room loudness or Sonos volume.
