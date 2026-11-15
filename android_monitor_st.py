#!/usr/bin/env python3
"""
Android System Monitor - Streamlit Edition (Polished UI)
========================================================
Live dashboard + ADB health diagnostics for an Android phone.

    pip install streamlit plotly pandas
    streamlit run android_monitor_st.py

Requirements: `adb` on PATH, USB debugging enabled and authorised on the phone.
Theme: use Streamlit's menu (top-right ⋮ → Settings → Theme) to pick Light, Dark
or "Use system setting". The charts and gauges follow the chosen theme.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections import deque
from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

MAX_HISTORY = 900

# =============================================================================
#  ADB layer
# =============================================================================


class Adb:
    def __init__(self, serial=None):
        self.serial = serial

    def run(self, args, timeout=10):
        cmd = ["adb"] + (["-s", self.serial] if self.serial else []) + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def shell(self, command, timeout=12):
        r = self.run(["shell", command], timeout)
        if r.returncode != 0 and not r.stdout.strip():
            raise RuntimeError(r.stderr.strip() or "ADB command failed")
        return r.stdout


def list_devices():
    """Returns None if adb is missing, else a list of (serial, label, state)."""
    try:
        r = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=8)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return []
    out = []
    for line in r.stdout.splitlines()[1:]:
        p = line.split()
        if len(p) >= 2:
            model = next((x.split(":", 1)[1] for x in p[2:] if x.startswith("model:")), "")
            out.append((p[0], f"{model.replace('_', ' ') or 'Android device'} ({p[0]})", p[1]))
    return out


# =============================================================================
#  Parsing helpers
# =============================================================================

BAT_HEALTH = {1: "Unknown", 2: "Good", 3: "Overheat", 4: "Dead", 5: "Over voltage", 6: "Failure", 7: "Cold"}
BAT_STATUS = {1: "Unknown", 2: "Charging", 3: "Discharging", 4: "Not charging", 5: "Full"}


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


FAST_CMD = (
    "grep ^cpu /proc/stat; "
    "echo @@MEM; cat /proc/meminfo; "
    "echo @@BAT; dumpsys battery; "
    "echo @@PS; for f in capacity current_now voltage_now charge_full charge_full_design charge_counter "
    "cycle_count status health technology; do echo \"$f=$(cat /sys/class/power_supply/battery/$f 2>/dev/null)\"; done; "
    "echo @@DF; df -k /data; "
    "echo @@NET; cat /proc/net/dev; "
    "echo @@FREQ; for c in /sys/devices/system/cpu/cpu[0-9]*; do "
    "echo \"$(basename $c) $(cat $c/cpufreq/scaling_cur_freq 2>/dev/null) $(cat $c/cpufreq/cpuinfo_max_freq 2>/dev/null)\"; done; "
    "echo @@THERM; for z in /sys/class/thermal/thermal_zone*; do echo \"$(cat $z/type 2>/dev/null)|$(cat $z/temp 2>/dev/null)\"; done; "
    "echo @@UP; cat /proc/uptime; cat /proc/loadavg"
)

DIAG_CMD = (
    "echo @@PROPS; getprop; "
    "echo @@SEL; getenforce 2>/dev/null; "
    "echo @@SU; which su 2>/dev/null; ls /system/xbin/su /system/bin/su /sbin/su /su/bin/su 2>/dev/null; "
    "echo @@PKG; pm list packages -3 2>/dev/null | wc -l; pm list packages -s 2>/dev/null | wc -l; "
    "pm list packages -d 2>/dev/null | wc -l; "
    "echo @@WM; wm size 2>/dev/null; wm density 2>/dev/null; "
    "echo @@PWR; dumpsys power 2>/dev/null | grep -m4 -E 'mWakefulness=|mIsPowered=|Display Power'; "
    "echo @@WIFI; dumpsys wifi 2>/dev/null | grep -m1 'mWifiInfo'; "
    "echo @@CRASH; logcat -b crash -d -t 300 2>/dev/null | grep -c 'FATAL EXCEPTION'; "
    "echo @@ANR; logcat -b events -d -t 1000 2>/dev/null | grep -c am_anr; "
    "echo @@END"
)

PROP_KEYS = [
    "ro.product.manufacturer", "ro.product.brand", "ro.product.model", "ro.product.device", "ro.product.name",
    "ro.build.version.release", "ro.build.version.sdk", "ro.build.version.security_patch", "ro.build.type",
    "ro.build.tags", "ro.build.fingerprint", "ro.product.cpu.abi", "ro.hardware", "ro.board.platform",
    "ro.boot.verifiedbootstate", "ro.boot.flash.locked", "ro.crypto.state", "ro.debuggable",
    "gsm.operator.alpha", "persist.sys.timezone",
]


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


def parse_battery(bat_txt, ps_txt):
    d = kv(bat_txt)
    ps = {}
    for line in ps_txt.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            ps[k.strip()] = v.strip()

    level = to_int(d.get("level"))
    if level is None:
        level = to_int(ps.get("capacity"))
    if level is None:
        raise RuntimeError("Battery information unavailable")

    temp = to_int(d.get("temperature"))
    mv = to_int(d.get("voltage"))
    if mv is None:
        raw = to_int(ps.get("voltage_now"))
        mv = (raw / 1000 if raw and raw > 20000 else raw) if raw is not None else None

    status = BAT_STATUS.get(to_int(d.get("status")), None) or ps.get("status") or "Unknown"
    health = BAT_HEALTH.get(to_int(d.get("health")), None) or ps.get("health") or "Unknown"
    plugged = [n for n, k in (("AC", "ac powered"), ("USB", "usb powered"),
                              ("Wireless", "wireless powered"), ("Dock", "dock powered")) if d.get(k) == "true"]

    def mah(v):
        return None if v is None or v <= 0 else (v / 1000 if v >= 20000 else float(v))

    counter = mah(to_int(d.get("charge counter")) or to_int(ps.get("charge_counter")))
    design, full = mah(to_int(ps.get("charge_full_design"))), mah(to_int(ps.get("charge_full")))
    soh = None
    if design and full and 0.3 <= full / design <= 1.3:
        soh = min(100.0, full / design * 100)

    cycles = None
    for key in ("cycle count", "cycle_count", "mcyclecount"):
        cycles = to_int(d.get(key))
        if cycles:
            break
    if not cycles:
        cycles = to_int(ps.get("cycle_count")) or None

    cur = to_int(ps.get("current_now"))
    current_ma = None
    if cur is not None:
        mag = abs(cur) / 1000 if abs(cur) >= 10000 else abs(cur)
        current_ma = mag if status in ("Charging", "Full") else -mag
        if status in ("Not charging", "Unknown"):
            current_ma = 0.0 if mag < 5 else current_ma
    volt_v = mv / 1000 if mv is not None else None
    power_w = volt_v * current_ma / 1000 if volt_v is not None and current_ma is not None else None

    eta_h = None
    if current_ma and abs(current_ma) > 20:
        if status == "Discharging" and counter:
            eta_h = counter / abs(current_ma)
        elif status == "Charging" and counter and full:
            eta_h = max(0.0, full - counter) / abs(current_ma)

    mcc, mcv = to_int(d.get("max charging current")), to_int(d.get("max charging voltage"))
    return {
        "level": level, "temp": temp / 10 if temp is not None else None, "volt": volt_v,
        "status": status, "health": health, "plugged": plugged,
        "tech": d.get("technology") or ps.get("technology") or "–",
        "design_mah": design, "full_mah": full, "counter_mah": counter, "soh": soh, "cycles": cycles,
        "current_ma": current_ma, "power_w": power_w, "eta_h": eta_h,
        "max_ma": mcc / 1000 if mcc else None, "max_v": mcv / 1e6 if mcv else None,
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


def parse_net(text):
    rx = tx = 0
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        if name.strip() == "lo":
            continue
        v = data.split()
        if len(v) >= 9:
            rx += int(v[0])
            tx += int(v[8])
    return rx, tx


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


def parse_top(text):
    lines = text.splitlines()
    hi = next((i for i, l in enumerate(lines) if "PID" in l and "CPU" in l), None)
    if hi is None:
        return []
    hdr = lines[hi].replace("S[%CPU]", "S %CPU").split()
    i_pid = next(i for i, h in enumerate(hdr) if h == "PID")
    i_cpu = next(i for i, h in enumerate(hdr) if "CPU" in h)
    i_mem = next((i for i, h in enumerate(hdr) if h in ("%MEM", "MEM%")), None)
    out = []
    for l in lines[hi + 1:]:
        f = l.split(None, len(hdr) - 1)
        if len(f) < len(hdr):
            continue
        try:
            out.append({"PID": int(f[i_pid]), "Process": f[-1].strip(), "CPU %": float(f[i_cpu].replace("%", "")),
                        "MEM %": float(f[i_mem].replace("%", "")) if i_mem is not None else None})
        except ValueError:
            continue
    out.sort(key=lambda p: -p["CPU %"])
    return out[:12]


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


# =============================================================================
#  Background monitor (threads, shared across browser sessions)
# =============================================================================


class Monitor:
    def __init__(self):
        self.lock = threading.RLock()
        self.serial, self.interval = None, 1.0
        self.history = deque(maxlen=MAX_HISTORY)
        self.procs, self.diag = [], {}
        self.error, self.connected = "Connecting to device…", False
        self.force_diag = False
        self._prev_cpu, self._prev_net = {}, None
        self._started = False

    def configure(self, serial, interval):
        with self.lock:
            if serial != self.serial:
                self.serial = serial
                self.history.clear()
                self.procs, self.diag = [], {}
                self._prev_cpu, self._prev_net = {}, None
                self.error, self.connected = "Connecting to device…", False
            self.interval = interval

    def start(self):
        if not self._started:
            self._started = True
            threading.Thread(target=self._fast_loop, daemon=True).start()
            threading.Thread(target=self._slow_loop, daemon=True).start()

    def sample(self, adb):
        sec = sections(adb.shell(FAST_CMD), "CPU")
        if "UP" not in sec:
            raise RuntimeError("Unexpected output from device")
        cpu, cores = parse_cpu(sec["CPU"], self._prev_cpu)
        bat = parse_battery(sec["BAT"], sec["PS"])
        rx_t, tx_t = parse_net(sec["NET"])
        now = time.monotonic()
        prev, self._prev_net = self._prev_net, (rx_t, tx_t, now)
        rx = tx = 0.0
        if prev and now > prev[2]:
            dt = now - prev[2]
            rx, tx = max(0, rx_t - prev[0]) / dt / 1024, max(0, tx_t - prev[1]) / dt / 1024

        zones = parse_thermal(sec.get("THERM", ""))
        cpu_zones = [t for n, t in zones if any(h in n.lower() for h in CPU_ZONE_HINTS)]
        up_lines = sec["UP"].strip().splitlines()
        uptime = float(up_lines[0].split()[0]) if up_lines and up_lines[0].split() else None
        load = [float(x) for x in up_lines[1].split()[:3]] if len(up_lines) > 1 else []

        s = {
            "t": time.time(), "cpu": cpu, "cores": cores, "freqs": parse_freq(sec.get("FREQ", "")),
            **parse_ram(sec["MEM"]), **parse_storage(sec["DF"]),
            "battery": bat, "bat": bat["level"], "temp": bat["temp"], "volt": bat["volt"],
            "current_ma": bat["current_ma"], "power_w": bat["power_w"],
            "rx": rx, "tx": tx, "rx_total": rx_t, "tx_total": tx_t,
            "zones": zones, "cpu_temp": max(cpu_zones) if cpu_zones else None,
            "max_temp": max([t for _, t in zones] + ([bat["temp"]] if bat["temp"] is not None else []) or [0]),
            "uptime": uptime, "load": load,
        }
        return s

    def _fast_loop(self):
        while True:
            started = time.monotonic()
            try:
                s = self.sample(Adb(self.serial))
                with self.lock:
                    self.history.append(s)
                    self.error, self.connected = None, True
            except FileNotFoundError:
                self._fail("`adb` not found - install Android platform-tools and add it to PATH.")
            except subprocess.TimeoutExpired:
                self._fail("Device timed out - is the phone awake and connected?")
            except Exception as e:  # noqa: BLE001
                self._fail(str(e))
            time.sleep(max(0.05, self.interval - (time.monotonic() - started)))

    def _fail(self, msg):
        with self.lock:
            self.error, self.connected = msg, False
            self._prev_cpu, self._prev_net = {}, None
        time.sleep(1.5)

    def _slow_loop(self):
        last_diag = 0.0
        while True:
            try:
                adb = Adb(self.serial)
                if self.connected:
                    procs = parse_top(adb.shell("top -b -n 1 -m 12", timeout=15))
                    with self.lock:
                        self.procs = procs
                    if self.force_diag or not self.diag or time.time() - last_diag > 45:
                        self.force_diag = False
                        diag = parse_diag(adb.shell(DIAG_CMD, timeout=30))
                        with self.lock:
                            self.diag = diag
                        last_diag = time.time()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2.0 if not self.diag else max(2.0, self.interval * 2))

    def snapshot(self):
        with self.lock:
            return {"history": list(self.history), "procs": list(self.procs), "diag": dict(self.diag),
                    "error": self.error, "connected": self.connected}


# =============================================================================
#  Phone condition assessment
# =============================================================================


def assess(df, s, diag):
    comps, finds = [], []

    def add(name, score, weight, detail):
        comps.append({"name": name, "score": max(0.0, min(100.0, float(score))), "weight": weight, "detail": detail})

    def find(level, msg):
        finds.append((level, msg))

    b = s["battery"]
    recent = df.tail(30)

    # --- battery health
    soh, cyc = b["soh"], b["cycles"]
    if soh is not None:
        sc, detail = interp(soh, [(50, 0), (90, 100)]), f"{soh:.0f}% of design capacity"
        if soh < 80:
            find("bad" if soh < 70 else "warn", f"Battery has worn down to {soh:.0f}% of its original capacity.")
    else:
        sc = {"Good": 90, "Unknown": 70, "Cold": 55, "Overheat": 45}.get(b["health"], 15)
        detail = f"Reported “{b['health']}” (capacity wear not exposed)"
        if b["health"] not in ("Good", "Unknown"):
            find("bad", f"Android reports the battery health as “{b['health']}”.")
    if cyc:
        sc -= interp(cyc, [(300, 0), (1000, 30)])
        detail += f", {cyc} cycles"
        if cyc > 800:
            find("warn", f"High battery cycle count ({cyc}).")
    add("Battery Health", sc, 30, detail)

    # --- thermals
    bt, ct = b["temp"], s["cpu_temp"]
    parts = []
    if bt is not None:
        parts.append(interp(bt, [(30, 100), (38, 100), (45, 60), (55, 0)]))
    if ct is not None:
        parts.append(interp(ct, [(45, 100), (60, 100), (75, 50), (90, 0)]))
    if parts:
        add("Thermals", min(parts), 20, f"Battery {bt:.1f} °C" + (f", CPU {ct:.0f} °C" if ct is not None else ""))
        if bt is not None and bt >= 42:
            find("warn" if bt < 47 else "bad", f"Battery is running hot ({bt:.1f} °C).")
        if ct is not None and ct >= 75:
            find("warn" if ct < 85 else "bad", f"CPU temperature is high ({ct:.0f} °C).")

    # --- memory / storage / cpu
    ram = recent["ram"].mean()
    add("Memory", interp(ram, [(60, 100), (75, 90), (90, 40), (97, 0)]), 15,
        f"{ram:.0f}% in use ({s['ram_used'] / 1024:.1f} / {s['ram_total'] / 1024:.1f} GB)")
    if ram >= 90:
        find("warn", f"Memory is under pressure ({ram:.0f}% used) — close background apps.")

    stor = s["storage"]
    add("Storage", interp(stor, [(70, 100), (85, 75), (95, 25), (99, 0)]), 15,
        f"{stor:.0f}% full, {s['st_free']:.1f} GB free")
    if stor >= 90:
        find("bad" if stor >= 95 else "warn", f"Storage is almost full ({s['st_free']:.1f} GB free).")

    cpu = recent["cpu"].mean()
    add("CPU Load", interp(cpu, [(40, 100), (70, 85), (90, 40), (100, 10)]), 10, f"{cpu:.0f}% average")
    if cpu >= 85:
        find("warn", f"CPU is under sustained heavy load ({cpu:.0f}%).")

    # --- security
    props = diag.get("props", {}) if diag else {}
    if props:
        sec_score, notes = 100.0, []
        patch = props.get("ro.build.version.security_patch")
        try:
            age = (date.today() - datetime.strptime(patch, "%Y-%m-%d").date()).days
            sec_score = interp(age, [(0, 100), (90, 100), (180, 75), (365, 40), (730, 10)])
            notes.append(f"patch {age}d old")
            if age > 180:
                find("warn" if age < 365 else "bad", f"Security patch is {age} days old ({patch}).")
        except Exception:  # noqa: BLE001
            pass
        boot = props.get("ro.boot.verifiedbootstate")
        if boot and boot != "green":
            sec_score = min(sec_score, 60)
            notes.append(f"boot state {boot}")
            find("warn", f"Verified boot state is “{boot}” (bootloader may be unlocked).")
        if diag.get("rooted"):
            sec_score = min(sec_score, 40)
            notes.append("rooted")
            find("warn", "Root access (su) detected.")
        if props.get("ro.crypto.state") not in (None, "", "encrypted"):
            sec_score = min(sec_score, 50)
            find("bad", "Device storage does not appear to be encrypted.")
        if diag.get("selinux") == "Permissive":
            sec_score = min(sec_score, 40)
            find("bad", "SELinux is in permissive mode.")
        add("Security", sec_score, 10, ", ".join(notes) or "verified & clean")

    if diag and (diag.get("crashes") or 0) > 0:
        find("warn", f"{diag['crashes']} app crash(es) in the recent system log.")
    if diag and (diag.get("anrs") or 0) > 0:
        find("warn", f"{diag['anrs']} app-not-responding event(s) in the recent system log.")

    total_w = sum(c["weight"] for c in comps) or 1
    score = sum(c["score"] * c["weight"] for c in comps) / total_w
    label = "Excellent" if score >= 85 else "Good" if score >= 70 else "Fair" if score >= 50 else "Needs Attention"
    level = "ok" if score >= 70 else "warn" if score >= 50 else "bad"
    if not finds:
        find("ok", "No problems detected — all telemetry within normal parameters.")
    finds.sort(key=lambda f: {"bad": 0, "warn": 1, "ok": 2}[f[0]])
    return {"score": score, "label": label, "level": level, "components": comps, "findings": finds}


# =============================================================================
#  UI & Styling Helpers
# =============================================================================

try:
    _ST_VER = tuple(int(x) for x in st.__version__.split(".")[:2])
except Exception:  # noqa: BLE001
    _ST_VER = (1, 40)
_NEW, _OLD = {"width": "stretch"}, {"use_container_width": True}
STRETCH, STRETCH_ALT = (_NEW, _OLD) if _ST_VER >= (1, 50) else (_OLD, _NEW)


def stretch(fn, *a, **k):
    """Call a Streamlit element full-width across old/new API versions."""
    try:
        return fn(*a, **STRETCH, **k)
    except TypeError:
        return fn(*a, **STRETCH_ALT, **k)


def theme_is_dark():
    try:
        t = {"dark": True, "light": False}.get(st.context.theme.type)
        if t is not None:
            return t
    except Exception:  # noqa: BLE001
        pass
    try:
        return {"dark": True, "light": False}.get(st.get_option("theme.base"))
    except Exception:  # noqa: BLE001
        return None


def make_pal():
    dark = theme_is_dark()
    if dark is None or dark:
        p = dict(
            cpu="#60a5fa", ram="#a78bfa", bat="#34d399", tmp="#fb923c", sto="#f472b6",
            rx="#22d3ee", tx="#facc15", ok="#34d399", warn="#fbbf24", bad="#f87171",
            txt="#f8fafc", mut="#cbd5e1", grid="rgba(148,163,184,0.16)", track="rgba(148,163,184,0.14)",
            hover_bg="rgba(15,23,42,0.92)"
        )
    else:
        p = dict(
            cpu="#2563eb", ram="#7c3aed", bat="#059669", tmp="#ea580c", sto="#db2777",
            rx="#0891b2", tx="#d97706", ok="#059669", warn="#d97706", bad="#e11d48",
            txt="#0f172a", mut="#334155", grid="rgba(100,116,139,0.20)", track="rgba(100,116,139,0.14)",
            hover_bg="rgba(255,255,255,0.95)"
        )
    if dark is None:  # theme unknown: use mid-tones that stay readable on both backgrounds
        p.update(txt="#94a3b8", mut="#8b9ab0")
    return p


P = make_pal()


def rgba(hex_color, a):
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def fmt_mb(m):
    return f"{m / 1024:.1f} GB" if m >= 1024 else f"{m:.0f} MB"


def fmt_rate(kb):
    return f"{kb / 1024:.2f} MB/s" if kb >= 1024 else f"{kb:.0f} KB/s"


def fmt_bytes(b):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or unit == "TB":
            return f"{b:.1f} {unit}" if unit != "B" else f"{b:.0f} B"
        b /= 1024


def fmt_dur(sec):
    if sec is None:
        return "–"
    sec = int(sec)
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    return (f"{d}d " if d else "") + f"{h}h {m}m"


def level_color(level):
    return P[level]


def base_layout(fig, h):
    fig.update_layout(
        height=h, margin=dict(l=14, r=18, t=24, b=14),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=P["mut"], size=13),
        hovermode="x unified", showlegend=False,
        hoverlabel=dict(bgcolor=P["hover_bg"], bordercolor=P["grid"], font=dict(family="Inter, sans-serif", size=12, color=P["txt"])),
    )
    axis = dict(automargin=True, tickfont=dict(size=12, color=P["mut"]), showline=True, linecolor=P["grid"],
                ticks="outside", tickcolor=P["grid"], ticklen=4)
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def gauge(value, color, rng=(0, 100), suffix="%", steps=None, h=200, decimals=0):
    """Half-dial gauge with room around it so the big value and scale numbers are never clipped."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        domain={"x": [0.04, 0.96], "y": [0.14, 0.94]},
        number={"suffix": suffix, "font": {"size": 30, "color": P["txt"], "family": "Inter, sans-serif"},
                "valueformat": f".{decimals}f"},
        gauge={
            "axis": {"range": list(rng), "nticks": 5, "tickcolor": P["mut"],
                     "tickfont": {"color": P["mut"], "size": 12}},
            "bar": {"color": color, "thickness": 0.36},
            "bgcolor": P["track"], "borderwidth": 0,
            "steps": steps or [],
        },
    ))
    fig.update_layout(
        height=h, margin=dict(l=19, r=16, t=16, b=22),
        paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", color=P["txt"]),
    )
    return fig


def donut(labels, values, colors, center, h=260):
    """Compact donut: percentage in the middle with a small label, ring slightly thicker for clarity."""
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.68, sort=False, direction="clockwise", rotation=0,
        marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0)", width=0)),
        textinfo="none", hovertemplate="<b>%{label}</b>: %{value:.1f}<extra></extra>",
        domain=dict(x=[0.16, 0.84], y=[0.04, 0.96]),
    ))
    fig.update_layout(
        height=h, margin=dict(l=6, r=6, t=6, b=6), paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
        annotations=[dict(
            text=f"<b>{center}</b><br><span style='font-size:12px'>{labels[0]}</span>",
            x=0.5, y=0.5, showarrow=False, align="center",
            font=dict(family="Inter, sans-serif", size=22, color=P["txt"]),
        )],
    )
    return fig


def area(df, series, h=250, ymin=0, ymax=None, unit="", fill=True):
    fig = go.Figure()
    x = [datetime.fromtimestamp(t) for t in df["t"]]
    for name, col, color in series:
        fig.add_trace(go.Scatter(
            x=x, y=df[col], name=name, mode="lines",
            line=dict(color=color, width=2.4, shape="spline", smoothing=0.55),
            fill="tozeroy" if fill else None, fillcolor=rgba(color, 0.12),
            hovertemplate=f"<b>{name}</b>: %{{y:.1f}}{unit}<extra></extra>",
        ))
    base_layout(fig, h)
    fig.update_xaxes(showgrid=False, color=P["mut"], tickformat="%H:%M:%S", nticks=6)
    fig.update_yaxes(gridcolor=P["grid"], zeroline=False, range=[ymin, ymax] if ymax is not None else None,
                     color=P["mut"], ticksuffix=unit if len(unit) <= 2 else "")
    if len(series) > 1:
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.14, x=0, font=dict(size=11)))
    return fig


def bars(x, y, color, h=240, unit="", ymax=None, text=True):
    fig = go.Figure(go.Bar(
        x=x, y=y, marker=dict(color=color, cornerradius=5),
        text=[f"{v:.0f}{unit}" for v in y] if text else None, textposition="outside",
        textfont=dict(color=P["mut"], size=12), cliponaxis=False,
        hovertemplate="<b>%{x}</b>: %{y:.1f}" + unit + "<extra></extra>"
    ))
    base_layout(fig, h)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(showgrid=False, color=P["mut"])
    fig.update_yaxes(gridcolor=P["grid"], zeroline=False, color=P["mut"], range=[0, ymax] if ymax else None)
    return fig


def hbars(labels, values, color, h=330, unit=""):
    """Horizontal bars: long names stay readable on the y-axis, biggest value on top."""
    labels = [str(l) if len(str(l)) <= 24 else str(l)[:23] + "…" for l in labels]
    values = [float(v) for v in values]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h", marker=dict(color=color, cornerradius=5),
        text=[f"{v:.1f}{unit}" for v in values], textposition="outside", cliponaxis=False,
        textfont=dict(color=P["mut"], size=12),
        hovertemplate="<b>%{y}</b>: %{x:.1f}" + unit + "<extra></extra>",
    ))
    base_layout(fig, h)
    fig.update_layout(hovermode="closest", margin=dict(l=10, r=48, t=10, b=10), bargap=0.35)
    fig.update_xaxes(gridcolor=P["grid"], zeroline=False, showline=False, ticks="",
                     range=[0, max(max(values, default=1), 1) * 1.2])
    fig.update_yaxes(autorange="reversed", showgrid=False, showline=False, ticks="")
    return fig


def proc_columns(df, color, h=340):
    """Clean column chart: no text on the bars or x-axis; hover shows the full process name."""
    fig = go.Figure(go.Bar(
        x=list(range(1, len(df) + 1)), y=df["CPU %"], marker=dict(color=color, cornerradius=5),
        customdata=list(zip(df["Process"], df["PID"])),
        hovertemplate="<b>%{customdata[0]}</b><br>PID %{customdata[1]} · CPU %{y:.1f}%<extra></extra>",
    ))
    base_layout(fig, h)
    fig.update_layout(hovermode="closest", bargap=0.3, margin=dict(l=14, r=18, t=12, b=10))
    fig.update_xaxes(showticklabels=False, showgrid=False, showline=False, ticks="")
    fig.update_yaxes(gridcolor=P["grid"], zeroline=False, ticksuffix="%", rangemode="tozero")
    return fig


def plot(fig, key):
    stretch(st.plotly_chart, fig, key=key, theme=None, config={"displayModeBar": False})


def card(title=None, icon=None):
    box = st.container(border=True)
    if title:
        prefix = f"<span class='card-ico'>{icon}</span>" if icon else ""
        box.markdown(f"<div class='card-hdr'>{prefix}<span>{title}</span></div>", unsafe_allow_html=True)
    return box


def badge(text, level):
    st.markdown(f"<span class='badge' style='--c:{level_color(level)}'>{text}</span>", unsafe_allow_html=True)


def render_comp_bars(components):
    html = ["<div class='comp-list'>"]
    for comp in components:
        sc = comp["score"]
        lvl = "ok" if sc >= 75 else "warn" if sc >= 50 else "bad"
        col = level_color(lvl)
        html.append(
            f"<div class='comp-row'>"
            f"  <div class='comp-top'>"
            f"    <span class='comp-name'>{comp['name']}</span>"
            f"    <span class='comp-detail'>{comp['detail']}</span>"
            f"    <span class='comp-score' style='color:{col}'>{sc:.0f}<small>/100</small></span>"
            f"  </div>"
            f"  <div class='comp-track'><div class='comp-fill' style='width:{sc:.1f}%;background:{col}'></div></div>"
            f"</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_findings(findings):
    icons = {"ok": "✓", "warn": "!", "bad": "✕"}
    html = ["<div class='finding-list'>"]
    for lvl, msg in findings:
        col = level_color(lvl)
        html.append(
            f"<div class='finding-item' style='--c:{col}'>"
            f"  <span class='finding-ico'>{icons[lvl]}</span>"
            f"  <span class='finding-msg'>{msg}</span>"
            f"</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def to_df(hist):
    keep = [{k: v for k, v in s.items() if not isinstance(v, (list, dict))} for s in hist]
    return pd.DataFrame(keep)


def v_or(v, fmt="{}", dash="–"):
    return dash if v is None else fmt.format(v)


# =============================================================================
#  Pages
# =============================================================================


def page_overview(c):
    s, a = c.s, c.assess
    left, right = st.columns([1.05, 1.95], gap="medium")
    with left:
        with card("Overall Device Health", "🛡️"):
            plot(gauge(a["score"], level_color(a["level"]), suffix="", h=205), "g_overall")
            st.markdown(
                f"<div style='text-align:center;margin-top:-6px;margin-bottom:8px'>"
                f"<span class='badge' style='--c:{level_color(a['level'])}'>{a['label']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.caption("Weighted composite score across battery wear, thermals, memory pressure, storage, CPU load, and OS security.")
    with right:
        with card("Subsystem Breakdown", "📊"):
            render_comp_bars(a["components"])
        with card("Active Diagnostic Findings", "🔍"):
            render_findings(a["findings"])

    cols = st.columns(6)
    b = s["battery"]
    cols[0].metric("CPU Load", f"{s['cpu']:.0f}%", f"{len(s['cores'])} cores" if s["cores"] else None, delta_color="off")
    cols[1].metric("RAM Usage", f"{s['ram']:.0f}%", f"{fmt_mb(s['ram_used'])} / {fmt_mb(s['ram_total'])}", delta_color="off")
    cols[2].metric("Battery", f"{b['level']}%", b["status"], delta_color="off")
    cols[3].metric("Thermals", v_or(b["temp"], "{:.1f} °C"), f"CPU {s['cpu_temp']:.0f} °C" if s["cpu_temp"] else "Battery sensor", delta_color="off")
    cols[4].metric("Free Storage", f"{s['st_free']:.1f} GB", f"{100 - s['storage']:.0f}% available", delta_color="off")
    cols[5].metric("System Uptime", fmt_dur(s["uptime"]), f"Load {s['load'][0]:.2f}" if s["load"] else None, delta_color="off")

    l, r = st.columns(2)
    with l:
        with card("CPU & Memory Utilisation", "⚡"):
            plot(area(c.df, [("CPU", "cpu", P["cpu"]), ("Memory", "ram", P["ram"])], ymax=100, unit="%"), "o_cm")
    with r:
        with card("Network Throughput", "🌐"):
            plot(area(c.df, [("Download", "rx", P["rx"]), ("Upload", "tx", P["tx"])], unit=" KB/s"), "o_net")


def page_battery(c):
    s = c.s
    b = s["battery"]
    g1, g2, g3 = st.columns(3)
    low = b["level"] <= 15 and b["status"] not in ("Charging", "Full")
    with g1:
        with card("State of Charge", "🔋"):
            plot(gauge(b["level"], P["bad"] if low else P["bat"]), "b_level")
            eta = b["eta_h"]
            eta_txt = "Estimating…" if eta is None else f"~{int(eta)}h {int((eta % 1) * 60)}m to {'full' if b['status'] == 'Charging' else 'empty'}"
            st.caption(f"Status: **{b['status']}** · {eta_txt}")
    with g2:
        with card("Capacity Health (SoH)", "❤️‍🩹"):
            if b["soh"] is not None:
                col = P["ok"] if b["soh"] >= 85 else P["warn"] if b["soh"] >= 70 else P["bad"]
                plot(gauge(b["soh"], col, rng=(50, 100)), "b_soh")
                st.caption(f"Full charge: **{b['full_mah']:.0f} mAh** vs **{b['design_mah']:.0f} mAh** design")
            else:
                st.markdown(
                    f"<div class='empty-stat'><div class='empty-val'>{b['health']}</div>"
                    f"<div class='empty-lbl'>Android Health Flag</div></div>",
                    unsafe_allow_html=True,
                )
                st.caption("Charge counter / design capacity registers are not exposed over ADB on this kernel.")
    with g3:
        with card("Pack Temperature", "🌡️"):
            t = b["temp"] if b["temp"] is not None else 0
            steps = [
                {"range": [0, 38], "color": rgba(P["ok"], 0.18)},
                {"range": [38, 45], "color": rgba(P["warn"], 0.22)},
                {"range": [45, 60], "color": rgba(P["bad"], 0.25)},
            ]
            plot(gauge(t, P["tmp"], rng=(0, 60), suffix=" °C", steps=steps, decimals=1), "b_temp")
            st.caption("Optimal operating range: **20 °C – 38 °C**")

    m = st.columns(6)
    m[0].metric("Power Source", ", ".join(b["plugged"]) or "Battery")
    m[1].metric("Current Flow", v_or(b["current_ma"], "{:+.0f} mA"))
    m[2].metric("Real-time Power", v_or(b["power_w"], "{:+.2f} W"))
    m[3].metric("Voltage", v_or(b["volt"], "{:.3f} V"))
    m[4].metric("Cycle Count", v_or(b["cycles"]))
    m[5].metric("Chemistry", b["tech"])

    l, r = st.columns(2)
    with l:
        with card("Charge Level Curve", "📈"):
            plot(area(c.df, [("Level", "bat", P["bat"])], ymax=100, unit="%"), "b_lvl")
    with r:
        with card("Thermal Curve", "🔥"):
            plot(area(c.df, [("Battery", "temp", P["tmp"])], ymin=None, unit=" °C"), "b_tmp")
    l, r = st.columns(2)
    with l:
        with card("Current Draw (+ Charge / − Discharge)", "⚡"):
            if c.df["current_ma"].notna().any():
                plot(area(c.df.fillna(0), [("Current", "current_ma", P["rx"])], ymin=None, unit=" mA"), "b_cur")
            else:
                st.info("Instantaneous current (`current_now`) isn't exposed by this device.")
    with r:
        with card("Cell Voltage Stability", "🔌"):
            plot(area(c.df, [("Voltage", "volt", P["tx"])], ymin=None, unit=" V", fill=False), "b_volt")


def page_cpu(c):
    s = c.s
    m = st.columns(5)
    m[0].metric("Total CPU Load", f"{s['cpu']:.0f}%")
    m[1].metric("Logical Cores", len(s["cores"]) or "–")
    for i, lab in enumerate(("Load Avg (1m)", "Load Avg (5m)", "Load Avg (15m)")):
        m[2 + i].metric(lab, f"{s['load'][i]:.2f}" if len(s["load"]) > i else "–")

    l, r = st.columns([3, 2])
    with l:
        with card("Aggregate CPU Utilisation", "📈"):
            plot(area(c.df, [("CPU", "cpu", P["cpu"])], ymax=100, unit="%", h=280), "c_hist")
    with r:
        with card("Per-Core Load", "🎛️"):
            if s["cores"]:
                plot(bars([f"C{i}" for i in range(len(s["cores"]))], s["cores"], P["cpu"], h=280, unit="%", ymax=115), "c_cores")

    l, r = st.columns(2)
    with l:
        with card("Core Clocks (Current vs Max MHz)", "⏱️"):
            if s["freqs"]:
                fr = s["freqs"]
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=[f["core"] for f in fr], y=[f["max"] for f in fr], name="Max Clock",
                    marker=dict(color=P["track"], cornerradius=5),
                    hovertemplate="<b>%{x} Max</b>: %{y:.0f} MHz<extra></extra>"
                ))
                fig.add_trace(go.Bar(
                    x=[f["core"] for f in fr], y=[f["cur"] for f in fr], name="Current Clock",
                    marker=dict(color=P["ram"], cornerradius=5),
                    hovertemplate="<b>%{x} Cur</b>: %{y:.0f} MHz<extra></extra>"
                ))
                base_layout(fig, 260)
                fig.update_layout(barmode="overlay", hovermode="x unified", showlegend=True,
                                  legend=dict(orientation="h", y=1.14, x=0, font=dict(size=11)))
                fig.update_xaxes(showgrid=False, color=P["mut"])
                fig.update_yaxes(gridcolor=P["grid"], color=P["mut"])
                plot(fig, "c_freq")
            else:
                st.info("Per-core `cpufreq` nodes are restricted on this device.")
    with r:
        with card("SoC & Battery Thermal History", "🌡️"):
            cols = [("Battery", "temp", P["tmp"])]
            if c.df["cpu_temp"].notna().any():
                cols.append(("CPU / SoC", "cpu_temp", P["bad"]))
            plot(area(c.df, cols, ymin=None, unit=" °C", h=260, fill=False), "c_temp")

    with card("Thermal Zone Sensors", "🧭"):
        if s["zones"]:
            z = pd.DataFrame(s["zones"], columns=["Sensor", "°C"]).groupby("Sensor", as_index=False)["°C"].max()
            z = z.sort_values("°C", ascending=False).reset_index(drop=True)
            stretch(st.dataframe, z.head(15), hide_index=True,
                    column_config={"°C": st.column_config.ProgressColumn("Temperature (°C)", min_value=0, max_value=100, format="%.1f °C")})
        else:
            st.info("Thermal zone sensors are not readable without root on this device.")


def page_memory(c):
    s = c.s
    l, m, r = st.columns(3)
    with l:
        with card("System RAM", "🧠"):
            plot(donut(["Used", "Available"], [s["ram_used"], s["ram_total"] - s["ram_used"]],
                       [P["ram"], P["track"]], f"{s['ram']:.0f}%"), "m_ram")
            st.caption(f"**{fmt_mb(s['ram_used'])}** active · **{fmt_mb(s['ram_total'] - s['ram_used'])}** available of **{fmt_mb(s['ram_total'])}**")
    with m:
        with card("Swap / zRAM", "🔄"):
            if s["swap_total"]:
                pct = s["swap_used"] / s["swap_total"] * 100
                plot(donut(["Used", "Free"], [s["swap_used"], s["swap_total"] - s["swap_used"]],
                           [P["tmp"], P["track"]], f"{pct:.0f}%"), "m_swap")
                st.caption(f"**{fmt_mb(s['swap_used'])}** compressed in zRAM of **{fmt_mb(s['swap_total'])}**")
            else:
                st.info("No swap / zRAM configured.")
    with r:
        with card("User Partition (/data)", "💾"):
            plot(donut(["Used", "Free"], [s["st_used"], s["st_free"]], [P["sto"], P["track"]], f"{s['storage']:.0f}%"), "m_sto")
            st.caption(f"**{s['st_used']:.1f} GB** used · **{s['st_free']:.1f} GB** free of **{s['st_total']:.1f} GB**")

    with card("Memory Allocation Timeline", "📉"):
        d = c.df.assign(ram_gb=c.df["ram_used"] / 1024, swap_gb=c.df["swap_used"] / 1024)
        plot(area(d, [("RAM Used", "ram_gb", P["ram"]), ("Swap Used", "swap_gb", P["tmp"])], unit=" GB", h=265), "m_hist")


def page_network(c):
    s, w = c.s, (c.diag.get("wifi") or {})
    m = st.columns(5)
    m[0].metric("Download Rate", fmt_rate(s["rx"]))
    m[1].metric("Upload Rate", fmt_rate(s["tx"]))
    m[2].metric("Session Peak ↓", fmt_rate(c.df["rx"].max()))
    m[3].metric("Total RX (Boot)", fmt_bytes(s["rx_total"]))
    m[4].metric("Total TX (Boot)", fmt_bytes(s["tx_total"]))

    l, r = st.columns([2.8, 1.2])
    with l:
        with card("Real-Time Bandwidth", "📡"):
            plot(area(c.df, [("Download", "rx", P["rx"]), ("Upload", "tx", P["tx"])], h=300, unit=" KB/s"), "n_hist")
    with r:
        with card("Wi-Fi Link Quality", "📶"):
            if w.get("rssi") is not None:
                q = interp(w["rssi"], [(-95, 0), (-85, 20), (-70, 55), (-55, 85), (-40, 100)])
                plot(gauge(q, P["ok"] if q >= 55 else P["warn"] if q >= 30 else P["bad"], h=180), "n_sig")
                ssid_name = w.get("ssid") if w.get("ssid") and not w["ssid"].startswith("<") else "Connected WLAN"
                band = {2: "2.4 GHz", 5: "5 GHz", 6: "6 GHz"}.get(int(str(w["freq"])[0]), "") if w.get("freq") else ""
                meta = " · ".join(x for x in (f"{w['rssi']} dBm", f"{w['speed']} Mbps" if w.get("speed") else None, band) if x)
                st.markdown(
                    f"<div style='text-align:center;margin-top:-4px'>"
                    f"<div style='font-weight:700;font-size:.98rem'>{ssid_name}</div>"
                    f"<div style='opacity:.68;font-size:.82rem;font-family:JetBrains Mono,monospace'>{meta}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("Wi-Fi interface is disconnected or link info is unavailable.")


def page_diag(c):
    d, props = c.diag, c.diag.get("props", {})
    if not d:
        st.info("Gathering deep hardware & security diagnostics…")
        return
    g = props.get
    l, r = st.columns(2)
    with l:
        with card("Hardware & OS Profile", "📱"):
            rows = [
                ("Model", f"{(g('ro.product.manufacturer') or '').title()} {g('ro.product.model', '')}".strip()),
                ("Codename", g("ro.product.device", "–")),
                ("Android Version", f"Android {g('ro.build.version.release', '–')} (API {g('ro.build.version.sdk', '–')})"),
                ("Security Patch", g("ro.build.version.security_patch", "–")),
                ("Build Type", f"{g('ro.build.type', '–')} · {g('ro.build.tags', '–')}"),
                ("SoC / Platform", f"{g('ro.board.platform') or g('ro.hardware', '–')} ({g('ro.product.cpu.abi', '–')})"),
                ("Display", " · ".join(x for x in (d["display"].get("size"),
                                                   f"{d['display']['density']} dpi" if d["display"].get("density") else None,
                                                   d["display"].get("state")) if x) or "–"),
                ("Carrier / TZ", f"{g('gsm.operator.alpha') or '–'} · {g('persist.sys.timezone', '–')}"),
            ]
            html = ["<div class='kv-list'>"]
            for k_lbl, val in rows:
                html.append(f"<div class='kv-row'><span class='kv-k'>{k_lbl}</span><span class='kv-v'>{val}</span></div>")
            html.append("</div>")
            st.markdown("".join(html), unsafe_allow_html=True)

    with r:
        with card("Security & Integrity Audit", "🔒"):
            boot = g("ro.boot.verifiedbootstate")
            enc = g("ro.crypto.state")
            checks = [
                ("Verified Boot (AVB)", boot == "green" if boot else None, boot or "unknown"),
                ("Bootloader Status", (g("ro.boot.flash.locked") == "1") if g("ro.boot.flash.locked") else None,
                 {"1": "locked", "0": "unlocked"}.get(g("ro.boot.flash.locked"), "unknown")),
                ("File-Based Encryption", (enc == "encrypted") if enc else None, enc or "unknown"),
                ("SELinux Mode", (d.get("selinux") == "Enforcing") if d.get("selinux") else None,
                 d.get("selinux") or "unknown"),
                ("Root Binaries (su)", not d.get("rooted"), "su binary found" if d.get("rooted") else "clean"),
                ("Build Debuggability", (g("ro.debuggable") == "0") if g("ro.debuggable") else None,
                 "ro.debuggable=0" if g("ro.debuggable") == "0" else f"ro.debuggable={g('ro.debuggable', '?')}"),
            ]
            html = ["<div class='sec-list'>"]
            for name, ok, note in checks:
                lvl = "ok" if ok else "warn" if ok is False else "mut"
                col = P[lvl] if lvl in P else P["mut"]
                pill = "PASS" if ok else "WARN" if ok is False else "N/A"
                html.append(
                    f"<div class='sec-row'>"
                    f"  <div><div class='sec-title'>{name}</div><div class='sec-note'>{note}</div></div>"
                    f"  <span class='badge' style='--c:{col}'>{pill}</span>"
                    f"</div>"
                )
            html.append("</div>")
            st.markdown("".join(html), unsafe_allow_html=True)

    l, r = st.columns(2)
    with l:
        with card("Package & Stability Telemetry", "📦"):
            a = d.get("apps", {})
            m = st.columns(3)
            m[0].metric("User Packages", v_or(a.get("user")))
            m[1].metric("System Packages", v_or(a.get("system")))
            m[2].metric("Disabled", v_or(a.get("disabled")))
            m = st.columns(2)
            m[0].metric("Recent App Crashes", v_or(d.get("crashes")), help="FATAL EXCEPTION entries in logcat crash buffer")
            m[1].metric("Recent ANRs", v_or(d.get("anrs")), help="am_anr events in logcat event buffer")
    with r:
        with card("Diagnostic Summary", "🩺"):
            render_findings(c.assess["findings"])
            st.caption(f"Last deep scan at **{datetime.fromtimestamp(d['time']).strftime('%H:%M:%S')}** · auto-refreshes every 45s")

    with st.expander("View Raw Telemetry Payload (JSON)"):
        st.json({"diagnostics": d, "assessment": c.assess}, expanded=False)


def page_procs(c):
    if not c.procs:
        st.info("Sampling process table (`top`)…")
        return
    df = pd.DataFrame(c.procs)
    l, r = st.columns([3, 2])
    with l:
        with card("Active Processes (Top 12 by CPU)", "⚙️"):
            stretch(st.dataframe, df, hide_index=True, column_config={
                "PID": st.column_config.NumberColumn("PID", format="%d"),
                "Process": st.column_config.TextColumn("Package / Binary"),
                "CPU %": st.column_config.ProgressColumn("CPU %", min_value=0, max_value=max(100.0, float(df["CPU %"].max())), format="%.1f%%"),
                "MEM %": st.column_config.NumberColumn("MEM %", format="%.1f%%"),
            })
    with r:
        with card("Top CPU Consumers", "📊"):
            plot(proc_columns(df.head(8), P["cpu"]), "p_bar")
            st.caption("Hover a column to see which process it is.")


PAGES = {
    "Overview": page_overview,
    "Battery": page_battery,
    "CPU & Thermal": page_cpu,
    "Memory & Storage": page_memory,
    "Network": page_network,
    "Diagnostics": page_diag,
    "Processes": page_procs,
}

NAV_ICONS = {
    "Overview": "🏠", "Battery": "🔋", "CPU & Thermal": "🔥", "Memory & Storage": "💾",
    "Network": "📡", "Diagnostics": "🩺", "Processes": "⚙️",
}

# =============================================================================
#  App & Polished CSS
# =============================================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    padding-top: 1.8rem;
    padding-bottom: 2.5rem;
    max-width: 1440px;
}
footer { visibility: hidden; }

/* Hero Header Banner */
.hero-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    border-radius: 18px;
    background: linear-gradient(135deg, color-mix(in srgb, #60a5fa 10%, transparent), color-mix(in srgb, #a78bfa 8%, transparent) 60%, color-mix(in srgb, #f472b6 6%, transparent));
    border: 1px solid color-mix(in srgb, currentColor 11%, transparent);
    box-shadow: 0 8px 30px -12px rgba(0, 0, 0, 0.12);
}
.hero-title {
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.15;
    background: linear-gradient(90deg, #60a5fa, #a78bfa 55%, #f472b6);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}
.hero-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
}
.meta-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    background: color-mix(in srgb, currentColor 7%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 10%, transparent);
    opacity: 0.88;
}

/* Live Status Pill */
.live-pill {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    padding: 7px 15px;
    border-radius: 99px;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    background: color-mix(in srgb, var(--c) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 30%, transparent);
    color: var(--c);
}
.live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--c);
    display: inline-block;
    animation: pulse-ring 1.8s infinite;
}
@keyframes pulse-ring {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--c) 65%, transparent); }
    100% { box-shadow: 0 0 0 8px transparent; }
}

/* Card Containers */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid color-mix(in srgb, currentColor 10%, transparent) !important;
    background: color-mix(in srgb, currentColor 2.2%, transparent) !important;
    box-shadow: 0 4px 20px -6px rgba(0, 0, 0, 0.06);
    transition: border-color 0.2s ease, transform 0.2s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: color-mix(in srgb, currentColor 18%, transparent) !important;
}
.card-hdr {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.94rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid color-mix(in srgb, currentColor 8%, transparent);
}
.card-ico {
    font-size: 1.05rem;
}

/* KPI Metric Cards */
[data-testid="stMetric"] {
    background: linear-gradient(145deg, color-mix(in srgb, currentColor 4.5%, transparent), color-mix(in srgb, currentColor 2%, transparent));
    border: 1px solid color-mix(in srgb, currentColor 10%, transparent);
    padding: 14px 16px;
    border-radius: 14px;
    transition: transform 0.15s ease, border-color 0.15s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, currentColor 22%, transparent);
}
[data-testid="stMetricLabel"] {
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.68;
}
[data-testid="stMetricValue"] {
    font-weight: 800 !important;
    letter-spacing: -0.025em;
    font-size: 1.55rem !important;
}
[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem !important;
    opacity: 0.75;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 4px 13px;
    border-radius: 99px;
    font-weight: 700;
    font-size: 0.8rem;
    letter-spacing: 0.02em;
    background: color-mix(in srgb, var(--c) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 32%, transparent);
    color: var(--c);
}

/* Custom Health Progress Bars */
.comp-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 4px 0 6px 0;
}
.comp-row {
    display: flex;
    flex-direction: column;
    gap: 5px;
}
.comp-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
    font-size: 0.86rem;
}
.comp-name {
    font-weight: 700;
}
.comp-detail {
    flex: 1;
    opacity: 0.65;
    font-size: 0.8rem;
    text-align: right;
    font-family: 'JetBrains Mono', monospace;
}
.comp-score {
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    min-width: 48px;
    text-align: right;
}
.comp-score small {
    opacity: 0.55;
    font-weight: 500;
}
.comp-track {
    height: 7px;
    width: 100%;
    border-radius: 99px;
    background: color-mix(in srgb, currentColor 10%, transparent);
    overflow: hidden;
}
.comp-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.4s ease;
}

/* Findings Alert Items */
.finding-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.finding-item {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 9px 13px;
    border-radius: 11px;
    background: color-mix(in srgb, var(--c) 10%, transparent);
    border-left: 3.5px solid var(--c);
    font-size: 0.86rem;
    font-weight: 500;
}
.finding-ico {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--c) 22%, transparent);
    color: var(--c);
    font-weight: 800;
    font-size: 0.75rem;
    flex-shrink: 0;
}

/* Key-Value & Security Lists */
.kv-list, .sec-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.kv-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 10px;
    border-radius: 9px;
    background: color-mix(in srgb, currentColor 3.5%, transparent);
    font-size: 0.85rem;
}
.kv-k {
    opacity: 0.68;
    font-weight: 600;
}
.kv-v {
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
}
.sec-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-radius: 10px;
    background: color-mix(in srgb, currentColor 3.5%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 7%, transparent);
}
.sec-title {
    font-weight: 700;
    font-size: 0.86rem;
}
.sec-note {
    font-size: 0.76rem;
    opacity: 0.62;
    font-family: 'JetBrains Mono', monospace;
}

/* Empty State Box */
.empty-stat {
    text-align: center;
    padding: 42px 12px 32px 12px;
}
.empty-val {
    font-size: 2.1rem;
    font-weight: 800;
    letter-spacing: -0.02em;
}
.empty-lbl {
    font-size: 0.8rem;
    opacity: 0.6;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 4px;
}

/* Status Footer Bar */
.status-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 18px;
    padding: 10px 16px;
    border-radius: 12px;
    background: color-mix(in srgb, currentColor 3.5%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 8%, transparent);
    font-size: 0.78rem;
    opacity: 0.75;
    font-family: 'JetBrains Mono', monospace;
}

/* ---------- Sidebar brand ---------- */
[data-testid="stSidebar"] {
    border-right: 1px solid color-mix(in srgb, currentColor 9%, transparent);
}
.brand {
    display: flex;
    align-items: center;
    gap: 13px;
    padding: 6px 2px 14px 2px;
}
.brand-logo {
    width: 46px;
    height: 46px;
    flex-shrink: 0;
    filter: drop-shadow(0 6px 14px rgba(124, 92, 255, 0.35));
}
.brand-logo .ecg {
    stroke-dasharray: 60;
    stroke-dashoffset: 60;
    animation: ecg-draw 2.8s ease-in-out infinite;
}
@keyframes ecg-draw {
    0%   { stroke-dashoffset: 60; opacity: 0.2; }
    45%  { stroke-dashoffset: 0;  opacity: 1; }
    80%  { stroke-dashoffset: 0;  opacity: 1; }
    100% { stroke-dashoffset: -60; opacity: 0.2; }
}
.brand-text { display: flex; flex-direction: column; line-height: 1.1; }
.brand-name {
    font-size: 1.22rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    background: linear-gradient(90deg, #60a5fa, #a78bfa 55%, #f472b6);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}
.brand-name b { font-weight: 500; opacity: 0.9; }
.brand-tag {
    margin-top: 5px;
    font-size: 0.72rem;
    font-weight: 500;
    opacity: 0.6;
    letter-spacing: 0.01em;
}
.brand-rule {
    height: 1px;
    margin: 0 0 6px 0;
    background: linear-gradient(90deg, color-mix(in srgb, #a78bfa 55%, transparent), transparent);
}

/* ---------- Navigation bar ---------- */
.st-key-navbar {
    padding: 5px;
    margin: 0 0 18px 0;
    border-radius: 18px;
    background: color-mix(in srgb, currentColor 4%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 10%, transparent);
    box-shadow: 0 6px 24px -10px rgba(0, 0, 0, 0.18), inset 0 1px 0 color-mix(in srgb, currentColor 6%, transparent);
    backdrop-filter: blur(8px);
    overflow-x: auto;
    scrollbar-width: none;
}
.st-key-navbar::-webkit-scrollbar { display: none; }
.st-key-navbar [data-testid="stButtonGroup"],
.st-key-navbar [role="radiogroup"] {
    display: flex;
    flex-wrap: nowrap;
    gap: 4px;
    width: 100%;
}
.st-key-navbar [data-testid="stButtonGroup"] button {
    flex: 1 1 0;
    min-width: max-content;
    height: 42px;
    padding: 0 16px;
    border: 0 !important;
    border-radius: 13px !important;
    background: transparent !important;
    box-shadow: none !important;
    color: inherit;
    opacity: 0.72;
    font-size: 0.86rem;
    font-weight: 600;
    letter-spacing: -0.005em;
    white-space: nowrap;
    transition: background 0.18s ease, opacity 0.18s ease, transform 0.18s ease;
}
.st-key-navbar [data-testid="stButtonGroup"] button p { font-weight: 600; font-size: 0.86rem; }
.st-key-navbar [data-testid="stButtonGroup"] button:hover {
    opacity: 1;
    background: color-mix(in srgb, currentColor 8%, transparent) !important;
}
.st-key-navbar [data-testid="stButtonGroup"] button[kind="segmented_controlActive"],
.st-key-navbar [data-testid="stButtonGroup"] [data-testid="stBaseButton-segmented_controlActive"] {
    opacity: 1;
    color: #ffffff !important;
    background: linear-gradient(135deg, #3b82f6, #7c5cff 60%, #d946ef) !important;
    box-shadow: 0 6px 16px -6px rgba(124, 92, 255, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
}
.st-key-navbar [data-testid="stButtonGroup"] button[kind="segmented_controlActive"] p,
.st-key-navbar [data-testid="stButtonGroup"] [data-testid="stBaseButton-segmented_controlActive"] p {
    color: #ffffff !important;
}
.st-key-navbar button:focus-visible { outline: 2px solid #a78bfa; outline-offset: 2px; }

/* Radio fallback for older Streamlit */
.st-key-navbar [role="radiogroup"] label {
    flex: 1 1 0;
    justify-content: center;
    padding: 9px 16px;
    border-radius: 13px;
    opacity: 0.72;
    cursor: pointer;
    transition: background 0.18s ease, opacity 0.18s ease;
}
.st-key-navbar [role="radiogroup"] label > div:first-child { display: none; }
.st-key-navbar [role="radiogroup"] label:hover { opacity: 1; background: color-mix(in srgb, currentColor 8%, transparent); }
.st-key-navbar [role="radiogroup"] label:has(input:checked) {
    opacity: 1;
    color: #fff;
    background: linear-gradient(135deg, #3b82f6, #7c5cff 60%, #d946ef);
    box-shadow: 0 6px 16px -6px rgba(124, 92, 255, 0.65);
}
.st-key-navbar [role="radiogroup"] label:has(input:checked) p { color: #fff; }

@media (max-width: 760px) {
    .st-key-navbar [data-testid="stButtonGroup"] button { height: 38px; padding: 0 12px; }
}
@media (prefers-reduced-motion: reduce) {
    .brand-logo .ecg { animation: none; stroke-dashoffset: 0; opacity: 1; }
}
</style>
"""


def brand_html():
    logo = (
        "<svg class='brand-logo' viewBox='0 0 48 48' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>"
        "<defs>"
        "<linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0' stop-color='#3b82f6'/><stop offset='0.6' stop-color='#7c5cff'/><stop offset='1' stop-color='#d946ef'/>"
        "</linearGradient>"
        "</defs>"
        "<rect x='1' y='1' width='46' height='46' rx='14' fill='url(#bg)'/>"
        "<rect x='1' y='1' width='46' height='46' rx='14' fill='none' stroke='white' stroke-opacity='0.28'/>"
        "<rect x='14.5' y='8' width='19' height='32' rx='4.5' fill='none' stroke='white' stroke-width='2.2'/>"
        "<line x1='21' y1='11.5' x2='27' y2='11.5' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-opacity='0.85'/>"
        "<polyline class='ecg' points='16.5,26 21,26 23,19.5 26,32.5 28.2,26 31.5,26' fill='none' stroke='white' "
        "stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/>"
        "</svg>"
    )
    return (
        "<div class='brand'>" + logo +
        "<div class='brand-text'>"
        "<span class='brand-name'>Android <b>Telemetry</b></span>"
        "<span class='brand-tag'>Live ADB monitor &amp; health diagnostics</span>"
        "</div></div><div class='brand-rule'></div>"
    )


@st.cache_resource
def get_monitor():
    m = Monitor()
    m.start()
    return m


def main():
    global P
    st.set_page_config(page_title="Android System Monitor", page_icon="📱", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    P = make_pal()

    # ---- Sidebar
    sb = st.sidebar
    sb.markdown(brand_html(), unsafe_allow_html=True)

    devices = list_devices()
    if devices is None:
        st.error("`adb` binary was not found. Install Android Platform-Tools and ensure `adb` is on your system PATH.")
        st.stop()

    ready = [d for d in devices if d[2] == "device"]
    if not ready:
        st.markdown(
            "<div class='hero-banner'><div><div class='hero-title'>Android System Monitor</div>"
            "<div class='hero-meta'><span class='meta-chip'>Waiting for ADB handshake…</span></div></div></div>",
            unsafe_allow_html=True,
        )
        with card("Connection Setup Guide", "🔌"):
            st.warning("No authorised Android device detected over ADB.")
            st.markdown(
                "1. Open **Settings → Developer options** on your handset and enable **USB debugging**.\n"
                "2. Connect the phone via USB cable (or pair wirelessly via `adb connect <ip>:<port>`).\n"
                "3. Check **Always allow from this computer** on the phone's RSA key prompt.\n"
                "4. Click **Rerun** or refresh this page."
            )
            if devices:
                st.caption("Interfaces detected by ADB daemon: " + ", ".join(f"`{d[0]}` ({d[2]})" for d in devices))
        st.stop()

    labels = {d[0]: d[1] for d in ready}
    serial = sb.selectbox("Target Device", list(labels), format_func=lambda k: labels[k])

    sb.divider()
    sb.markdown("##### ⚙️ Sampling Controls")
    interval = sb.slider("Polling Interval (s)", 0.5, 5.0, 1.0, 0.5)
    window = sb.select_slider(
        "Chart Horizon",
        options=[30, 60, 180, 300, 600],
        value=60,
        format_func=lambda x: f"{x // 60} min" if x >= 60 else f"{x} sec",
    )
    paused = sb.toggle("Pause Live Stream", value=False)

    mon = get_monitor()
    mon.configure(serial, interval)

    if sb.button("🔄 Force Deep Diagnostics", use_container_width=True):
        mon.force_diag = True

    # ---- Hero Header
    snap0 = mon.snapshot()
    props0 = snap0["diag"].get("props", {})
    name = f"{(props0.get('ro.product.manufacturer') or '').title()} {props0.get('ro.product.model', '')}".strip() or labels[serial]

    chips = [f"<span class='meta-chip'>SN: {serial}</span>"]
    if props0.get("ro.build.version.release"):
        chips.append(f"<span class='meta-chip'>Android {props0.get('ro.build.version.release')} (API {props0.get('ro.build.version.sdk', '?')})</span>")
    if props0.get("ro.board.platform"):
        chips.append(f"<span class='meta-chip'>{props0.get('ro.board.platform')}</span>")

    if paused:
        pill_col, pill_txt = P["warn"], "Stream Paused"
    elif snap0["connected"]:
        pill_col, pill_txt = P["ok"], f"Live · {interval:.1f}s"
    else:
        pill_col, pill_txt = P["bad"], "Reconnecting"

    st.markdown(
        f"<div class='hero-banner'>"
        f"  <div>"
        f"    <div class='hero-title'>{name}</div>"
        f"    <div class='hero-meta'>{''.join(chips)}</div>"
        f"  </div>"
        f"  <div class='live-pill' style='--c:{pill_col}'><span class='live-dot'></span>{pill_txt}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ---- Navigation Bar
    nav_opts = list(PAGES)

    def nav_label(k):
        return f"{NAV_ICONS.get(k, '•')}  {k}"

    try:
        nav_box = st.container(key="navbar")
    except TypeError:  # very old Streamlit without container keys
        nav_box = st.container()
    with nav_box:
        if hasattr(st, "segmented_control"):
            page = st.segmented_control("View", nav_opts, default=nav_opts[0], format_func=nav_label,
                                        label_visibility="collapsed", key="nav")
        else:
            page = st.radio("View", nav_opts, horizontal=True, format_func=nav_label,
                            label_visibility="collapsed", key="nav")
    page = page or nav_opts[0]

    # ---- Live Fragment Body
    def dashboard():
        global P
        P = make_pal()
        snap = mon.snapshot()
        hist = snap["history"]
        if not hist:
            (st.warning if snap["error"] else st.info)(snap["error"] or "Initialising ADB telemetry stream…")
            return
        if snap["error"]:
            st.error(snap["error"])
        n = max(2, int(window / interval))
        df = to_df(hist[-n:])
        s = hist[-1]
        a = assess(to_df(hist), s, snap["diag"])
        c = SimpleNamespace(s=s, df=df, diag=snap["diag"], procs=snap["procs"], assess=a)
        PAGES[page](c)

        st.markdown(
            f"<div class='status-footer'>"
            f"  <span>⚡ Last packet: {datetime.fromtimestamp(s['t']).strftime('%H:%M:%S')}</span>"
            f"  <span>📦 Buffer: {len(hist)} / {MAX_HISTORY} samples · Window: {len(df)} pts</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    run_every = None if paused else interval
    st.fragment(run_every=run_every)(dashboard)()

    # ---- Sidebar Exports
    hist = mon.snapshot()["history"]
    if hist:
        sb.divider()
        sb.markdown("##### 📥 Export Telemetry")
        sb.download_button(
            "⬇ Time-Series CSV",
            to_df(hist).to_csv(index=False),
            "android_telemetry.csv",
            "text/csv",
            use_container_width=True,
        )
        snap = mon.snapshot()
        report = {
            "generated": datetime.now().isoformat(),
            "assessment": assess(to_df(hist), hist[-1], snap["diag"]),
            "diagnostics": snap["diag"],
            "latest": {k: v for k, v in hist[-1].items() if k != "zones"},
        }
        sb.download_button(
            "⬇ Health Report JSON",
            json.dumps(report, default=str, indent=2),
            "android_health_report.json",
            "application/json",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
