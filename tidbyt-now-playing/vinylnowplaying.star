load("render.star", "render")
load("http.star", "http")

BACKGROUND = "#101d3d"
HEADER = "#75bfff"
ARTIST = "#ffffff"
TITLE = "#35d6c7"
DETAIL = "#9db4dc"
PAGE_FRAMES = 50
FRAME_DELAY = 100


def clean(value, fallback):
    if value == None or value == "" or value == "unknown" or value == "unavailable":
        return fallback
    return value


def song_page(artist, title, detail):
    return render.Stack(
        children = [
            render.Box(width = 64, height = 32, color = BACKGROUND),
            render.Padding(
                pad = (2, 1, 0, 0),
                child = render.Text(
                    content = "NOW SPINNING",
                    font = "CG-pixel-3x5-mono",
                    color = HEADER,
                ),
            ),
            render.Padding(
                pad = (2, 8, 0, 0),
                child = render.Marquee(
                    width = 60,
                    align = "start",
                    child = render.Text(content = artist, font = "tb-8", color = ARTIST),
                ),
            ),
            render.Padding(
                pad = (2, 17, 0, 0),
                child = render.Marquee(
                    width = 60,
                    align = "start",
                    delay = 5,
                    child = render.Text(content = title, font = "tb-8", color = TITLE),
                ),
            ),
            render.Padding(
                pad = (2, 27, 0, 0),
                child = render.Marquee(
                    width = 60,
                    align = "start",
                    delay = 10,
                    child = render.Text(
                        content = detail,
                        font = "CG-pixel-3x5-mono",
                        color = DETAIL,
                    ),
                ),
            ),
        ],
    )


def cover_page(artwork_url):
    if artwork_url == "":
        return render.Box(
            width = 64,
            height = 32,
            color = BACKGROUND,
            child = render.Text(
                content = "NO COVER ART",
                font = "CG-pixel-3x5-mono",
                color = DETAIL,
            ),
        )

    response = http.get(artwork_url, ttl_seconds = 3600)
    if response.status_code != 200:
        return cover_page("")

    return render.Box(
        width = 64,
        height = 32,
        color = BACKGROUND,
        child = render.Image(src = response.body(), width = 32, height = 32),
    )


def main(config):
    artist = clean(config.get("artist"), "Unknown artist")
    title = clean(config.get("title"), "Unknown song")
    album = clean(config.get("album"), "")
    year = clean(config.get("year"), "")
    artwork_url = clean(config.get("artwork_url"), "")

    detail = album
    if album != "" and year != "":
        detail = album + "  |  " + year
    elif year != "":
        detail = year

    first_page = song_page(artist, title, detail)
    second_page = cover_page(artwork_url)

    return render.Root(
        delay = FRAME_DELAY,
        max_age = 900,
        show_full_animation = True,
        child = render.Animation(
            children = [first_page] * PAGE_FRAMES + [second_page] * PAGE_FRAMES,
        ),
    )

