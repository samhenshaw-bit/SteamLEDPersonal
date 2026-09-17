"""Decky plugin entry point.

Each async method decorated with nothing is exposed as an RPC call the
TypeScript frontend can invoke via serverAPI.callPluginMethod().
"""

import asyncio

from py_modules.steamled.effects import catalog
from py_modules.steamled.engine import Engine

_engine = Engine()


class Plugin:
    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def _main(self):
        """Called when the plugin loads. Hardware detection happens here."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _engine.autostart)

    async def _unload(self):
        """Called when Decky unloads the plugin (not system shutdown).

        Does NOT persist the disabled state — the user didn't turn it off,
        they just closed Decky. On next load, autostart resumes the effect.
        """
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: _engine.stop(persist=False)
        )

    # ── read ──────────────────────────────────────────────────────────────────

    async def get_status(self):
        return _engine.get_status()

    async def get_catalog(self):
        return catalog()

    async def get_params(self, effect_id: str):
        status = _engine.get_status()
        effects = status.get("effects", {})
        return effects.get(effect_id, {})

    # ── control ───────────────────────────────────────────────────────────────

    async def set_enabled(self, enabled: bool):
        _engine.set_enabled(enabled)

    async def set_effect(self, effect_id: str):
        _engine.set_effect(effect_id)

    async def set_param(self, effect_id: str, key: str, value):
        _engine.set_param(effect_id, key, value)

    async def set_brightness(self, value: float):
        _engine.set_brightness(value)

    async def set_reverse(self, value: bool):
        _engine.set_reverse(value)

    async def set_now_playing(self, enabled: bool):
        _engine.set_now_playing(enabled)

    # ── game palette (dynamic artwork extraction) ─────────────────────────────

    async def set_game_palette(self, colors: list, app_id: str = None):
        """Accept a palette extracted by the frontend from Steam artwork.

        colors: list of 2-6 hex strings (with or without #).
        app_id: Steam app id string (optional, for cache invalidation).
        """
        _engine.set_game_palette(colors, app_id=app_id)

    async def game_changed(self, title: str, app_id: str = None):
        """Called by the frontend when the running game changes.

        Triggers curated palette fallback if no dynamic palette has been
        delivered yet for this app.
        """
        _engine.game_changed(title, app_id=app_id)

    # ── profiles ──────────────────────────────────────────────────────────────

    async def list_profiles(self):
        return _engine.list_profiles()

    async def save_profile(self, name: str):
        return _engine.save_profile(name)

    async def load_profile(self, name: str):
        return _engine.load_profile(name)

    async def delete_profile(self, name: str):
        return _engine.delete_profile(name)
