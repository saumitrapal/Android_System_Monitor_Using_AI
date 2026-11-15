"""Process metric: busiest processes from `top`."""


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
