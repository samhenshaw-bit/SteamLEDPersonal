"""Access to the Steam Machine front light bar via the Linux multicolor LED class."""

import glob
import os
import re

LED_GLOB = "/sys/class/leds/valve-leds[[]?[]]"


def _index_of(path: str) -> int:
    m = re.search(r"\[(\d+)\]$", path)
    return int(m.group(1)) if m else 0


def discover():
    """Return sysfs paths sorted numerically."""
    paths = glob.glob("/sys/class/leds/valve-leds*")
    paths = [p for p in paths if re.search(r"valve-leds\[?\d+\]?$", p)]
    paths.sort(key=_index_of)
    return paths


def available() -> bool:
    return bool(discover())


class Strip:
    def __init__(self, reverse: bool = False):
        self.paths = discover()
        self.n = len(self.paths)
        if not self.n:
            raise RuntimeError("No valve-leds found on this system")

        self.max = self._read_int(self.paths[0], "max_brightness", 255)
        self._reverse = reverse
        self._rebuild_map()
        self._saved = None
        self._last = [None] * self.n
        self._primed = False

    def _rebuild_map(self):
        order = list(range(self.n))
        if self._reverse:
            order.reverse()
        self.map = order

    def set_reverse(self, reverse: bool):
        if reverse != self._reverse:
            self._reverse = reverse
            self._rebuild_map()
            self._last = [None] * self.n

    @staticmethod
    def _read_int(path, name, default):
        try:
            with open(os.path.join(path, name)) as f:
                return int(f.read().strip())
        except Exception:
            return default

    def _write(self, phys_i, name, value):
        try:
            with open(os.path.join(self.paths[phys_i], name), "w") as f:
                f.write(value)
            return True
        except OSError:
            return False

    def save(self):
        self._saved = []
        for p in self.paths:
            try:
                with open(os.path.join(p, "multi_intensity")) as f:
                    mi = f.read().strip()
                with open(os.path.join(p, "brightness")) as f:
                    br = f.read().strip()
            except Exception:
                mi, br = "0 0 0", str(self.max)
            self._saved.append((mi, br))

    def restore(self):
        if not self._saved:
            return
        for i, (mi, br) in enumerate(self._saved):
            self._write(i, "multi_intensity", mi)
            self._write(i, "brightness", br)
        self._last = [None] * self.n

    def _q(self, c: float) -> int:
        return max(0, min(self.max, int(round(c * self.max))))

    def prime(self):
        if self._primed:
            return
        self._primed = True
        for i, p in enumerate(self.paths):
            if self._read_int(p, "brightness", 0) <= 0:
                self._write(i, "brightness", str(self.max))

    def show(self, pixels, master: float = 1.0):
        self.prime()
        for logical, px in enumerate(pixels):
            if logical >= self.n:
                break
            phys = self.map[logical]
            r = self._q(px[0] * master)
            g = self._q(px[1] * master)
            b = self._q(px[2] * master)
            packed = (r, g, b)
            if self._last[phys] == packed:
                continue
            if self._write(phys, "multi_intensity", f"{r} {g} {b}"):
                self._last[phys] = packed

    def clear(self):
        self.show([(0.0, 0.0, 0.0)] * self.n)
