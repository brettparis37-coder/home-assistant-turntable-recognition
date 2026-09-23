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

## Add the script and automation

Add the contents of `home-assistant.yaml` to the appropriate script and
automation YAML files, or create both through the Home Assistant UI using Edit
in YAML.

The automation accepts both `mock` and `recognized` statuses, so mock mode can
be used for the first end-to-end test.

The Home Assistant script pushes song details, waits ten seconds, then pushes
the album view separately. Use `page=details` or `page=album` when testing a
single view from Developer Tools. The album view has a 32×32 cover on the left
with a scrolling album name and year on the right. The frame delay is 50 ms,
making scrolling about twice as fast as the earlier 100 ms version. Pixlet
scales the cover with nearest-neighbor sampling, which keeps the image sharp on
the pixel display. If no artwork URL is available, the second view shows
`NO COVER ART`. The optional `background` argument applies to both views; it
falls back to navy when omitted. The sample value is manually selected. Automatic
color extraction from each recognized album cover is a later recognition-app
change.

Each screen is a one-time foreground display. The album page returns to the
usual Tidbyt rotation afterward. If an older version remains in the rotation
under content ID `vinylnowplaying`, delete it with `tidbytassistant.delete`:

```yaml
contentid: vinylnowplaying
devicename:
  - living_room
```

