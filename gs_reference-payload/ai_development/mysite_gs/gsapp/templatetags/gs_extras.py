"""Template tags for the gs-reference mock.

`gs_placeholder` returns an `<img>` tag pointing at picsum.photos with a
deterministic seed so a given (tint, aspect, label/seed) tuple yields
the same photo across page loads. Picsum serves stock photography
sourced from Unsplash, no API key, free for commercial use.

The mock requires internet on first paint to fetch the image; the
browser caches subsequent loads.
"""
import hashlib

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


# Aspect → (width, height) in px. Picsum scales the photo and we let CSS
# fit it to the container with object-fit: cover.
ASPECTS = {
    "16x9": (1600, 900),
    "21x9": (2100, 900),
    "4x5":  (800, 1000),
    "1x1":  (1000, 1000),
}


@register.simple_tag
def gs_placeholder(tint="navy", aspect="16x9", label="", seed=""):
    """Render an <img> backed by Picsum (Unsplash-sourced stock photo).

    Args:
        tint:   semantic color hint from the dataviz palette (navy, sky,
                mauve, teal, burnt, purple, brick, amber, brown, olive).
                Used as part of the deterministic seed so a given tint
                consistently picks the same image across loads.
        aspect: '16x9' / '21x9' / '4x5' / '1x1'.
        label:  optional content hint folded into the seed for
                additional uniqueness.
        seed:   explicit override seed string; if non-empty, takes
                precedence over the tint+label hash so callers can
                guarantee distinct images per placement.
    """
    width, height = ASPECTS.get(aspect, ASPECTS["16x9"])
    seed_str = seed or f"{tint}-{aspect}-{label}"
    # Hash the seed to a stable short token Picsum accepts.
    digest = hashlib.sha1(seed_str.encode("utf-8")).hexdigest()[:12]
    url = f"https://picsum.photos/seed/{digest}/{width}/{height}"
    alt = _safe(label or f"placeholder ({tint})")
    return mark_safe(
        f'<img src="{url}" alt="{alt}" loading="lazy" '
        f'width="{width}" height="{height}">'
    )


def _safe(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
