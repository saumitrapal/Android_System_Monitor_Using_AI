"""CPU metric: load, per-core load, clock speeds and thermal zones."""

import re

from core.utils import to_int


def parse_cpu(text, prev):
    usage = {}
    for line in text.splitlines():
        p = line.split()
        if not p or not p[0].startswith("cpu"):
            continue
        vals = list(map(int, p[1:]))
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        old = prev.get(p[0])
        prev[p[0]] = (total, idle)
        if old and total > old[0]:
            usage[p[0]] = max(0.0, min(100.0, (1 - (idle - old[1]) / (total - old[0])) * 100))
        else:
            usage[p[0]] = 0.0
    total = usage.pop("cpu", 0.0)
    cores = [usage[k] for k in sorted(usage, key=lambda c: int(c[3:]))]
    return total, cores


def parse_freq(text):
    out = []
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 3 and p[1].isdigit() and p[2].isdigit():
            out.append({"core": p[0], "cur": int(p[1]) / 1000, "max": int(p[2]) / 1000})
    return sorted(out, key=lambda r: int(re.sub(r"\D", "", r["core"]) or 0))


def parse_thermal(text):
    zones = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        name, raw = line.split("|", 1)
        v = to_int(raw)
        if v is None:
            continue
        t = v / 1000 if abs(v) >= 1000 else (v / 10 if abs(v) >= 200 else v)
        if -30 < t < 150:
            zones.append((name.strip() or "zone", round(float(t), 1)))
    return zones


CPU_ZONE_HINTS = ("cpu", "soc", "cluster", "big", "little", "tsens", "mtktscpu")
