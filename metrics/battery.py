"""Battery metric: level, health, temperature, current, voltage, cycles."""

from core.utils import kv, to_int


BAT_HEALTH = {1: "Unknown", 2: "Good", 3: "Overheat", 4: "Dead", 5: "Over voltage", 6: "Failure", 7: "Cold"}


BAT_STATUS = {1: "Unknown", 2: "Charging", 3: "Discharging", 4: "Not charging", 5: "Full"}


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
