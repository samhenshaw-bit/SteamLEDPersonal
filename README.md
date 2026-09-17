# SteamLED

A Decky Loader plugin for the Steam Machine that drives the front LED light bar (17 RGB LEDs). Fork of [thesirms/SteamLED](https://github.com/thesirms/SteamLED) with expanded effects, automatic game colour extraction, and saved profiles.

---

## What's different from the original

| Feature | Original | This fork |
|---|---|---|
| Game colours | 21 hand-curated games only | **Any Steam game** — colours extracted from artwork automatically |
| Effects | Animated, Static, Off | + **Fire**, **Rain**, **CPU Load**, **Audio Reactive** |
| Profiles | None | Save and switch named effect snapshots |
| Flags | 27 | 35 |
| Game palettes | 21 | 31 (curated) + unlimited (automatic) |
| LED 0 flicker fix | No | Yes — hardware trigger pins reset on load |

---

## Installation

### Via Decky (recommended)

1. Open Decky → **Settings → Developer → Install Plugin from URL**
2. Paste the latest release URL:
   ```
   https://github.com/samhenshaw-bit/SteamLEDPersonal/releases/latest/download/SteamLED.zip
   ```
3. The plugin appears in your Decky menu immediately.

### On-device build

```bash
git clone https://github.com/samhenshaw-bit/SteamLEDPersonal.git
cd SteamLEDPersonal
bash install-local.sh
```

The script installs Node 20 via nvm if needed, builds the TypeScript frontend, and restarts the Decky plugin loader.

---

## Effects

### Animated
Eight motions — Scroll, Pulse, Bounce, Crossfade, Breathe, Scanner — across 11 colour presets plus custom (2–6 colours) and Rainbow.

### Static
Solid colour, colour preset held still, any of 35 flags, or a named game palette.

### Fire
Heat simulation. Each LED has a heat value that randomly ignites near the base and cools toward the other end. Comes in Classic, Blue, Toxic, and Magical colour modes.

### Rain
Drips spawn at one end of the bar and travel along it, fading as they go. Adjustable density, speed, and tail length.

### CPU Load
The bar fills from left to right proportional to CPU usage, shifting green → yellow → red. Useful for quick-glance system monitoring.

### Audio Reactive
Reads the PulseAudio/PipeWire output peak and pulses the bar to the beat. Three modes: brightness pulse, fill bar, colour shift. Requires `pactl` (available by default on SteamOS).

---

## Now Playing — automatic game colours

When **Now Playing** is on and you launch any Steam game:

1. The plugin reads the game's Steam App ID from the running session
2. It fetches the game's header artwork from Steam's CDN (`header.jpg`, 460×215px)
3. A k-means quantizer runs in the browser on a scaled-down version of the image (10% — fast, no external dependencies)
4. The 4–6 most vivid dominant colours are sent to the Python backend
5. The light bar animates those colours with a scrolling motion

The extracted palette is cached by App ID for the session, so re-launching the same game is instant.

**Fallback chain:**
- If the artwork fetch fails (offline, CDN blip) → keep the current effect unchanged
- If the extracted palette has fewer than 2 usable colours → fall back to the curated palette for that game if one exists, otherwise keep the current effect

The 31 curated palettes are still available as named presets in the Static effect → Game palette menu.

---

## Profiles

Save the current effect + all its parameters as a named profile (e.g. "Gaming", "Movie Mode", "Night"). Switch between them instantly from the top of the plugin panel.

Profiles are stored in the plugin's config file and survive reboots.

---

## Controls

| Control | Where |
|---|---|
| Enable/disable | Light Bar section toggle |
| Choose effect | Effect dropdown |
| Brightness | Slider, 0–100% |
| Reverse direction | Toggle (flips animation direction) |
| Now Playing | Now Playing section toggle |
| Save/load profiles | Profiles section at the top |

Effect-specific controls (speed, blend, tail length, colours, etc.) appear automatically beneath the effect dropdown when relevant.

---

## Building a release

Push a git tag and GitHub Actions handles the rest:

```bash
git tag v1.0.0
git push --tags
```

The workflow installs dependencies, builds the TypeScript bundle, zips the plugin, and attaches `SteamLED.zip` to a new GitHub Release. The release URL is what you paste into Decky.

To build locally without tagging:

```bash
bash package.sh
# Output: out/SteamLED.zip
```

---

## Project structure

```
py_modules/steamled/
  engine.py     Core render loop, settings, game palette + profile RPCs
  strip.py      sysfs LED hardware interface (trigger-pin fix for LED 0)
  effects.py    All effects — Animated, Static, Fire, Rain, CpuLoad, AudioReactive, Off
  color.py      Color math (gamma, HSV, lerp, palette utilities)
  games.py      Curated per-game palettes + title matching
  flags.py      35 flag definitions
  scroll.py     Named color presets

src/
  index.tsx         Main plugin panel (game watch, palette preview, param controls)
  colorQuant.ts     K-means colour quantizer (runs in Chromium, no external deps)
  api.ts            Type-safe RPC bindings to the Python backend
  ColorField.tsx    HSV colour picker (thumbstick-friendly, two sliders)
  ProfileManager.tsx Saved profiles UI

.github/workflows/
  release.yml   Build + publish zip on git tag push
```

---

## Adding a new game palette

Open [py_modules/steamled/games.py](py_modules/steamled/games.py) and add an entry to `GAMES`:

```python
"your_game": {
    "label": "Your Game",
    "stops": [
        (0.0, "HEX_COLOR", "rgb"),   # position, hex, interp mode ("rgb" or "hsv")
        (0.5, "HEX_COLOR", "hsv"),
        (1.0, "HEX_COLOR", "rgb"),
    ],
},
```

Then add a title alias to `_ALIASES`:

```python
("your game title", "your_game"),
```

The curated palette appears in the Static → Game palette menu and is also used as the Now Playing fallback if the artwork extraction fails.

---

## Requirements

- Steam Machine running SteamOS (Linux with `valve-leds` kernel devices)
- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) installed
- Audio Reactive effect requires `pactl` (included with SteamOS by default)
- Build: Node 18+, pnpm 9 (installed automatically by `install-local.sh`)

---

## Licence

BSD-3-Clause — same as the original SteamLED.
