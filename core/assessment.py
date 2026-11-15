"""Overall phone health score and the findings list."""

from datetime import date
from datetime import datetime

from core.utils import interp


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
