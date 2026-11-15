"""Background threads that poll the phone and keep the history."""

from collections import deque
import subprocess
import threading
import time

from core.adb import Adb
from core.commands import DIAG_CMD, FAST_CMD
from core.config import MAX_HISTORY
from core.utils import sections
from metrics.battery import parse_battery
from metrics.cpu import CPU_ZONE_HINTS, parse_cpu, parse_freq, parse_thermal
from metrics.diagnostics import parse_diag
from metrics.memory import parse_ram, parse_storage
from metrics.network import parse_net
from metrics.processes import parse_top


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
