"""Small parsing and maths helpers shared by all metrics."""

import re


def to_int(v):
    try:
        return int(re.match(r"-?\d+", str(v).strip()).group())
    except Exception:  # noqa: BLE001
        return None


def kv(text):
    out = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().lower()
            if k and k not in out:
                out[k] = v.strip()
    return out


def sections(raw, first="HEAD"):
    parts = re.split(r"^@@(\w+)\s*$", raw, flags=re.M)
    out = {first: parts[0]}
    for i in range(1, len(parts) - 1, 2):
        out[parts[i]] = parts[i + 1]
    return out


def interp(x, pts):
    """Piecewise-linear interpolation through sorted (x, y) points (clamped)."""
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / ((x1 - x0) or 1)
    return pts[-1][1]
