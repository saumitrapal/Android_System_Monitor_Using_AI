"""Diagnostics metric: device info, security checks, packages, Wi-Fi, crashes."""

import re
import time

from core.commands import PROP_KEYS
from core.utils import sections, to_int


def parse_diag(raw):
    sec = sections(raw, "PRE")
    props = {}
    for m in re.finditer(r"^\[(.+?)\]: \[(.*)\]$", sec.get("PROPS", ""), flags=re.M):
        if m.group(1) in PROP_KEYS:
            props[m.group(1)] = m.group(2)

    nums = [to_int(x) for x in sec.get("PKG", "").split()]
    nums += [None] * (3 - len(nums))
    wm = sec.get("WM", "")
    size = re.search(r"Physical size:\s*(\S+)", wm)
    dens = re.search(r"Physical density:\s*(\d+)", wm)
    pwr = sec.get("PWR", "")
    wake = re.search(r"mWakefulness=(\w+)", pwr)
    wifi = sec.get("WIFI", "")
    ssid = re.search(r'SSID: "?([^",]+)"?', wifi)
    rssi = re.search(r"RSSI: (-?\d+)", wifi)
    speed = re.search(r"Link speed: (\d+)", wifi)
    freq = re.search(r"Frequency: (\d+)", wifi)
    su_lines = [l.strip() for l in sec.get("SU", "").splitlines() if l.strip().startswith("/")]
    return {
        "props": props,
        "selinux": sec.get("SEL", "").strip() or None,
        "rooted": bool(su_lines),
        "apps": {"user": nums[0], "system": nums[1], "disabled": nums[2]},
        "display": {"size": size.group(1) if size else None, "density": int(dens.group(1)) if dens else None,
                    "state": wake.group(1) if wake else None},
        "wifi": {"ssid": ssid.group(1) if ssid else None, "rssi": int(rssi.group(1)) if rssi else None,
                 "speed": int(speed.group(1)) if speed else None, "freq": int(freq.group(1)) if freq else None},
        "crashes": to_int(sec.get("CRASH", "")), "anrs": to_int(sec.get("ANR", "")),
        "time": time.time(),
    }
