"""Memory and storage metric: RAM, swap/zRAM and /data usage."""

import re


def parse_ram(text):
    v = {}
    for line in text.splitlines():
        m = re.match(r"(\w+):\s+(\d+)", line)
        if m:
            v[m.group(1)] = int(m.group(2))
    total = v.get("MemTotal", 0)
    if not total:
        raise RuntimeError("RAM information unavailable")
    avail = v.get("MemAvailable", v.get("MemFree", 0))
    used = total - avail
    st_t, st_f = v.get("SwapTotal", 0), v.get("SwapFree", 0)
    return {
        "ram": used / total * 100, "ram_used": used / 1024, "ram_total": total / 1024,
        "swap_used": (st_t - st_f) / 1024, "swap_total": st_t / 1024,
    }


def parse_storage(text):
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 5 and p[0].startswith("/"):
            try:
                total, used, free = int(p[1]), int(p[2]), int(p[3])
            except ValueError:
                continue
            return {"storage": used / total * 100 if total else 0, "st_used": used / 1048576,
                    "st_free": free / 1048576, "st_total": total / 1048576}
    raise RuntimeError("Storage information unavailable")
