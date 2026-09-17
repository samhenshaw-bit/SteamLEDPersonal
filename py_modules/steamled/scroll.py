"""Named color presets for the Animated effect.

Anything whose neighbors sit on opposite sides of the hue wheel goes gray
where they meet. Presets are ordered so adjacent colors are hue-adjacent.
More than four stops limits each color to ~three pixels on a 17-LED strip.
"""

from .color import hsv, to_hex

# Order pins custom and rainbow at top; rest alphabetical.
ORDER = [
    "custom",
    "rainbow",
    "aurora",
    "candy",
    "deep_sea",
    "ember",
    "forest",
    "miami",
    "orchid",
    "sunset",
    "toxic",
    "ultraviolet",
]

PRESETS = {
    "custom":     {"label": "Custom",      "colors": []},
    "rainbow":    {"label": "Rainbow",     "colors": []},  # generated
    "aurora":     {"label": "Aurora",      "colors": ["00FFCC", "0080FF", "8000FF"]},
    "candy":      {"label": "Candy",       "colors": ["FF69B4", "FF1493", "FF69B4", "FFFFFF"]},
    "deep_sea":   {"label": "Deep Sea",    "colors": ["001F5B", "0066CC", "00CCFF", "00FFCC"]},
    "ember":      {"label": "Ember",       "colors": ["FF0000", "FF4400", "FF8800", "FFCC00"]},
    "forest":     {"label": "Forest",      "colors": ["003300", "006600", "00CC00", "66FF66"]},
    "miami":      {"label": "Miami",       "colors": ["FF1177", "FF44CC", "CC44FF", "4488FF"]},
    "orchid":     {"label": "Orchid",      "colors": ["660066", "CC00CC", "FF44FF", "AA00FF"]},
    "sunset":     {"label": "Sunset",      "colors": ["FF0044", "FF4400", "FF8800", "FFCC00", "FF6600"]},
    "toxic":      {"label": "Toxic",       "colors": ["00FF00", "88FF00", "CCFF00", "FFFF00"]},
    "ultraviolet":{"label": "Ultraviolet", "colors": ["2200FF", "8800FF", "CC00FF", "FF00CC"]},
}


def rainbow_colors(spread=1.0, count=8):
    """Generate a hue wheel. spread controls how many turns are covered."""
    spread = max(0.2, min(3.0, spread))
    out = []
    for i in range(count):
        h = (i / count) * spread
        out.append(to_hex(hsv(h % 1.0, 1.0, 1.0)))
    return out


def is_generated(preset_id):
    return preset_id == "rainbow"


def colors_for(preset_id, spread=1.0):
    """Return hex color list for a preset. Empty list for 'custom'."""
    if preset_id == "rainbow":
        return rainbow_colors(spread)
    preset = PRESETS.get(preset_id)
    if not preset:
        return []
    return list(preset["colors"])


def options(include_custom=True):
    """Dropdown options list."""
    out = []
    for k in ORDER:
        if k == "custom" and not include_custom:
            continue
        p = PRESETS.get(k)
        if p:
            out.append({"value": k, "label": p["label"]})
    return out
