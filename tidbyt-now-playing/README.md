# Tidbyt Turntable Now Playing

## Files

- `vinylnowplaying.star`: Tidbyt Pixlet screen.
- `home-assistant.yaml`: Home Assistant script and automation.

## Install the Tidbyt screen

Copy `vinylnowplaying.star` to:

`/config/tidbyt/vinylnowplaying.star`

## Test from Developer Tools

Run `tidbytassistant.push` with:

```yaml
contenttype: custom
customcontent: vinylnowplaying
publishtype: foreground
devicename:
  - living_room
arguments: "artist=Tears For Fears;title=Everybody Wants To Rule The World;album=Songs From The Big Chair;year=1985;artwork_url=https://i.scdn.co/image/ab67616d0000b27322463d6939fec9e17b2a6235;background=#1f4241;page=details"
```

## Add the scripts and automations

Add the contents of `home-assistant.yaml` to the appropriate script and
automation YAML files, or create both through the Home Assistant UI using Edit
in YAML. Replace the previous `show_turntable_now_playing` script and the old
"Show New Song on Tidbyt", "Live Sonos Group Volume on Living Room Tidbyt", and
"Hide Tidbyt Sonos Volume After Idle" automations. Keep unrelated scripts and
automations in those files.

The controller starts when both `sensor.turntable_playback_state` is `playing`
and `sensor.turntable_now_playing` contains a recognized track. It explicitly
pushes the song details page for ten seconds, then the album page for ten
seconds, and repeats until playback ends. A new recognized track restarts it
with the new metadata.

The details and album pages are separate pushes using the same Tidbyt content
ID. This makes each ten-second view explicit instead of depending on a nested
animation sequence. Only clockwise or counterclockwise events from the Hue
rotary dial interrupt that loop; changing volume from a dashboard slider does
not. The volume script shows the current group volume and waits three seconds
after the latest dial event. If a recognized track is still playing, it resumes
the now-playing loop; otherwise it removes both temporary apps and restores the
normal Tidbyt rotation. No timer helper is required.

Use `page=details` or `page=album` when testing a single view from Developer
Tools. The album view has a 32×32 cover on the left with a scrolling album name
and year on the right. If no artwork URL is available, it shows `NO COVER ART`.
The optional `background` argument applies to both views; it falls back to navy
when omitted.

The Tidbyt app is installed under content ID `vinylnowplaying` while a track is
active, and deleted when playback is idle. If an older copy remains in the
rotation, delete it manually with `tidbytassistant.delete`:

```yaml
contentid: vinylnowplaying
devicename:
  - living_room
```


