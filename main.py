import os
import sys

try:
    import decky
    SETTINGS_DIR = decky.DECKY_PLUGIN_SETTINGS_DIR
    LOGGER = decky.logger
except ImportError:
    import logging
    LOGGER = logging.getLogger("steamled")
    SETTINGS_DIR = os.path.expanduser(
        "~/.config/decky-loader/plugins/SteamLED"
    )

sys.path.append(os.path.join(os.path.dirname(__file__), "py_modules"))

from steamled import effects as fx          # noqa: E402
from steamled import games                  # noqa: E402
from steamled.engine import Engine          # noqa: E402
from steamled.strip import available        # noqa: E402


class Plugin:
    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def _main(self):
        settings = os.path.join(SETTINGS_DIR, "config.json")
        self.engine = Engine(settings_path=settings, logger=LOGGER)
        LOGGER.info(f"SteamLED loaded. Light bar present: {available()}")
        self.engine.autostart()

    async def _unload(self):
        try:
            self.engine.stop(restore=True, persist=False)
        except Exception as e:
            LOGGER.warning(f"unload: {e}")
        LOGGER.info("SteamLED unloaded")

    async def _uninstall(self):
        try:
            self.engine.stop(restore=True, persist=False)
        except Exception:
            pass

    # ── queries ───────────────────────────────────────────────────────────────

    async def get_status(self) -> dict:
        return self.engine.status()

    async def get_catalog(self) -> list:
        return fx.catalog()

    async def get_params(self, effect_id: str) -> dict:
        return self.engine.params_for(effect_id)

    # ── control ───────────────────────────────────────────────────────────────

    async def set_enabled(self, enabled: bool) -> dict:
        if enabled:
            self.engine.start()
        else:
            self.engine.stop(restore=True)
        return self.engine.status()

    async def set_effect(self, effect_id: str) -> dict:
        self.engine.select(effect_id)
        if not self.engine.state["enabled"]:
            self.engine.start()
        return self.engine.status()

    async def set_param(self, effect_id: str, key: str, value) -> bool:
        self.engine.set_param(effect_id, key, value)
        return True

    async def set_brightness(self, value: float) -> bool:
        self.engine.set_brightness(value)
        return True

    async def set_reverse(self, value: bool) -> bool:
        self.engine.set_reverse(value)
        return True

    async def set_now_playing(self, value: bool) -> dict:
        self.engine.set_now_playing(value)
        return self.engine.status()

    async def game_changed(self, title: str = "") -> dict:
        gid = games.match(title) if title else None
        LOGGER.info(f"game_changed: {title!r} -> {gid}")
        self.engine.notify_game(gid)
        return self.engine.status()

    async def set_game_palette(self, colors: list = None, app_id: str = None) -> bool:
        colors = colors or []
        LOGGER.info(f"set_game_palette: {len(colors)} colours for app {app_id!r}")
        self.engine.set_game_palette(colors, app_id)
        return True
