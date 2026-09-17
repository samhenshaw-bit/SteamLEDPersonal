"""Color math utilities. All RGB values are float tuples in 0-1 range."""

import math

BLACK = (0.0, 0.0, 0.0)

# Applied to game/flag palettes before rendering to compensate for perceptual
# characteristics of the LED strip viewed at distance.
PALETTE_SAT = 1.35
PALETTE_GAMMA = 1.8


def gamma(rgb, g=2.2):
    """Perceptual correction. LEDs are brutally nonlinear without this."""
    return tuple(c ** (1.0 / g) for c in rgb)


def from_hex(h):
    """Parse a hex string (with or without #) to a float RGB tuple."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b)
    except (ValueError, IndexError):
        return (1.0, 0.0, 0.0)  # fall back to red so bad values are visible


def to_hex(rgb):
    """Float RGB tuple to a 6-digit hex string without #."""
    r, g, b = rgb
    ri = min(255, max(0, round(r * 255)))
    gi = min(255, max(0, round(g * 255)))
    bi = min(255, max(0, round(b * 255)))
    return f"{ri:02X}{gi:02X}{bi:02X}"


def hsv(h, s, v):
    """Hue (0-1 turns), saturation, value → RGB."""
    h = h % 1.0
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    i = i % 6
    if i == 0:
        return (v, t, p)
    if i == 1:
        return (q, v, p)
    if i == 2:
        return (p, v, t)
    if i == 3:
        return (p, q, v)
    if i == 4:
        return (t, p, v)
    return (v, p, q)


def lerp(a, b, t):
    """Linear interpolation between two RGB tuples."""
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def hsv_lerp(a, b, t):
    """Interpolate via HSV to avoid muddy gray midpoints on wide hue distances."""
    def to_hsv(rgb):
        r, g, bl = rgb
        mx = max(r, g, bl)
        mn = min(r, g, bl)
        d = mx - mn
        if d == 0:
            h = 0.0
        elif mx == r:
            h = ((g - bl) / d) % 6 / 6
        elif mx == g:
            h = ((bl - r) / d + 2) / 6
        else:
            h = ((r - g) / d + 4) / 6
        s = 0.0 if mx == 0 else d / mx
        return (h, s, mx)

    ha, sa, va = to_hsv(a)
    hb, sb, vb = to_hsv(b)
    # Shortest hue path
    dh = hb - ha
    if dh > 0.5:
        dh -= 1.0
    if dh < -0.5:
        dh += 1.0
    return hsv(ha + dh * t, sa + (sb - sa) * t, va + (vb - va) * t)


def scale(rgb, factor):
    """Scale brightness by a factor."""
    return tuple(c * factor for c in rgb)


def saturate(rgb, amount):
    """Boost saturation. amount > 1 increases, < 1 decreases."""
    r, g, b = rgb
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return tuple(max(0.0, min(1.0, lum + (c - lum) * amount)) for c in (r, g, b))


def deepen(pixels):
    """Stretch the value range of a pixel list to increase dynamic range.

    Flat palettes (e.g., Neon White where everything is near-white) look
    dim on the strip. This rescales so the darkest pixel maps to black
    while the brightest stays at its original level, increasing contrast
    without blowing out the highlights.
    """
    if not pixels:
        return pixels
    values = [max(c) for c in pixels]
    lo = min(values)
    hi = max(values)
    if hi - lo < 0.05 or hi < 0.001:
        # Already high-contrast or monochromatic — don't distort.
        return pixels
    scale_factor = 1.0 / hi
    return [tuple((c - lo * (c / max(max(px), 1e-6))) * scale_factor
                  for c in px)
            for px in pixels]


def ramp(stops, n):
    """Sample a multi-stop gradient across n pixels.

    stops: list of (position, hex_color, mode) where position is 0-1,
           mode is "rgb" or "hsv".
    Returns list of n float RGB tuples.
    """
    if not stops:
        return [BLACK] * n
    stops = sorted(stops, key=lambda s: s[0])
    result = []
    for i in range(n):
        t = i / max(1, n - 1)
        # Find surrounding stops
        lo = stops[0]
        hi = stops[-1]
        for j in range(len(stops) - 1):
            if stops[j][0] <= t <= stops[j + 1][0]:
                lo, hi = stops[j], stops[j + 1]
                break
        span = hi[0] - lo[0]
        if span < 1e-6:
            result.append(from_hex(hi[1]))
            continue
        frac = (t - lo[0]) / span
        a = from_hex(lo[1])
        b = from_hex(hi[1])
        mode = lo[2] if len(lo) > 2 else "rgb"
        if mode == "hsv":
            result.append(hsv_lerp(a, b, frac))
        else:
            result.append(lerp(a, b, frac))
    return result
