"""Effects.

Two primary effects, deliberately: Animated (anything that moves) and Static
(anything that doesn't). Everything the user picks is a parameter of one of
those, rather than a top-level entry. That keeps the effect dropdown short
and puts related choices next to each other.

Additional special-purpose effects: Fire, Rain, CpuLoad, AudioReactive.

Each effect declares its own parameters including show_if conditions.
The frontend builds controls from that metadata — adding a new effect
needs no TypeScript changes.

An effect implements render(t, n, p) -> list of n rgb tuples, where t is
seconds since the effect started and p is the live parameter dict.
"""

import math
import os
import subprocess
import threading
import time

from .color import (BLACK, PALETTE_GAMMA, PALETTE_SAT, deepen, from_hex,
                    gamma, hsv, lerp, saturate, scale)
from .flags import options as flag_options
from .flags import sample as flag_sample
from .games import animate as game_animate
from .games import options as game_options
from .games import sample as game_sample
from .scroll import colors_for as scroll_colors
from .scroll import options as scroll_options


# ── parameter descriptors ────────────────────────────────────────────────────

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
    """Show a parameter only when all conditions hold.

    Conditions are (key, op, value) with op in "eq", "ne", "gte", "in".
    Evaluated in the frontend from this metadata.
    """
    spec = dict(spec)
    spec["show_if"] = [{"key": k, "op": op, "value": v}
                       for k, op, v in conditions]
    return spec


def palette_bar(pixels, stretch=True):
    """Apply gamma + saturation to a pixel list for palette-style rendering."""
    src = deepen(pixels) if stretch else pixels
    return [gamma(saturate(c, PALETTE_SAT), g=PALETTE_GAMMA) for c in src]


# ── base ─────────────────────────────────────────────────────────────────────

class Effect:
    id = "base"
    label = "Base"
    description = ""
    params: list = []
    fps = 60
    static = False  # static effects paint once and idle

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
            {"value": "game",   "label": "Game palette"},
        ]),
        only_if(color("color", "Color", "1A9FFF"), ("mode", "eq", "color")),
        only_if(select("preset", "Colors", "sunset",
                       scroll_options(include_custom=False)),
                ("mode", "eq", "preset")),
        only_if(slider("spread", "Hue spread", 1.0, 0.2, 3.0, 0.1),
                ("mode", "eq", "preset"), ("preset", "eq", "rainbow")),
        only_if(select("flag", "Flag", "uk", _flag_menu()),
                ("mode", "eq", "flag")),
        only_if(slider("size", "Eye size", 1.6, 1.0, 5.0, 0.2, "px"),
                ("mode", "eq", "flag"), ("flag", "eq", HAL_ID)),
        only_if(slider("halo", "Halo", 0.12, 0.0, 0.5, 0.02),
                ("mode", "eq", "flag"), ("flag", "eq", HAL_ID)),
        only_if(select("game", "Game", "deadlock", game_options()),
                ("mode", "eq", "game")),
    ]

    def __init__(self):
        self._key = None
        self._cache = None

    def render(self, t, n, p):
        mode = p["mode"]

        if mode == "game":
            # Check for animated palette first (e.g. Balatro)
            live = game_animate(p.get("game", "deadlock"), t, n)
            if live is not None:
                return palette_bar(live, stretch=False)

        key = (mode, n, p.get("flag"), p.get("game"), p.get("color"),
               p.get("preset"), p.get("spread"))
        if key != self._key:
            if mode == "flag":
                if p["flag"] == HAL_ID:
                    self._cache = _hal(n, "FF0A0A", p.get("size", 1.6),
                                       p.get("halo", 0.12))
                else:
                    self._cache = palette_bar(flag_sample(p["flag"], n))
            elif mode == "game":
                self._cache = palette_bar(
                    game_sample(p.get("game", "deadlock"), n))
            elif mode == "preset":
                self._cache = palette_bar(_preset_bar(p, n), stretch=False)
            else:
                self._cache = [gamma(from_hex(p["color"]))] * n
            self._key = key
        return self._cache


# ── animated ──────────────────────────────────────────────────────────────────

MOTIONS = [
    {"value": "scroll",       "label": "Scroll Right"},
    {"value": "scroll_left",  "label": "Scroll Left"},
    {"value": "pulse",        "label": "Outward Pulse"},
    {"value": "split",        "label": "Inward Pulse"},
    {"value": "bounce",       "label": "Bounce"},
    {"value": "fade",         "label": "Crossfade"},
    {"value": "breathe",      "label": "Breathe"},
    {"value": "scanner",      "label": "Scanner"},
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
                u = (center - abs(i - center)) / max(1e-6, center) \
                    - phase * 2.0
            elif motion == "scroll_left":
                u = x + phase
            else:
                u = x - phase
            out.append(gamma(self._at(u, rgb, soft)))
        return out


# ── fire ─────────────────────────────────────────────────────────────────────

class Fire(Effect):
    id = "fire"
    label = "Fire"
    description = "Heat simulation — sparks ignite at one end and cool toward the other."
    fps = 30
    params = [
        slider("cooling", "Cooling", 0.08, 0.02, 0.25, 0.01),
        slider("sparking", "Sparking", 0.7, 0.2, 1.0, 0.05),
        select("colour", "Colour", "classic", [
            {"value": "classic", "label": "Classic fire"},
            {"value": "blue",    "label": "Blue flame"},
            {"value": "green",   "label": "Toxic"},
            {"value": "purple",  "label": "Magical"},
        ]),
    ]

    def __init__(self):
        self._heat = None

    @staticmethod
    def _palette(v, colour):
        """Map heat value 0-1 to an RGB colour."""
        if colour == "blue":
            if v < 0.5:
                return (0.0, 0.0, v * 2)
            else:
                t = (v - 0.5) * 2
                return (t * 0.8, t * 0.9, 1.0)
        if colour == "green":
            if v < 0.5:
                return (0.0, v * 2, 0.0)
            else:
                t = (v - 0.5) * 2
                return (t * 0.8, 1.0, t * 0.8)
        if colour == "purple":
            if v < 0.5:
                return (v * 1.4, 0.0, v * 2)
            else:
                t = (v - 0.5) * 2
                return (0.7 + t * 0.3, t * 0.8, 1.0)
        # classic: black → red → orange → yellow → white
        if v < 0.33:
            return (v / 0.33, 0.0, 0.0)
        elif v < 0.66:
            t = (v - 0.33) / 0.33
            return (1.0, t, 0.0)
        else:
            t = (v - 0.66) / 0.34
            return (1.0, 1.0, t)

    def render(self, t, n, p):
        import random

        if self._heat is None or len(self._heat) != n:
            self._heat = [0.0] * n

        cooling = p["cooling"]
        sparking = p["sparking"]
        colour = p["colour"]

        # Cool each cell
        for i in range(n):
            self._heat[i] = max(0.0, self._heat[i] - cooling * random.random())

        # Diffuse upward (toward index 0 = start of bar)
        for i in range(n - 1, 1, -1):
            self._heat[i] = (self._heat[i] * 0.5 +
                             self._heat[i - 1] * 0.3 +
                             self._heat[i - 2] * 0.2)

        # Randomly ignite sparks near the base (end of bar)
        if random.random() < sparking:
            cell = n - 1 - int(random.random() * max(1, n // 5))
            self._heat[cell] = min(1.0, self._heat[cell] + random.random() * 0.6 + 0.3)

        return [gamma(self._palette(self._heat[i], colour)) for i in range(n)]


# ── rain ─────────────────────────────────────────────────────────────────────

class Rain(Effect):
    id = "rain"
    label = "Rain"
    description = "Drips fall from one end of the bar and fade as they travel."
    fps = 30
    params = [
        slider("density",     "Density",     0.4,  0.1, 1.0, 0.05),
        slider("tail_length", "Tail length", 0.5,  0.2, 0.9, 0.05),
        slider("speed",       "Speed",       1.0,  0.3, 3.0, 0.1, "x"),
        color("drop_color",   "Color",       "00CCFF"),
    ]

    def __init__(self):
        self._drops = []  # list of (position_float, brightness)
        self._next_drop = 0.0
        self._last_t = 0.0

    def render(self, t, n, p):
        import random

        dt = max(0.0, min(0.1, t - self._last_t))
        self._last_t = t

        speed = p["speed"]
        density = p["density"]
        tail = p["tail_length"]
        base_rgb = gamma(from_hex(p["drop_color"]))

        # Spawn new drops
        self._next_drop -= dt
        if self._next_drop <= 0.0:
            self._drops.append([0.0, 1.0])
            interval = 0.3 / max(0.01, density)
            self._next_drop = interval * (0.5 + random.random() * 0.5)

        # Advance drops
        advance = speed * 8.0 * dt
        self._drops = [[pos + advance, br] for pos, br in self._drops
                       if pos < n + 2]

        # Build pixel buffer
        buf = [[0.0, 0.0, 0.0] for _ in range(n)]
        for pos, br in self._drops:
            for j in range(n):
                d = abs(j - pos)
                if d <= 0.5:
                    intensity = br
                elif d < tail * n * 0.5:
                    intensity = br * (1.0 - d / (tail * n * 0.5)) ** 2
                else:
                    continue
                for c in range(3):
                    buf[j][c] = min(1.0, buf[j][c] + base_rgb[c] * intensity)

        return [tuple(px) for px in buf]


# ── cpu load ─────────────────────────────────────────────────────────────────

class CpuLoad(Effect):
    id = "cpu_load"
    label = "CPU Load"
    description = "Bar fills left-to-right with CPU usage. Green → yellow → red."
    fps = 10
    static = False
    params = [
        slider("poll_ms", "Update interval", 500, 200, 2000, 100, "ms"),
    ]

    def __init__(self):
        self._load = 0.0
        self._last_read = 0.0
        self._prev_idle = None
        self._prev_total = None

    def _read_cpu(self):
        """Read /proc/stat and return CPU usage fraction 0-1."""
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            fields = [int(x) for x in line.split()[1:]]
            idle = fields[3]
            total = sum(fields)
            if self._prev_total is None:
                self._prev_idle = idle
                self._prev_total = total
                return 0.0
            d_idle = idle - self._prev_idle
            d_total = total - self._prev_total
            self._prev_idle = idle
            self._prev_total = total
            if d_total == 0:
                return 0.0
            return max(0.0, min(1.0, 1.0 - d_idle / d_total))
        except (OSError, IndexError, ValueError):
            return 0.0

    def render(self, t, n, p):
        poll = p["poll_ms"] / 1000.0
        if t - self._last_read >= poll:
            self._load = self._read_cpu()
            self._last_read = t

        filled = int(round(self._load * n))
        out = []
        for i in range(n):
            if i >= filled:
                out.append(BLACK)
                continue
            frac = i / max(1, n - 1)
            # green (0, 1, 0) → yellow (1, 1, 0) → red (1, 0, 0)
            if frac < 0.5:
                c = lerp((0.0, 1.0, 0.0), (1.0, 1.0, 0.0), frac * 2)
            else:
                c = lerp((1.0, 1.0, 0.0), (1.0, 0.0, 0.0), (frac - 0.5) * 2)
            out.append(gamma(c))
        return out


# ── audio reactive ────────────────────────────────────────────────────────────

class AudioReactive(Effect):
    id = "audio_reactive"
    label = "Audio Reactive"
    description = "Pulses brightness to the audio output level via PulseAudio/PipeWire."
    fps = 30
    params = [
        slider("sensitivity", "Sensitivity", 1.0, 0.2, 5.0, 0.1),
        select("preset", "Colors", "sunset", scroll_options(include_custom=False)),
        select("mode", "Mode", "pulse", [
            {"value": "pulse",   "label": "Brightness pulse"},
            {"value": "fill",    "label": "Fill bar"},
            {"value": "breathe", "label": "Colour shift"},
        ]),
    ]

    # Shared state across all instances — one background reader thread.
    _level = 0.0
    _reader_thread = None
    _reader_lock = threading.Lock()
    _stop_reader = False

    @classmethod
    def _ensure_reader(cls):
        with cls._reader_lock:
            if cls._reader_thread is not None and cls._reader_thread.is_alive():
                return
            cls._stop_reader = False
            t = threading.Thread(target=cls._reader_loop, daemon=True)
            t.start()
            cls._reader_thread = t

    @classmethod
    def _reader_loop(cls):
        """Poll pactl for sink peak level every ~50ms."""
        while not cls._stop_reader:
            try:
                result = subprocess.run(
                    ["pactl", "get-sink-peak", "0"],
                    capture_output=True, text=True, timeout=0.5
                )
                val = float(result.stdout.strip())
                cls._level = max(0.0, min(1.0, val))
            except Exception:
                cls._level = 0.0
            time.sleep(0.05)

    def __init__(self):
        self._ensure_reader()
        self._smooth = 0.0

    def render(self, t, n, p):
        raw = AudioReactive._level * p["sensitivity"]
        raw = max(0.0, min(1.0, raw))
        # Smooth: fast attack, slow decay
        if raw > self._smooth:
            self._smooth = self._smooth * 0.3 + raw * 0.7
        else:
            self._smooth = self._smooth * 0.85 + raw * 0.15
        v = self._smooth

        cols = scroll_colors(p["preset"], 1.0)
        if not cols:
            cols = ["FF3030", "FF8800"]
        rgb = [from_hex(c) for c in cols]
        m = len(rgb)

        mode = p["mode"]
        out = []

        if mode == "fill":
            filled = int(round(v * n))
            for i in range(n):
                if i < filled:
                    idx = int((i / max(1, n - 1)) * (m - 1))
                    out.append(gamma(rgb[min(idx, m - 1)]))
                else:
                    out.append(BLACK)
        elif mode == "breathe":
            hue_phase = t * 0.1
            for i in range(n):
                from .color import hsv as _hsv
                h = (hue_phase + i / n * 0.3) % 1.0
                c = _hsv(h, 0.9, v)
                out.append(gamma(c))
        else:  # pulse
            base_idx = int((t * 0.1) % 1.0 * m)
            c = rgb[base_idx % m]
            out = [scale(gamma(c), v)] * n

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

REGISTRY = {e.id: e for e in [
    Animated, Static, Fire, Rain, CpuLoad, AudioReactive, Off
]}

ORDER = ["animated", "static", "fire", "rain", "cpu_load", "audio_reactive", "off"]


def catalog():
    return [REGISTRY[i].describe() for i in ORDER if i in REGISTRY]


def build(effect_id):
    cls = REGISTRY.get(effect_id) or REGISTRY["off"]
    return cls()
