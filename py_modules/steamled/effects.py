"""Effects — Animated, Static, Off.

Each effect declares its own parameters including show_if conditions.
The frontend builds controls from that metadata — no TypeScript changes
needed when adding a new parameter.

render(t, n, p) -> list of n rgb tuples. t is seconds since the effect
started, p is the live parameter dict.
"""

import math
import random
import struct
import subprocess
import threading
import time

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


# ── fire ─────────────────────────────────────────────────────────────────────

_FIRE_PALETTES = {
    "classic": [(0.0, (0,0,0)), (0.3, (1,0,0)), (0.6, (1,0.5,0)), (0.85, (1,1,0)), (1.0, (1,1,1))],
    "blue":    [(0.0, (0,0,0)), (0.3, (0,0,1)), (0.6, (0,0.5,1)), (0.85, (0,1,1)), (1.0, (1,1,1))],
    "toxic":   [(0.0, (0,0,0)), (0.3, (0,0.4,0)), (0.6, (0.4,1,0)), (0.85, (1,1,0)), (1.0, (1,1,1))],
    "magical": [(0.0, (0,0,0)), (0.3, (0.5,0,1)), (0.6, (1,0,0.5)), (0.85, (1,0.5,1)), (1.0, (1,1,1))],
}


def _fire_color(h, stops):
    h = max(0.0, min(1.0, h))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if h <= t1:
            f = (h - t0) / max(1e-9, t1 - t0)
            return tuple(c0[j] + (c1[j] - c0[j]) * f for j in range(3))
    return stops[-1][1]


class Fire(Effect):
    id = "fire"
    label = "Fire"
    description = "Heat simulation that rises along the bar."
    fps = 30
    params = [
        select("palette", "Colour", "classic", [
            {"value": "classic", "label": "Classic"},
            {"value": "blue",    "label": "Blue"},
            {"value": "toxic",   "label": "Toxic"},
            {"value": "magical", "label": "Magical"},
        ]),
        slider("cooling",  "Cooling",  0.5, 0.1, 1.0, 0.05),
        slider("sparking", "Sparking", 0.7, 0.1, 1.0, 0.05),
    ]

    def __init__(self):
        self._heat = None

    def render(self, t, n, p):
        if self._heat is None or len(self._heat) != n:
            self._heat = [0.0] * n

        heat = self._heat
        cooling = p["cooling"]
        sparking = p["sparking"]

        # Cool every cell
        for i in range(n):
            heat[i] = max(0.0, heat[i] - random.uniform(0, cooling * 0.15))

        # Heat rises: diffuse toward the far end
        for i in range(n - 1, 1, -1):
            heat[i] = heat[i - 1] * 0.3 + heat[i - 2] * 0.2 + heat[i] * 0.5

        # Ignite sparks at the base
        if random.random() < sparking:
            idx = random.randint(0, min(2, n - 1))
            heat[idx] = min(1.0, heat[idx] + random.uniform(0.5, 1.0))

        stops = _FIRE_PALETTES.get(p["palette"], _FIRE_PALETTES["classic"])
        return [gamma(_fire_color(h, stops)) for h in heat]


# ── rain ─────────────────────────────────────────────────────────────────────

_RAIN_COLOURS = {
    "cyan":   (0.0, 1.0, 1.0),
    "white":  (1.0, 1.0, 1.0),
    "purple": (0.7, 0.0, 1.0),
    "green":  (0.0, 1.0, 0.2),
}


class Rain(Effect):
    id = "rain"
    label = "Rain"
    description = "Droplets travel along the bar and fade."
    fps = 30
    params = [
        select("colour", "Colour", "cyan", [
            {"value": "cyan",   "label": "Cyan"},
            {"value": "white",  "label": "White"},
            {"value": "purple", "label": "Purple"},
            {"value": "green",  "label": "Green"},
        ]),
        slider("density",  "Density",     0.3, 0.05, 1.0,  0.05),
        slider("speed",    "Speed",       1.0, 0.2,  3.0,  0.1, "x"),
        slider("tail",     "Tail length", 0.7, 0.2,  0.95, 0.05),
    ]

    def __init__(self):
        self._drops = []
        self._buf = None
        self._last_t = 0.0
        self._spawn_acc = 0.0

    def render(self, t, n, p):
        if self._buf is None or len(self._buf) != n:
            self._buf = [BLACK] * n
            self._drops = []
            self._last_t = t

        dt = max(0.0, min(0.1, t - self._last_t))
        self._last_t = t

        speed   = p["speed"]
        tail    = p["tail"]
        density = p["density"]
        colour  = _RAIN_COLOURS.get(p["colour"], _RAIN_COLOURS["cyan"])

        # Decay
        self._buf = [tuple(c * tail for c in px) for px in self._buf]

        # Move drops
        step = speed * dt * n * 0.3
        self._drops = [d + step for d in self._drops if d + step < n]

        # Spawn
        self._spawn_acc += density * speed * dt * 2.0
        while self._spawn_acc >= 1.0:
            self._spawn_acc -= 1.0
            self._drops.append(0.0)

        # Paint
        buf = list(self._buf)
        for d in self._drops:
            i = int(d)
            if 0 <= i < n:
                buf[i] = tuple(max(buf[i][j], colour[j]) for j in range(3))
        self._buf = buf

        return [gamma(px) for px in buf]


# ── cpu load — background reader ──────────────────────────────────────────────

class _CpuReader:
    _instance = None
    _inst_lock = threading.Lock()

    @classmethod
    def get(cls):
        with cls._inst_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._load = 0.0
        self._prev = None
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def load(self):
        with self._lock:
            return self._load

    def _read(self):
        try:
            with open("/proc/stat") as f:
                parts = f.readline().split()[1:]
            vals = list(map(int, parts))
            return sum(vals), vals[3]  # total, idle
        except Exception:
            return None

    def _run(self):
        while True:
            cur = self._read()
            if cur and self._prev:
                dt = cur[0] - self._prev[0]
                di = cur[1] - self._prev[1]
                with self._lock:
                    self._load = max(0.0, min(1.0, 1.0 - di / max(1, dt)))
            self._prev = cur
            time.sleep(0.5)


class CpuLoad(Effect):
    id = "cpu_load"
    label = "CPU Load"
    description = "Bar fills with CPU usage. Green → yellow → red."
    fps = 5
    params = [
        slider("floor", "Minimum lit", 0.0, 0.0, 0.5, 0.05),
    ]

    def render(self, t, n, p):
        load  = _CpuReader.get().load()
        floor = p["floor"]
        fill  = max(floor, load)
        lit   = max(1, int(round(fill * n)))

        out = []
        for i in range(n):
            if i >= lit:
                out.append(BLACK)
                continue
            x = i / max(1, n - 1)
            if x < 0.5:
                c = (x * 2, 1.0, 0.0)
            else:
                c = (1.0, 1.0 - (x - 0.5) * 2, 0.0)
            out.append(gamma(c))
        return out


# ── audio reactive — background pacat reader ──────────────────────────────────

class _AudioReader:
    _instance = None
    _inst_lock = threading.Lock()

    @classmethod
    def get(cls):
        with cls._inst_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._peak = 0.0
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def peak(self):
        with self._lock:
            v = self._peak
            self._peak *= 0.85  # natural decay between reads
            return v

    def _run(self):
        RATE  = 8000
        CHUNK = 800  # 100 ms of samples
        while True:
            try:
                proc = subprocess.Popen(
                    ["pacat", "--record",
                     "--device=@DEFAULT_MONITOR@",
                     "--channels=1",
                     "--format=s16le",
                     f"--rate={RATE}",
                     "--latency-msec=100"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                while True:
                    raw = proc.stdout.read(CHUNK * 2)
                    if not raw:
                        break
                    samples = struct.unpack(f"<{len(raw) // 2}h", raw[: len(raw) // 2 * 2])
                    if samples:
                        pk = max(abs(s) for s in samples) / 32768.0
                        with self._lock:
                            self._peak = max(self._peak, pk)
                proc.wait()
            except Exception:
                pass
            time.sleep(2.0)


_AUDIO_COLOURS = {
    "cyan":  (0.0, 1.0, 1.0),
    "white": (1.0, 1.0, 1.0),
    "fire":  (1.0, 0.3, 0.0),
}


class AudioReactive(Effect):
    id = "audio"
    label = "Audio Reactive"
    description = "Pulses to the audio output level. Requires pacat (SteamOS default)."
    fps = 30
    params = [
        select("mode", "Mode", "pulse", [
            {"value": "pulse",  "label": "Brightness pulse"},
            {"value": "fill",   "label": "Fill bar"},
            {"value": "shift",  "label": "Colour shift"},
        ]),
        select("colour", "Colour", "cyan", [
            {"value": "cyan",    "label": "Cyan"},
            {"value": "white",   "label": "White"},
            {"value": "fire",    "label": "Fire"},
            {"value": "rainbow", "label": "Rainbow"},
        ]),
        slider("sensitivity", "Sensitivity", 1.0, 0.2, 4.0, 0.1, "x"),
        slider("floor",       "Minimum",     0.05, 0.0, 0.5, 0.02),
    ]

    def _base_colour(self, key, t):
        if key == "rainbow":
            h6 = (t * 0.1 % 1.0) * 6
            x  = 1 - abs(h6 % 2 - 1)
            i  = int(h6) % 6
            return [(1,x,0),(x,1,0),(0,1,x),(0,x,1),(x,0,1),(1,0,x)][i]
        return _AUDIO_COLOURS.get(key, _AUDIO_COLOURS["cyan"])

    def render(self, t, n, p):
        raw   = _AudioReader.get().peak()
        level = min(1.0, raw * p["sensitivity"])
        level = max(p["floor"], level)
        base  = self._base_colour(p["colour"], t)
        mode  = p["mode"]

        if mode == "fill":
            lit = max(1, int(round(level * n)))
            return [gamma(base) if i < lit else BLACK for i in range(n)]

        if mode == "shift":
            comp = tuple(1.0 - c for c in base)
            c = tuple(base[j] + (comp[j] - base[j]) * level for j in range(3))
            return [gamma(scale(c, 0.8 + 0.2 * level))] * n

        # pulse (default)
        return [gamma(scale(base, level))] * n


# ── registry ──────────────────────────────────────────────────────────────────

REGISTRY = {e.id: e for e in [Animated, Static, Fire, Rain, CpuLoad, AudioReactive, Off]}
ORDER = ["animated", "static", "fire", "rain", "cpu_load", "audio", "off"]


def catalog():
    return [REGISTRY[i].describe() for i in ORDER if i in REGISTRY]


def build(effect_id):
    cls = REGISTRY.get(effect_id) or REGISTRY["off"]
    return cls()
