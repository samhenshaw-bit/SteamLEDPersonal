"""Background render loop + settings persistence."""

import json
import os
import threading
import time

from . import effects as fx
from . import games as fx_games
from .strip import Strip, available

SETTINGS_VERSION = 5


class Engine:
    def __init__(self, settings_path=None, logger=None):
        self.settings_path = settings_path
        self.log = logger
        self._lock = threading.RLock()
        self._thread = None
        self._stop = threading.Event()

        self.strip = None
        self.effect = None
        self._override = None
        self._override_effect = None
        self.state = {
            "version": SETTINGS_VERSION,
            "enabled": False,
            "effect": "animated",
            "brightness": 1.0,
            "reverse": True,
            "now_playing": True,
            "params": {},
        }
        self._load()

    # ── settings ──────────────────────────────────────────────────────────────

    def _load(self):
        if not self.settings_path or not os.path.exists(self.settings_path):
            return
        try:
            with open(self.settings_path) as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                return
            keys = ["enabled", "effect", "brightness", "reverse", "now_playing"]
            if saved.get("version", 1) < SETTINGS_VERSION:
                keys.remove("reverse")
                self._warn("migrating settings; resetting orientation")
            for k in keys:
                if k in saved:
                    self.state[k] = saved[k]
            if self.state["effect"] not in fx.REGISTRY:
                self._warn(f"unknown saved effect {self.state['effect']!r}; using default")
                self.state["effect"] = "animated"
            self.state["version"] = SETTINGS_VERSION
            if isinstance(saved.get("params"), dict):
                self.state["params"] = self._prune(saved["params"])
        except Exception as e:
            self._warn(f"settings load failed: {e}")

    def _prune(self, saved_params):
        kept = {}
        for eid, vals in saved_params.items():
            cls = fx.REGISTRY.get(eid)
            if cls is None or not isinstance(vals, dict):
                continue
            valid = {d["key"] for d in cls.params}
            trimmed = {k: v for k, v in vals.items() if k in valid}
            if trimmed:
                kept[eid] = trimmed
        return kept

    def save(self):
        if not self.settings_path:
            return
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            tmp = self.settings_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.state, f, indent=2)
            os.replace(tmp, self.settings_path)
        except Exception as e:
            self._warn(f"settings save failed: {e}")

    def _warn(self, msg):
        if self.log:
            self.log.warning(f"[steamled] {msg}")

    def _info(self, msg):
        if self.log:
            self.log.info(f"[steamled] {msg}")

    # ── params ────────────────────────────────────────────────────────────────

    def params_for(self, effect_id):
        cls = fx.REGISTRY.get(effect_id)
        if not cls:
            return {}
        merged = cls.defaults()
        merged.update(self.state["params"].get(effect_id, {}))
        return merged

    def set_param(self, effect_id, key, value):
        with self._lock:
            self.state["params"].setdefault(effect_id, {})[key] = value
        self.save()

    # ── status ────────────────────────────────────────────────────────────────

    def status(self):
        return {
            "available": available(),
            "leds": self.strip.n if self.strip else 0,
            "enabled": self.state["enabled"],
            "effect": self.state["effect"],
            "brightness": self.state["brightness"],
            "reverse": self.state["reverse"],
            "now_playing": self.state["now_playing"],
            "playing": fx_games.label_for(self._override),
            "params": self.params_for(self.state["effect"]),
            "game_palette": self.state.get("game_palette"),
            "game_palette_app_id": self.state.get("game_palette_app_id"),
        }

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return True
            if not available():
                self._warn("no valve-leds present; not starting")
                return False
            self.strip = Strip(reverse=self.state["reverse"])
            self.strip.save()
            self.effect = fx.build(self.state["effect"])
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="steamled-render", daemon=True)
            self._thread.start()
            self.state["enabled"] = True
        self.save()
        self._info(f"started: {self.state['effect']}")
        return True

    def stop(self, restore=True, persist=True):
        with self._lock:
            self._stop.set()
            th = self._thread
            self._thread = None
        if th:
            th.join(timeout=2.0)
        with self._lock:
            if self.strip and restore:
                self.strip.restore()
            self.strip = None
            self.effect = None
            if persist:
                self.state["enabled"] = False
        if persist:
            self.save()
        self._info("stopped" if persist else "stopped (shutdown)")
        return True

    def autostart(self, timeout=90.0):
        """Resume on plugin load.

        If hardware is already up, starts immediately.
        If not ready yet, spawns a background thread that waits — so _main
        returns immediately and Decky can answer RPC calls straight away.
        """
        if not self.state.get("enabled"):
            self._info("not enabled; nothing to resume")
            return False

        if available():
            return self.start()

        def wait():
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self._stop.is_set():
                    return
                if available():
                    self._info("light bar appeared; resuming")
                    self.start()
                    return
                time.sleep(2.0)
            self._warn(f"no light bar after {timeout:.0f}s; not resuming")

        self._info("light bar not ready yet; waiting in background")
        threading.Thread(target=wait, name="steamled-autostart", daemon=True).start()
        return True

    def select(self, effect_id):
        if effect_id not in fx.REGISTRY:
            return False
        with self._lock:
            self.state["effect"] = effect_id
            self.effect = fx.build(effect_id)
            if self.strip:
                self.strip._last = [None] * self.strip.n
        self.save()
        return True

    def set_now_playing(self, value):
        with self._lock:
            self.state["now_playing"] = bool(value)
            if not self.state["now_playing"]:
                self._override = None
                self._override_effect = None
        self.save()

    def notify_game(self, game_id):
        with self._lock:
            if not self.state["now_playing"]:
                return False
            if game_id == self._override:
                return True
            self._override = game_id
            self._override_effect = fx.build("static") if game_id else None
            if self.strip:
                self.strip._last = [None] * self.strip.n
        self._info(f"now playing: {game_id}")
        return True

    def set_brightness(self, value):
        with self._lock:
            self.state["brightness"] = max(0.0, min(1.0, float(value)))
        self.save()

    def set_reverse(self, value):
        with self._lock:
            self.state["reverse"] = bool(value)
            if self.strip:
                self.strip.set_reverse(bool(value))
        self.save()

    def set_game_palette(self, colors, app_id=None):
        with self._lock:
            self.state["game_palette"] = list(colors) if colors else []
            self.state["game_palette_app_id"] = app_id

    # ── render loop ───────────────────────────────────────────────────────────

    def _run(self):
        t0 = time.monotonic()
        painted_static = None
        while not self._stop.is_set():
            with self._lock:
                strip = self.strip
                master = self.state["brightness"]
                if self._override and self._override_effect:
                    effect = self._override_effect
                    eid = "static"
                    override = self._override
                else:
                    effect, eid, override = self.effect, self.state["effect"], None
            if not strip or not effect:
                break

            params = self.params_for(eid)
            if override:
                params = dict(params, mode="game", game=override)
            now = time.monotonic() - t0

            try:
                sig = (eid, override, tuple(sorted(params.items())), master) \
                    if effect.static else None
                if not effect.static or sig != painted_static:
                    pixels = effect.render(now, strip.n, params)
                    strip.show(pixels, master)
                    painted_static = sig
            except Exception as e:
                self._warn(f"render error in {eid}: {e}")
                time.sleep(0.5)
                continue

            self._stop.wait(1.0 / max(1, effect.fps))
