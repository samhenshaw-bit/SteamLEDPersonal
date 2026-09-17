"""Hardware interface — the valve-led sysfs devices.

Discovers LEDs at /sys/class/leds/valve-ledsN/, sorts numerically, and
provides show() / restore() around a background render loop.

Key fix: on prime(), any LED whose kernel trigger is not "none" (Steam's
notification daemon sets valve-leds0 to "heartbeat" or similar) is
explicitly reset to "none". Without this, Steam's daemon races with our
render loop and the leftmost LED flickers a different colour every few
frames. On restore(), the original triggers are written back so Steam
regains clean control.

As a belt-and-braces measure, LED 0 is always written last in show() so
our value is the final write in each frame window, overriding any
concurrent Steam write.
"""

import os
import re

_LED_ROOT = "/sys/class/leds"
_LED_RE = re.compile(r"^valve-leds(\d+)$")
_TRIGGER_RE = re.compile(r"\[(\w+)\]")


def _discover():
    """Return LED sysfs paths sorted by numeric index."""
    try:
        entries = os.listdir(_LED_ROOT)
    except OSError:
        return []
    pairs = []
    for name in entries:
        m = _LED_RE.match(name)
        if m:
            pairs.append((int(m.group(1)), os.path.join(_LED_ROOT, name)))
    pairs.sort()
    return [path for _, path in pairs]


def _read(path, attr):
    try:
        with open(os.path.join(path, attr)) as f:
            return f.read().strip()
    except OSError:
        return ""


def _write(path, attr, value):
    try:
        with open(os.path.join(path, attr), "w") as f:
            f.write(str(value))
        return True
    except OSError:
        return False


def _active_trigger(path):
    """Return the currently active trigger name for an LED device."""
    content = _read(path, "trigger")
    m = _TRIGGER_RE.search(content)
    return m.group(1) if m else "none"


class Strip:
    def __init__(self, paths):
        self._paths = paths
        self._n = len(paths)
        self._max = [self._read_max(p) for p in paths]
        self._last = [None] * self._n
        self._saved = None
        self._saved_triggers = {}  # path → original trigger string
        self._primed = False
        self._reverse = False

    @staticmethod
    def _read_max(path):
        v = _read(path, "max_brightness")
        try:
            return max(1, int(v))
        except ValueError:
            return 255

    # ── ownership ────────────────────────────────────────────────────────────

    def prime(self):
        """Claim exclusive LED control.

        Disables any kernel trigger on each device so Steam's own daemon can
        no longer interleave writes with ours. Saves originals for restore().

        The most common culprit is valve-leds0 (leftmost LED) which the Steam
        UI uses for system notification flashes. Setting its trigger to "none"
        stops the kernel driver from fighting our render loop.
        """
        if self._primed:
            return
        self._primed = True

        for path in self._paths:
            trigger = _active_trigger(path)
            if trigger != "none":
                self._saved_triggers[path] = trigger
                _write(path, "trigger", "none")

        # Ensure master brightness isn't at zero (would make all LEDs invisible).
        for i, path in enumerate(self._paths):
            b = _read(path, "brightness")
            try:
                if int(b) == 0:
                    _write(path, "brightness", str(self._max[i]))
            except ValueError:
                pass

    def save(self):
        """Snapshot the current hardware state so restore() can return to it."""
        self._saved = []
        for path in self._paths:
            raw = _read(path, "multi_intensity")
            try:
                parts = [int(x) for x in raw.split()]
                self._saved.append(tuple(parts) if len(parts) == 3 else (0, 0, 0))
            except (ValueError, AttributeError):
                self._saved.append((0, 0, 0))

    def restore(self):
        """Return LED control to Steam.

        Writes back the snapshotted pixel state and re-enables any kernel
        triggers we disabled in prime(), so Steam's own animations resume.
        """
        if self._saved is not None:
            for i, path in enumerate(self._paths):
                r, g, b = self._saved[i]
                _write(path, "multi_intensity", f"{r} {g} {b}")

        for path, trigger in self._saved_triggers.items():
            _write(path, "trigger", trigger)
        self._saved_triggers.clear()
        self._primed = False

    # ── rendering ────────────────────────────────────────────────────────────

    def show(self, pixels, brightness):
        """Write a pixel list to hardware.

        pixels:     list of (r, g, b) float tuples in 0-1.
        brightness: master scale in 0-1.

        Skips redundant writes (cached per LED) to reduce syscall overhead
        at 60 fps. LED 0 is always written last — this ensures our value
        is the final write in each frame window, overriding any concurrent
        Steam write on that LED.
        """
        n = min(len(pixels), self._n)

        if self._reverse:
            logical = list(reversed(range(n)))
        else:
            logical = list(range(n))

        # Write order: 1..n-1 first, then 0 last (anti-race for LED 0).
        order = list(range(1, n)) + [0]

        for phys in order:
            log = logical[phys] if phys < len(logical) else phys
            if log >= len(pixels):
                continue
            r, g, b = pixels[log]
            mx = self._max[phys]
            ri = min(255, max(0, round(r * brightness * mx)))
            gi = min(255, max(0, round(g * brightness * mx)))
            bi = min(255, max(0, round(b * brightness * mx)))
            rgb = (ri, gi, bi)
            if rgb == self._last[phys]:
                continue
            _write(self._paths[phys], "multi_intensity", f"{ri} {gi} {bi}")
            self._last[phys] = rgb

    def clear_cache(self):
        """Force a full repaint on the next show() call."""
        self._last = [None] * self._n

    def set_reverse(self, rev):
        self._reverse = bool(rev)
        self.clear_cache()

    @property
    def n(self):
        return self._n

    # ── factory ──────────────────────────────────────────────────────────────

    @classmethod
    def open(cls):
        """Discover LED devices and return a Strip, or None if none found."""
        paths = _discover()
        return cls(paths) if paths else None
