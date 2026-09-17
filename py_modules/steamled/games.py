"""Hand-curated per-game color palettes.

These are used as named presets when the user selects them explicitly, or
as a fallback when Now Playing is on but no dynamic palette has been
extracted from artwork yet.

The dynamic palette system (artwork → canvas → k-means → LED) handles
the "any game works automatically" requirement. This file handles games
where the artist picked specific meaningful colors worth preserving.

Format:
  Each game: list of (position, hex, interp_mode) stops where position
  is 0.0-1.0, interp_mode is "rgb" or "hsv".

  animate() returns a time-varying pixel list (currently only Balatro).
  sample() returns a static pixel list.
  match() maps a Steam title string to a palette id.
"""

import math

from .color import from_hex, hsv, lerp, ramp, scale

GAMES = {
    "balatro": {
        "label": "Balatro",
        "stops": [
            (0.0, "FF1744", "rgb"),
            (0.4, "FF6D00", "rgb"),
            (0.7, "AA00FF", "rgb"),
            (1.0, "FF1744", "rgb"),
        ],
        "animated": True,
    },
    "blue_prince": {
        "label": "Blue Prince",
        "stops": [
            (0.0, "0D0D2B", "rgb"),
            (0.4, "1A237E", "hsv"),
            (0.7, "283593", "hsv"),
            (1.0, "C5CAE9", "rgb"),
        ],
    },
    "cs2": {
        "label": "Counter-Strike 2",
        "stops": [
            (0.0, "FF6B00", "rgb"),
            (0.5, "FFAA00", "rgb"),
            (1.0, "FF6B00", "rgb"),
        ],
    },
    "cyberpunk": {
        "label": "Cyberpunk 2077",
        "stops": [
            (0.0, "00FFFF", "rgb"),
            (0.3, "FF00FF", "hsv"),
            (0.7, "FFFF00", "rgb"),
            (1.0, "00FFFF", "rgb"),
        ],
    },
    "deadlock": {
        "label": "Deadlock",
        "stops": [
            (0.0, "FF5500", "rgb"),
            (0.5, "FF8800", "rgb"),
            (1.0, "FF5500", "rgb"),
        ],
    },
    "elden_ring": {
        "label": "Elden Ring",
        "stops": [
            (0.0, "1A0A00", "rgb"),
            (0.3, "8B6914", "rgb"),
            (0.6, "C8A951", "rgb"),
            (1.0, "1A0A00", "rgb"),
        ],
    },
    "forza": {
        "label": "Forza Horizon 5",
        "stops": [
            (0.0, "FF6600", "rgb"),
            (0.4, "FFAA00", "rgb"),
            (0.7, "FFD700", "rgb"),
            (1.0, "FF6600", "rgb"),
        ],
    },
    "gta5": {
        "label": "GTA V",
        "stops": [
            (0.0, "111111", "rgb"),
            (0.2, "00AA00", "rgb"),
            (0.5, "FFFFFF", "rgb"),
            (0.8, "00AA00", "rgb"),
            (1.0, "111111", "rgb"),
        ],
    },
    "half_life": {
        "label": "Half-Life",
        "stops": [
            (0.0, "FF6600", "rgb"),
            (0.5, "FF8800", "rgb"),
            (1.0, "FF6600", "rgb"),
        ],
    },
    "half_life_2": {
        "label": "Half-Life 2",
        "stops": [
            (0.0, "FF6600", "rgb"),
            (0.4, "FF9900", "rgb"),
            (0.7, "FFCC00", "rgb"),
            (1.0, "FF6600", "rgb"),
        ],
    },
    "hollow_knight": {
        "label": "Hollow Knight",
        "stops": [
            (0.0, "111144", "rgb"),
            (0.4, "2244AA", "hsv"),
            (0.7, "88AAFF", "hsv"),
            (1.0, "111144", "rgb"),
        ],
    },
    "silksong": {
        "label": "Hollow Knight: Silksong",
        "stops": [
            (0.0, "1A0033", "rgb"),
            (0.3, "8800CC", "hsv"),
            (0.7, "FF44FF", "hsv"),
            (1.0, "1A0033", "rgb"),
        ],
    },
    "neon_white": {
        "label": "Neon White",
        "stops": [
            (0.0, "FF0080", "hsv"),
            (0.4, "FF8000", "hsv"),
            (0.7, "FFFF40", "rgb"),
            (1.0, "FF0080", "hsv"),
        ],
    },
    "portal": {
        "label": "Portal",
        "stops": [
            (0.0, "0066FF", "rgb"),
            (0.5, "FF6600", "rgb"),
            (1.0, "0066FF", "rgb"),
        ],
    },
    "portal2": {
        "label": "Portal 2",
        "stops": [
            (0.0, "0088FF", "rgb"),
            (0.4, "00CCFF", "rgb"),
            (0.6, "FF8800", "rgb"),
            (1.0, "FF4400", "rgb"),
        ],
    },
    "rdr": {
        "label": "Red Dead Redemption",
        "stops": [
            (0.0, "3D1C02", "rgb"),
            (0.4, "8B3A1A", "rgb"),
            (0.7, "C87941", "rgb"),
            (1.0, "3D1C02", "rgb"),
        ],
    },
    "rdr2": {
        "label": "Red Dead Redemption 2",
        "stops": [
            (0.0, "1A0800", "rgb"),
            (0.3, "7A1F00", "rgb"),
            (0.6, "C85A00", "rgb"),
            (0.85, "F5D08B", "rgb"),
            (1.0, "1A0800", "rgb"),
        ],
    },
    "stardew": {
        "label": "Stardew Valley",
        "stops": [
            (0.0, "4A7B47", "rgb"),
            (0.3, "8BC34A", "rgb"),
            (0.6, "FDD835", "rgb"),
            (1.0, "4A7B47", "rgb"),
        ],
    },
    "subnautica": {
        "label": "Subnautica",
        "stops": [
            (0.0, "003366", "rgb"),
            (0.3, "0066CC", "hsv"),
            (0.6, "00CCFF", "hsv"),
            (0.85, "00FFAA", "hsv"),
            (1.0, "003366", "rgb"),
        ],
    },
    "tf2": {
        "label": "Team Fortress 2",
        "stops": [
            (0.0, "B83C00", "rgb"),
            (0.3, "FF6600", "rgb"),
            (0.7, "5B8C5A", "rgb"),
            (1.0, "B83C00", "rgb"),
        ],
    },
    # ── New additions ──────────────────────────────────────────────
    "baldurs_gate3": {
        "label": "Baldur's Gate 3",
        "stops": [
            (0.0, "1A0033", "rgb"),
            (0.3, "660099", "hsv"),
            (0.6, "CC44FF", "hsv"),
            (0.85, "FF88FF", "rgb"),
            (1.0, "1A0033", "rgb"),
        ],
    },
    "hades": {
        "label": "Hades",
        "stops": [
            (0.0, "8B0000", "rgb"),
            (0.3, "FF2200", "rgb"),
            (0.6, "FF8C00", "rgb"),
            (0.85, "FF4400", "rgb"),
            (1.0, "8B0000", "rgb"),
        ],
    },
    "hades2": {
        "label": "Hades II",
        "stops": [
            (0.0, "0D001A", "rgb"),
            (0.3, "440066", "hsv"),
            (0.6, "9900CC", "hsv"),
            (0.85, "FF66FF", "hsv"),
            (1.0, "0D001A", "rgb"),
        ],
    },
    "god_of_war": {
        "label": "God of War",
        "stops": [
            (0.0, "1A0505", "rgb"),
            (0.4, "8B1A1A", "rgb"),
            (0.7, "CC0000", "rgb"),
            (1.0, "1A0505", "rgb"),
        ],
    },
    "horizon": {
        "label": "Horizon Zero Dawn",
        "stops": [
            (0.0, "1A3300", "rgb"),
            (0.3, "CC6600", "rgb"),
            (0.6, "FFAA00", "rgb"),
            (0.85, "66FF00", "rgb"),
            (1.0, "1A3300", "rgb"),
        ],
    },
    "disco_elysium": {
        "label": "Disco Elysium",
        "stops": [
            (0.0, "0A0A0F", "rgb"),
            (0.3, "1A1A4F", "rgb"),
            (0.6, "4444AA", "hsv"),
            (0.85, "AAAAFF", "rgb"),
            (1.0, "0A0A0F", "rgb"),
        ],
    },
    "minecraft": {
        "label": "Minecraft",
        "stops": [
            (0.0, "4A7B47", "rgb"),
            (0.3, "885A34", "rgb"),
            (0.6, "7CB342", "rgb"),
            (1.0, "4A7B47", "rgb"),
        ],
    },
    "among_us": {
        "label": "Among Us",
        "stops": [
            (0.0, "C51111", "rgb"),
            (0.25, "1D67A4", "rgb"),
            (0.5, "4CAF50", "rgb"),
            (0.75, "ECC94B", "rgb"),
            (1.0, "C51111", "rgb"),
        ],
    },
    "returnal": {
        "label": "Returnal",
        "stops": [
            (0.0, "00FF88", "hsv"),
            (0.4, "00FFFF", "hsv"),
            (0.7, "8800FF", "hsv"),
            (1.0, "00FF88", "hsv"),
        ],
    },
    "alan_wake2": {
        "label": "Alan Wake 2",
        "stops": [
            (0.0, "000011", "rgb"),
            (0.3, "001144", "rgb"),
            (0.6, "FFEE44", "rgb"),
            (0.85, "FFFFFF", "rgb"),
            (1.0, "000011", "rgb"),
        ],
    },
    "wukong": {
        "label": "Black Myth: Wukong",
        "stops": [
            (0.0, "1A0A00", "rgb"),
            (0.3, "CC6600", "rgb"),
            (0.6, "FFD700", "rgb"),
            (0.85, "CC4400", "rgb"),
            (1.0, "1A0A00", "rgb"),
        ],
    },
}

# Steam title substring → game id. Checked case-insensitively.
# Longer / more specific strings must come first.
_ALIASES = [
    ("balatro",              "balatro"),
    ("blue prince",          "blue_prince"),
    ("counter-strike 2",     "cs2"),
    ("counter-strike",       "cs2"),
    ("cyberpunk 2077",       "cyberpunk"),
    ("deadlock",             "deadlock"),
    ("elden ring",           "elden_ring"),
    ("forza horizon",        "forza"),
    ("grand theft auto v",   "gta5"),
    ("gta v",                "gta5"),
    ("half-life 2",          "half_life_2"),
    ("half-life",            "half_life"),
    ("hollow knight: silksong", "silksong"),
    ("hollow knight",        "hollow_knight"),
    ("neon white",           "neon_white"),
    ("portal 2",             "portal2"),
    ("portal",               "portal"),
    ("red dead redemption 2","rdr2"),
    ("red dead redemption",  "rdr"),
    ("stardew valley",       "stardew"),
    ("subnautica",           "subnautica"),
    ("team fortress 2",      "tf2"),
    ("baldur's gate 3",      "baldurs_gate3"),
    ("baldur",               "baldurs_gate3"),
    ("hades ii",             "hades2"),
    ("hades 2",              "hades2"),
    ("hades",                "hades"),
    ("god of war",           "god_of_war"),
    ("horizon zero dawn",    "horizon"),
    ("disco elysium",        "disco_elysium"),
    ("minecraft",            "minecraft"),
    ("among us",             "among_us"),
    ("returnal",             "returnal"),
    ("alan wake 2",          "alan_wake2"),
    ("black myth",           "wukong"),
    ("wukong",               "wukong"),
]


def match(title):
    """Map a Steam game title to a palette id, or None if no match."""
    if not title:
        return None
    t = title.lower()
    for alias, game_id in _ALIASES:
        if alias in t:
            return game_id
    return None


def sample(game_id, n):
    """Render a game palette across n pixels."""
    game = GAMES.get(game_id, GAMES["deadlock"])
    return ramp(game["stops"], n)


def animate(game_id, t, n):
    """Time-varying render for games that support animation. Returns None for static."""
    game = GAMES.get(game_id)
    if not game or not game.get("animated"):
        return None
    if game_id == "balatro":
        return _balatro(t, n)
    return None


def _balatro(t, n):
    """Balatro: cycling red/orange/purple that ebbs and flows like a flush."""
    out = []
    for i in range(n):
        phase = (i / n + t * 0.1) % 1.0
        # Three-color cycle: red → orange → purple
        p3 = (phase * 3) % 3
        if p3 < 1.0:
            c = lerp(from_hex("FF1744"), from_hex("FF6D00"), p3)
        elif p3 < 2.0:
            c = lerp(from_hex("FF6D00"), from_hex("AA00FF"), p3 - 1.0)
        else:
            c = lerp(from_hex("AA00FF"), from_hex("FF1744"), p3 - 2.0)
        v = 0.7 + 0.3 * math.sin(t * 1.2 + i * 0.4)
        out.append(scale(c, v))
    return out


def options():
    """Dropdown list for the Static effect "game" submenu."""
    order = [
        "balatro", "baldurs_gate3", "blue_prince", "cs2", "cyberpunk",
        "deadlock", "disco_elysium", "elden_ring", "forza", "god_of_war",
        "gta5", "half_life", "half_life_2", "hades", "hades2",
        "hollow_knight", "silksong", "horizon", "minecraft", "among_us",
        "neon_white", "portal", "portal2", "rdr", "rdr2",
        "returnal", "stardew", "subnautica", "tf2", "alan_wake2", "wukong",
    ]
    return [{"value": k, "label": GAMES[k]["label"]}
            for k in order if k in GAMES]


def label_for(game_id):
    game = GAMES.get(game_id)
    return game["label"] if game else game_id
