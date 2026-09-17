"""Core render engine.

Manages an LED strip through a background render thread, persists settings
to JSON, and handles game override logic.

New in this fork:
  - set_game_palette(colors): accept a dynamic palette extracted from Steam
    artwork by the TypeScript frontend — applies to any game, no curated
    list required.
  - Profile management: save/load/delete named snapshots of effect + params.
  - Settings version 6 (adds profiles + game_palette_app_id tracking).
"""

import json
import os
import threading
import time

from .effects import build, catalog
from .games import match as game_match
from .strip import Strip

SETTINGS_VERSION = 6
CONFIG_DIR = os.path.expanduser(
    "~/.config/decky-loader/plugins/SteamLED"
)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def _default_state():
    return {
        "version": SETTINGS_VERSION,
        "enabled": True,
        "effect": "animated",
        "brightness": 1.0,
        "reverse": False,
        "now_playing": True,
        "profiles": [],
        "effects": {},
    }


class Engine:
    def __init__(self):
        self._lock = threading.RLock()
        self._strip = None
        self._effect = None
        self._state = _default_state()
        self._thread = None
        self._running = False
        self._t0 = 0.0
        # Override state: set when frontend provides a dynamic game palette.
        self._game_palette = None        # list of hex strings from artwork
        self._game_palette_app_id = None # Steam app id that the palette came from
        self._pre_game_state = None      # {"effect": ..., "params": ...} to restore on exit

    # ── settings persistence ──────────────────────────────────────────────────

    def _load(self):
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}

        state = _default_state()
        version = data.get("version", 0)

        # Copy known fields
        for k in ("enabled", "effect", "brightness", "reverse", "now_playing"):
            if k in data:
                state[k] = data[k]
        if "profiles" in data:
            state["profiles"] = data["profiles"]

        # Merge per-effect param dicts from saved state
        saved_effects = data.get("effects", {})
        state["effects"] = {}
        for eff_spec in catalog():
            eid = eff_spec["id"]
            defaults = {p["key"]: p["default"] for p in eff_spec["params"]}
            saved = saved_effects.get(eid, {})
            # Only restore known keys to avoid stale params from old versions
            merged = {k: saved.get(k, v) for k, v in defaults.items()}
            state["effects"][eid] = merged

        # Version migrations
        if version < 4:
            # Pre-v4: reverse was unreliable; let hardware detection settle it.
            state["reverse"] = False

        state["version"] = SETTINGS_VERSION
        self._state = state

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with self._lock:
            data = dict(self._state)
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _prune(self):
        """Remove param keys that no longer exist in any effect's metadata."""
        with self._lock:
            all_known = {}
            for eff_spec in catalog():
                eid = eff_spec["id"]
                known = {p["key"] for p in eff_spec["params"]}
                all_known[eid] = known
            for eid, params in list(self._state["effects"].items()):
                if eid not in all_known:
                    del self._state["effects"][eid]
                    continue
                self._state["effects"][eid] = {
                    k: v for k, v in params.items()
                    if k in all_known[eid]
                }

    # ── startup / shutdown ────────────────────────────────────────────────────

    def autostart(self):
        """Called on plugin load. Waits up to 90s for LED hardware then starts."""
        self._load()
        self._prune()

        deadline = time.time() + 90.0
        while time.time() < deadline:
            strip = Strip.open()
            if strip:
                self._strip = strip
                break
            time.sleep(2.0)

        if self._strip is None:
            return  # No hardware — sit idle

        with self._lock:
            self._strip.set_reverse(self._state["reverse"])
            self._strip.save()
            if self._state["enabled"]:
                self._start_loop()

    def stop(self, persist=True):
        """Stop the render loop and hand LEDs back to Steam."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._strip is not None:
            self._strip.restore()
        if persist:
            self.save()

    def _start_loop(self):
        if self._thread is not None and self._thread.is_alive():
            return
        with self._lock:
            eid = self._state["effect"]
        self._effect = build(eid)
        self._strip.prime()
        self._t0 = time.time()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ── render loop ───────────────────────────────────────────────────────────

    def _run(self):
        last_static_key = None

        while self._running:
            with self._lock:
                enabled = self._state["enabled"]
                if not enabled:
                    time.sleep(0.05)
                    continue

                effect = self._effect
                eid = self._state["effect"]
                params = dict(self._state["effects"].get(eid, {}))
                brightness = self._state["brightness"]
                game_palette = self._game_palette

            if effect is None:
                time.sleep(0.05)
                continue

            t = time.time() - self._t0

            # Dynamic game palette override: inject colors into animated/custom.
            if game_palette and len(game_palette) >= 2:
                params = self._game_palette_params(game_palette, params)

            # Static effects: skip repainting if nothing changed.
            if effect.static:
                key = (eid, brightness, str(params))
                if key == last_static_key:
                    time.sleep(1.0 / 30)
                    continue
                last_static_key = key
            else:
                last_static_key = None

            try:
                pixels = effect.render(t, self._strip.n, params)
            except Exception:
                pixels = [(0, 0, 0)] * self._strip.n

            self._strip.show(pixels, brightness)
            time.sleep(1.0 / effect.fps)

    @staticmethod
    def _game_palette_params(palette, base_params):
        """Build Animated/custom params from a dynamic game palette list."""
        colors = palette[:6]  # Animated supports up to 6
        p = dict(base_params)
        p["preset"] = "custom"
        p["count"] = len(colors)
        for i, hex_color in enumerate(colors):
            p[f"c{i + 1}"] = hex_color.lstrip("#")
        # Default to a smooth scroll if the current motion doesn't make sense
        if p.get("motion") not in ("scroll", "scroll_left", "pulse", "split",
                                    "bounce", "fade", "breathe", "scanner"):
            p["motion"] = "scroll"
        return p

    # ── public RPC methods ────────────────────────────────────────────────────

    def get_status(self):
        with self._lock:
            eid = self._state["effect"]
            params = dict(self._state["effects"].get(eid, {}))
            return {
                "enabled":        self._state["enabled"],
                "effect":         eid,
                "brightness":     self._state["brightness"],
                "reverse":        self._state["reverse"],
                "now_playing":    self._state["now_playing"],
                "params":         params,
                "game_palette":   self._game_palette,
                "game_palette_app_id": self._game_palette_app_id,
                "hardware":       self._strip is not None,
            }

    def set_enabled(self, enabled):
        with self._lock:
            self._state["enabled"] = bool(enabled)
        if enabled and self._strip and (self._thread is None or
                                        not self._thread.is_alive()):
            self._start_loop()
        elif not enabled and self._running:
            self._running = False
        self.save()

    def set_effect(self, effect_id):
        with self._lock:
            self._state["effect"] = effect_id
            if effect_id not in self._state["effects"]:
                self._state["effects"][effect_id] = build(effect_id).defaults()
            self._effect = build(effect_id)
            self._strip.clear_cache() if self._strip else None
            self._t0 = time.time()
        self.save()

    def set_param(self, effect_id, key, value):
        with self._lock:
            if effect_id not in self._state["effects"]:
                self._state["effects"][effect_id] = {}
            self._state["effects"][effect_id][key] = value
            if self._effect and self._effect.static:
                self._strip.clear_cache() if self._strip else None
        self.save()

    def set_brightness(self, value):
        with self._lock:
            self._state["brightness"] = max(0.0, min(1.0, float(value)))
        self.save()

    def set_reverse(self, value):
        with self._lock:
            self._state["reverse"] = bool(value)
            if self._strip:
                self._strip.set_reverse(self._state["reverse"])
        self.save()

    def set_now_playing(self, enabled):
        with self._lock:
            self._state["now_playing"] = bool(enabled)
            if not enabled:
                self._clear_game_palette_locked()
        self.save()

    def game_changed(self, title, app_id=None):
        """Called when the running game changes.

        If a dynamic palette was set by the frontend for this app_id, it stays
        active. If no dynamic palette yet, falls back to curated game match.
        If the title is empty/None, clears any game override.
        """
        with self._lock:
            if not self._state["now_playing"]:
                return

            if not title:
                self._clear_game_palette_locked()
                return

            # If we already have a dynamic palette for this app, keep it.
            if (app_id and self._game_palette_app_id == app_id
                    and self._game_palette):
                return

            # Fall back to curated palette match.
            game_id = game_match(title)
            if game_id:
                eid = self._state["effect"]
                if self._pre_game_state is None:
                    self._pre_game_state = {
                        "effect": eid,
                        "params": dict(self._state["effects"].get(eid, {})),
                    }
                # Drive the Static effect in "game" mode.
                if "static" not in self._state["effects"]:
                    self._state["effects"]["static"] = build("static").defaults()
                self._state["effects"]["static"]["mode"] = "game"
                self._state["effects"]["static"]["game"] = game_id
                self._state["effect"] = "static"
                self._effect = build("static")
                self._t0 = time.time()

    # ── dynamic game palette (artwork extraction) ─────────────────────────────

    def set_game_palette(self, colors, app_id=None):
        """Set a dynamic palette extracted from Steam artwork.

        colors: list of 2-6 hex strings from the frontend quantizer.
        app_id: Steam app id (optional, used to avoid re-fetching on revisit).

        Switches to Animated/custom with these colors while now_playing is on.
        Pass colors=None (or empty list) to clear and restore the previous effect.
        """
        with self._lock:
            if not colors:
                self._clear_game_palette_locked()
                return

            if not self._state["now_playing"]:
                return

            # Save current state to restore later.
            if self._pre_game_state is None:
                eid = self._state["effect"]
                self._pre_game_state = {
                    "effect": eid,
                    "params": dict(self._state["effects"].get(eid, {})),
                }

            self._game_palette = [c.lstrip("#") for c in colors[:6]]
            self._game_palette_app_id = app_id

            # Switch to Animated effect — the render loop injects the palette.
            if "animated" not in self._state["effects"]:
                self._state["effects"]["animated"] = build("animated").defaults()
            self._state["effect"] = "animated"
            self._effect = build("animated")
            self._t0 = time.time()
            if self._strip:
                self._strip.clear_cache()

    def _clear_game_palette_locked(self):
        """Restore the pre-game effect. Must be called with _lock held."""
        self._game_palette = None
        self._game_palette_app_id = None
        if self._pre_game_state is not None:
            eid = self._pre_game_state["effect"]
            self._state["effect"] = eid
            if eid in self._state["effects"]:
                self._state["effects"][eid].update(
                    self._pre_game_state.get("params", {})
                )
            self._effect = build(eid)
            self._t0 = time.time()
            self._pre_game_state = None
            if self._strip:
                self._strip.clear_cache()

    # ── profiles ──────────────────────────────────────────────────────────────

    def list_profiles(self):
        with self._lock:
            return [{"name": p["name"], "effect": p["effect"]}
                    for p in self._state.get("profiles", [])]

    def save_profile(self, name):
        """Snapshot current effect + params as a named profile."""
        with self._lock:
            eid = self._state["effect"]
            profile = {
                "name": name,
                "effect": eid,
                "brightness": self._state["brightness"],
                "params": dict(self._state["effects"].get(eid, {})),
            }
            profiles = self._state.setdefault("profiles", [])
            profiles[:] = [p for p in profiles if p["name"] != name]
            profiles.append(profile)
        self.save()
        return True

    def load_profile(self, name):
        """Restore a saved profile, returning False if not found."""
        with self._lock:
            profiles = self._state.get("profiles", [])
            profile = next((p for p in profiles if p["name"] == name), None)
            if not profile:
                return False
            eid = profile["effect"]
            self._state["effect"] = eid
            self._state["brightness"] = profile.get("brightness", 1.0)
            if eid not in self._state["effects"]:
                self._state["effects"][eid] = build(eid).defaults()
            self._state["effects"][eid].update(profile.get("params", {}))
            self._effect = build(eid)
            self._t0 = time.time()
            if self._strip:
                self._strip.clear_cache()
            # Clear any active game override
            self._game_palette = None
            self._game_palette_app_id = None
            self._pre_game_state = None
        self.save()
        return True

    def delete_profile(self, name):
        with self._lock:
            profiles = self._state.setdefault("profiles", [])
            profiles[:] = [p for p in profiles if p["name"] != name]
        self.save()
        return True
