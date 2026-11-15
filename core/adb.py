"""ADB access: run commands on the phone and list connected devices."""

import subprocess


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
