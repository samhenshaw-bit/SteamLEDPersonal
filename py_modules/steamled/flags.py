"""Flags as weighted vertical color bands.

Each flag is a list of (hex_color, relative_weight) pairs.
Horizontal flags are rendered as verticals (the strip is 1D).
Flags with emblems (Japan, Canada, UK) are approximated by dominant bands.

Design goal: recognizable at a glance from across the room.
"""

# Shared color constants
W = "FFFFFF"  # white
K = "000000"  # black
R = "FF0000"  # red
B = "0000FF"  # blue
G = "00AA00"  # green

FLAGS = {
    # ─── Europe ────────────────────────────────────────────────────
    "uk": {
        "label": "United Kingdom",
        "bands": [(R, 2), (W, 1), (B, 2), (W, 1), (R, 2)],
    },
    "ireland": {
        "label": "Ireland",
        "bands": [("169B62", 1), (W, 1), ("FF883E", 1)],
    },
    "france": {
        "label": "France",
        "bands": [("002395", 1), (W, 1), ("ED2939", 1)],
    },
    "germany": {
        "label": "Germany",
        "bands": [(K, 1), ("DD0000", 1), ("FFCE00", 1)],
    },
    "italy": {
        "label": "Italy",
        "bands": [("009246", 1), (W, 1), ("CE2B37", 1)],
    },
    "spain": {
        "label": "Spain",
        "bands": [("AA151B", 1), ("F1BF00", 2), ("AA151B", 1)],
    },
    "netherlands": {
        "label": "Netherlands",
        "bands": [("AE1C28", 1), (W, 1), ("21468B", 1)],
    },
    "belgium": {
        "label": "Belgium",
        "bands": [(K, 1), ("FDDA25", 1), ("EF3340", 1)],
    },
    "austria": {
        "label": "Austria",
        "bands": [("ED2939", 1), (W, 1), ("ED2939", 1)],
    },
    "switzerland": {
        "label": "Switzerland",
        "bands": [("FF0000", 2), (W, 1), ("FF0000", 2)],
    },
    "denmark": {
        "label": "Denmark",
        "bands": [("C60C30", 2), (W, 1), ("C60C30", 2)],
    },
    "sweden": {
        "label": "Sweden",
        "bands": [("006AA7", 2), ("FECC02", 1), ("006AA7", 2)],
    },
    "norway": {
        "label": "Norway",
        "bands": [("EF2B2D", 2), (W, 1), ("002868", 1), (W, 1), ("EF2B2D", 2)],
    },
    "finland": {
        "label": "Finland",
        "bands": [(W, 2), ("003580", 1), (W, 2)],
    },
    "poland": {
        "label": "Poland",
        "bands": [(W, 1), ("DC143C", 1)],
    },
    "ukraine": {
        "label": "Ukraine",
        "bands": [("005BBB", 1), ("FFD500", 1)],
    },
    "greece": {
        "label": "Greece",
        "bands": [("0D5EAF", 1), (W, 1), ("0D5EAF", 1), (W, 1), ("0D5EAF", 1)],
    },
    "portugal": {
        "label": "Portugal",
        "bands": [("006600", 2), ("FF0000", 3)],
    },
    "scotland": {
        "label": "Scotland",
        "bands": [("003399", 2), (W, 1), ("003399", 2)],
    },
    "wales": {
        "label": "Wales",
        "bands": [(W, 1), ("00AB39", 1)],
    },
    # ─── Americas ──────────────────────────────────────────────────
    "us": {
        "label": "United States",
        "bands": [("B22234", 2), (W, 1), ("B22234", 2), (W, 1), ("3C3B6E", 3)],
    },
    "canada": {
        "label": "Canada",
        "bands": [("FF0000", 2), (W, 3), ("FF0000", 2)],
    },
    "mexico": {
        "label": "Mexico",
        "bands": [("006847", 1), (W, 1), ("CE1126", 1)],
    },
    "brazil": {
        "label": "Brazil",
        "bands": [("009C3B", 3), ("FEDD00", 2), ("002776", 1)],
    },
    "argentina": {
        "label": "Argentina",
        "bands": [("74ACDF", 1), (W, 1), ("74ACDF", 1)],
    },
    # ─── Asia / Pacific ────────────────────────────────────────────
    "japan": {
        "label": "Japan",
        "bands": [(W, 3), ("BC002D", 2), (W, 3)],
    },
    "south_korea": {
        "label": "South Korea",
        "bands": [(W, 1), ("C60C30", 1), (W, 1), ("003478", 1), (W, 1)],
    },
    "india": {
        "label": "India",
        "bands": [("FF9933", 1), (W, 1), ("138808", 1)],
    },
    "australia": {
        "label": "Australia",
        "bands": [("00008B", 3), (R, 1), (W, 1), ("00008B", 2)],
    },
    "new_zealand": {
        "label": "New Zealand",
        "bands": [("00247D", 3), (R, 2), ("00247D", 2)],
    },
    # ─── Africa ────────────────────────────────────────────────────
    "south_africa": {
        "label": "South Africa",
        "bands": [("007A4D", 2), (W, 1), ("FFB612", 1), (K, 1), ("DE3831", 2)],
    },
    "nigeria": {
        "label": "Nigeria",
        "bands": [("008751", 1), (W, 1), ("008751", 1)],
    },
    # ─── Middle East ───────────────────────────────────────────────
    "israel": {
        "label": "Israel",
        "bands": [("0038B8", 1), (W, 2), ("0038B8", 1)],
    },
    # ─── Pride ─────────────────────────────────────────────────────
    "pride": {
        "label": "Pride",
        "bands": [("FF0018", 1), ("FFA52C", 1), ("FFFF41", 1),
                  ("008018", 1), ("0000F9", 1), ("86007D", 1)],
    },
    "trans": {
        "label": "Trans Pride",
        "bands": [("55CDFC", 2), ("F7A8B8", 2), (W, 2), ("F7A8B8", 2), ("55CDFC", 2)],
    },
}

ORDER = [
    "uk", "ireland", "scotland", "wales",
    "france", "germany", "italy", "spain", "netherlands", "belgium",
    "austria", "switzerland", "denmark", "sweden", "norway", "finland",
    "poland", "ukraine", "greece", "portugal",
    "us", "canada", "mexico", "brazil", "argentina",
    "japan", "south_korea", "india", "australia", "new_zealand",
    "south_africa", "nigeria", "israel",
    "pride", "trans",
]


def options():
    """Dropdown options in display order."""
    return [{"value": k, "label": FLAGS[k]["label"]}
            for k in ORDER if k in FLAGS]


def _hex_to_float(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0)


def edges(flag_id):
    """Return (colors, weights) for a flag."""
    flag = FLAGS.get(flag_id, FLAGS["uk"])
    bands = flag["bands"]
    colors = [_hex_to_float(b[0]) for b in bands]
    weights = [b[1] for b in bands]
    return colors, weights


def sample(flag_id, n):
    """Render a flag across n pixels using box-filter coverage."""
    colors, weights = edges(flag_id)
    total = sum(weights)
    # Convert weights to cumulative band edges in 0-1 space
    cum = []
    acc = 0.0
    for w in weights:
        acc += w / total
        cum.append(acc)

    out = []
    for i in range(n):
        t = (i + 0.5) / n  # pixel centre
        for j, edge in enumerate(cum):
            if t <= edge:
                out.append(colors[j])
                break
        else:
            out.append(colors[-1])
    return out
