"""Extract a readable dominant accent color from supported album-art hosts."""

from __future__ import annotations

import colorsys
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image


_ALLOWED_IMAGE_DOMAINS = (
    "discogs.com",
    "scdn.co",
    "mzstatic.com",
    "coverartarchive.org",
    "archive.org",
)
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def _read_image_bytes(artwork_url: str) -> bytes:
    request = Request(artwork_url, headers={"User-Agent": "HomeAssistantTurntableRecognition/0.12.0"})
    opener = build_opener(_NoRedirect())
    content = bytearray()
    with opener.open(request, timeout=4) as response:
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > _MAX_IMAGE_BYTES:
                return b""
    return bytes(content)


def dominant_artwork_color(artwork_url: str) -> str:
    """Return a vivid, readable hex color, or empty when the image is unavailable."""
    parsed = urlparse(artwork_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(
        host == domain or host.endswith("." + domain) for domain in _ALLOWED_IMAGE_DOMAINS
    ):
        return ""

    content = _read_image_bytes(artwork_url)
    if not content:
        return ""
    image = Image.open(BytesIO(content)).convert("RGB")
    image.thumbnail((48, 48))
    palette = image.quantize(colors=16).convert("RGB")
    candidates = []
    for count, (red, green, blue) in palette.getcolors(48 * 48) or []:
        hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        if value < 0.18 or value > 0.98 or saturation < 0.16:
            continue
        # Bright, saturated regions should beat large areas of dark cover shadow.
        score = count * ((0.25 + saturation) ** 1.5) * ((0.2 + value) ** 2)
        candidates.append((score, hue, saturation, value))

    if not candidates:
        colors = palette.getcolors(48 * 48) or []
        if not colors:
            return ""
        _count, (red, green, blue) = max(colors)
        hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        if saturation < 0.16:
            return "#48484a"
    else:
        _score, hue, saturation, value = max(candidates)

    rgb = colorsys.hsv_to_rgb(
        hue,
        max(0.48, min(0.88, saturation)),
        max(0.42, min(0.58, value)),
    )
    return "#%02x%02x%02x" % tuple(round(channel * 255) for channel in rgb)

