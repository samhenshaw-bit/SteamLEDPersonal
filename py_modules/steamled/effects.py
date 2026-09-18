"""Effects — Animated, Static, Off.

Each effect declares its own parameters including show_if conditions.
The frontend builds controls from that metadata — no TypeScript changes
needed when adding a new parameter.

render(t, n, p) -> list of n rgb tuples. t is seconds since the effect
started, p is the live parameter dict.
"""

import math

from .color import (BLACK, PALETTE_GAMMA, PALETTE_SAT, deepen, from_hex,
                    gamma, saturate, scale)
from .flags import options as flag_options
from .flags import sample as flag_sample
from .games import animate as game_animate
from .games import sample as game_sample
from .scroll import colors_for as scroll_colors
from .scroll import options as scroll_options


# ── parameter descriptors ─────────────────────────────────────────────────────

def slider(key, label, default, lo, hi, step=0.1, unit=""):
    return {"key": key, "label": label, "type": "slider", "default": default,
            "min": lo, "max": hi, "step": step, "unit": unit}


def color(key, label, default):
    return {"key": key, "label": label, "type": "color", "default": default}


def toggle(key, label, default):
    return {"key": key, "label": label, "type": "toggle", "default": default}


def select(key, label, default, options):
    return {"key": key, "label": label, "type": "select", "default": default,
            "options": options}


def only_if(spec, *conditions):
    spec = dict(spec)
    spec["show_if"] = [{"key": k, "op": op, "value": v}
                       for k, op, v in conditions]
    return spec


def palette_bar(pixels, stretch=True):
    src = deepen(pixels) if stretch else pixels
    return [gamma(saturate(c, PALETTE_SAT), g=PALETTE_GAMMA) for c in src]


# ── base ──────────────────────────────────────────────────────────────────────

class Effect:
    id = "base"
    label = "Base"
    description = ""
    params: list = []
    fps = 60
    static = False

    def render(self, t, n, p):
        raise NotImplementedError

    @classmethod
    def defaults(cls):
        return {d["key"]: d["default"] for d in cls.params}

    @classmethod
    def describe(cls):
        return {"id": cls.id, "label": cls.label,
                "description": cls.description, "params": cls.params}


# ── static ────────────────────────────────────────────────────────────────────

HAL_ID = "hal"


def _flag_menu():
    return flag_options() + [{"value": HAL_ID, "label": "HAL 9000"}]


def _hal(n, hex_color, size, halo):
    center = (n - 1) / 2.0
    base = gamma(from_hex(hex_color))
    radius = max(1.0, size / 2.0)
    out = []
    for i in range(n):
        d = abs(i - center)
        if d <= radius:
            w = 1.0 - (d / radius) * 0.35
        else:
            w = halo * max(0.0, 1.0 - (d - radius) / 2.5) ** 2
        out.append(scale(base, w) if w > 0.001 else BLACK)
    return out


def _preset_bar(p, n):
    cols = scroll_colors(p["preset"], p.get("spread", 1.0))
    if not cols:
        cols = ["FF3030", "3080FF"]
    rgb = [from_hex(c) for c in cols]
    m = len(rgb)
    out = []
    for i in range(n):
        f = (i / n) * m
        a = int(f) % m
        w = f - int(f)
        b = rgb[(a + 1) % m]
        out.append(tuple(rgb[a][j] + (b[j] - rgb[a][j]) * w for j in range(3)))
    return out


class Static(Effect):
    id = "static"
    label = "Static"
    description = "A fixed picture on the bar."
    static = True
    params = [
        select("mode", "Show", "color", [
            {"value": "color",  "label": "Solid color"},
            {"value": "preset", "label": "Colors"},
            {"value": "flag",   "label": "Flag"},
        ]),
        only_if(color("color", "Color", "1A9FFF"), ("mode", "eq", "color")),
        only_if(select("preset", "Colors", "sunset",
                       scroll_options(include_custom=False)),
                ("mode", "eq", "preset")),
        only_if(slider("spread", "Hue spread", 1.0, 0.2, 3.0, 0.1),
                ("mode", "eq", "preset"), ("preset", "eq", "rainbow")),
        only_if(select("flag", "Flag", "us", _flag_menu()),
                ("mode", "eq", "flag")),
        only_if(slider("size", "Eye size", 1.6, 1.0, 5.0, 0.2, "px"),
                ("mode", "eq", "flag"), ("flag", "eq", HAL_ID)),
        only_if(slider("halo", "Halo", 0.12, 0.0, 0.5, 0.02),
                ("mode", "eq", "flag"), ("flag", "eq", HAL_ID)),
    ]

    def __init__(self):
        self._key = None
        self._cache = None

    def render(self, t, n, p):
        mode = p["mode"]

        if mode == "game":
            live = game_animate(p.get("game", "deadlock"), t, n)
            if live is not None:
                return palette_bar(live, stretch=False)

        if mode == "flag" and p.get("flag") == HAL_ID:
            key = ("hal", n, p.get("size", 1.6), p.get("halo", 0.12))
            if key != self._key:
                self._cache = _hal(n, "FF0A0A", p.get("size", 1.6), p.get("halo", 0.12))
                self._key = key
            return self._cache

        key = (mode, n, p.get("flag"), p.get("game"), p.get("color"),
               p.get("preset"), p.get("spread"))
        if key != self._key:
            if mode == "flag":
                self._cache = palette_bar(flag_sample(p["flag"], n))
            elif mode == "game":
                self._cache = palette_bar(game_sample(p.get("game", "deadlock"), n))
            elif mode == "preset":
                self._cache = palette_bar(_preset_bar(p, n), stretch=False)
            else:
                self._cache = [gamma(from_hex(p.get("color", "1A9FFF")))] * n
            self._key = key
        return self._cache


# ── animated ──────────────────────────────────────────────────────────────────

MOTIONS = [
    {"value": "scroll",      "label": "Scroll Right"},
    {"value": "scroll_left", "label": "Scroll Left"},
    {"value": "pulse",       "label": "Outward Pulse"},
    {"value": "split",       "label": "Inward Pulse"},
    {"value": "bounce",      "label": "Bounce"},
    {"value": "fade",        "label": "Crossfade"},
    {"value": "breathe",     "label": "Breathe"},
    {"value": "scanner",     "label": "Scanner"},
]

_BANDED = ("scroll", "scroll_left", "pulse", "bounce", "split")


class Animated(Effect):
    id = "animated"
    label = "Animated"
    description = "Colors in motion."
    fps = 30
    params = [
        select("motion", "Motion", "scroll", MOTIONS),
        select("preset", "Colors", "sunset", scroll_options()),
        only_if(slider("spread", "Hue spread", 1.0, 0.2, 3.0, 0.1),
                ("preset", "eq", "rainbow")),
        only_if(slider("count", "How many colors", 4, 2, 6, 1),
                ("preset", "eq", "custom")),
        only_if(color("c1", "Color 1", "FF3030"), ("preset", "eq", "custom")),
        only_if(color("c2", "Color 2", "FFA030"), ("preset", "eq", "custom")),
        only_if(color("c3", "Color 3", "30D060"),
                ("preset", "eq", "custom"), ("count", "gte", 3)),
        only_if(color("c4", "Color 4", "3080FF"),
                ("preset", "eq", "custom"), ("count", "gte", 4)),
        only_if(color("c5", "Color 5", "9040E0"),
                ("preset", "eq", "custom"), ("count", "gte", 5)),
        only_if(color("c6", "Color 6", "FF40A0"),
                ("preset", "eq", "custom"), ("count", "gte", 6)),
        slider("speed", "Speed", 1.0, 0.1, 3.0, 0.1, "x"),
        only_if(slider("blend", "Blend", 0.7, 0.0, 1.0, 0.05),
                ("motion", "in", list(_BANDED))),
        only_if(slider("tail", "Tail length", 0.75, 0.3, 0.95, 0.05),
                ("motion", "eq", "scanner")),
        only_if(slider("floor", "Minimum", 0.06, 0.0, 0.5, 0.02),
                ("motion", "eq", "breathe")),
    ]

    def __init__(self):
        self.buf = None
        self.pos = 0.0
        self.dir = 1.0
        self.last_t = 0.0

    @staticmethod
    def _colors(p):
        cols = scroll_colors(p["preset"], p.get("spread", 1.0))
        if not cols:
            k = int(max(2, min(6, p.get("count", 4))))
            cols = [p[f"c{i + 1}"] for i in range(k)]
        return [from_hex(c) for c in cols]

    @staticmethod
    def _at(u, rgb, soft):
        m = len(rgb)
        f = (u % 1.0) * m
        a = int(f) % m
        frac = f - int(f)
        hold = 1.0 - soft
        if frac <= hold:
            return rgb[a]
        x = (frac - hold) / soft
        w = 0.5 - 0.5 * math.cos(math.pi * x)
        b = rgb[(a + 1) % m]
        return tuple(rgb[a][j] + (b[j] - rgb[a][j]) * w for j in range(3))

    def _breathe(self, t, n, p, rgb):
        c = self._at(-t * 0.06 * p["speed"], rgb, 1.0)
        period = 6.0 / max(0.1, p["speed"])
        v = (math.sin(2 * math.pi * t / period) + 1) / 2
        f = p["floor"]
        v = f + (1 - f) * (v ** 2)
        return [scale(gamma(c), v)] * n

    def _scanner(self, t, n, p, rgb):
        if self.buf is None or len(self.buf) != n:
            self.buf = [[0.0, 0.0, 0.0] for _ in range(n)]
        dt = max(0.0, min(0.1, t - self.last_t))
        self.last_t = t
        d = p["tail"]
        for px in self.buf:
            px[0] *= d
            px[1] *= d
            px[2] *= d
        self.pos += self.dir * 12.0 * p["speed"] * dt
        if self.pos >= n - 1:
            self.pos, self.dir = n - 1, -1.0
        elif self.pos <= 0:
            self.pos, self.dir = 0.0, 1.0
        c = self._at(self.pos / max(1, n - 1), rgb, 1.0)
        i = int(self.pos)
        if 0 <= i < n:
            for k in range(3):
                self.buf[i][k] = max(self.buf[i][k], c[k])
        return [gamma(tuple(px)) for px in self.buf]

    def render(self, t, n, p):
        motion = p["motion"]
        rgb = self._colors(p)
        if len(rgb) == 1:
            return [gamma(rgb[0])] * n
        if motion == "breathe":
            return self._breathe(t, n, p, rgb)
        if motion == "scanner":
            return self._scanner(t, n, p, rgb)

        soft = max(0.001, p["blend"]) if motion in _BANDED else 1.0
        phase = t * 0.12 * p["speed"]
        center = (n - 1) / 2.0

        out = []
        for i in range(n):
            x = i / n
            if motion == "pulse":
                u = abs(i - center) / max(1e-6, center) - phase * 2.0
            elif motion == "bounce":
                tri = abs(((phase * 2.0) % 2.0) - 1.0)
                u = x - tri
            elif motion == "fade":
                u = -phase
            elif motion == "split":
                u = (center - abs(i - center)) / max(1e-6, center) - phase * 2.0
            elif motion == "scroll_left":
                u = x + phase
            else:
                u = x - phase
            out.append(gamma(self._at(u, rgb, soft)))
        return out


# ── off ───────────────────────────────────────────────────────────────────────

class Off(Effect):
    id = "off"
    label = "Off"
    description = "Bar dark."
    static = True

    def render(self, t, n, p):
        return [BLACK] * n


# ── registry ──────────────────────────────────────────────────────────────────

REGISTRY = {e.id: e for e in [Animated, Static, Off]}
ORDER = ["animated", "static", "off"]


def catalog():
    return [REGISTRY[i].describe() for i in ORDER if i in REGISTRY]


def build(effect_id):
    cls = REGISTRY.get(effect_id) or REGISTRY["off"]
    return cls()
