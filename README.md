# Android System Monitor

A live dashboard for an Android phone, built with Streamlit and ADB. It shows real-time CPU, memory, storage, battery, network and temperature readings, plus a health score and a security check, all without installing anything on the phone.

## Features

- **Overview:** overall health score, subsystem scores, findings and key numbers at a glance
- **Battery:** charge level, capacity health (when the phone reports it), temperature, current, voltage, cycle count and time-to-full or time-to-empty
- **CPU & Thermal:** total and per-core load, core clock speeds, thermal sensors and temperature history
- **Memory & Storage:** RAM, swap/zRAM and `/data` storage usage, with a memory timeline
- **Network:** live download and upload speed, totals since boot and Wi-Fi signal quality
- **Diagnostics:** hardware and OS details, security checks (verified boot, encryption, SELinux, root), package counts, app crashes and ANRs
- **Processes:** the busiest processes by CPU, with the process name shown on hover
- **Export:** download the readings as CSV and a health report as JSON
- Works in Light and Dark themes, with adjustable polling speed and chart time window

## Requirements

- Python 3.9 or newer
- [Android Platform-Tools](https://developer.android.com/tools/releases/platform-tools) (`adb`) installed and on your PATH
- An Android phone with **USB debugging** turned on
- Python packages listed in `requirements.txt` (Streamlit 1.39 or newer is needed for the custom navigation bar styling)

## Setup

1. Install the Python packages:

   ```
   pip install -r requirements.txt
   ```

2. On the phone, go to **Settings → Developer options** and turn on **USB debugging**. If you don't see Developer options, tap **Build number** seven times in **Settings → About phone**.

3. Connect the phone with a USB cable and accept the "Allow USB debugging?" prompt. Tick **Always allow from this computer**.

4. Check that the phone is detected:

   ```
   adb devices
   ```

   Your phone should be listed as `device`, not `unauthorized`.

## Run

```
streamlit run app.py
```

The dashboard opens in your browser, usually at http://localhost:8501.

## Using the dashboard

- Pick your phone in **Target Device** in the sidebar if more than one is connected.
- **Polling Interval** sets how often the phone is read (0.5 to 5 seconds).
- **Chart Horizon** sets how much history the charts show.
- **Pause Live Stream** freezes the display without losing the data that was collected.
- **Force Deep Diagnostics** refreshes the hardware and security scan right away. It also refreshes by itself every 45 seconds.
- Change the theme from the Streamlit menu (top-right ⋮ → Settings → Theme).

## Wireless connection (optional)

On Android 11 or newer you can connect over Wi-Fi:

```
adb pair <ip>:<pairing-port>
adb connect <ip>:<port>
```

Use the address and pairing code shown in **Developer options → Wireless debugging**.

## Troubleshooting

| Problem | What to try |
| --- | --- |
| "`adb` binary was not found" | Install Platform-Tools and add the folder to your PATH, then restart the terminal |
| No device detected | Use a data-capable USB cable, unlock the phone and accept the debugging prompt |
| Device shows as `unauthorized` | Unplug and reconnect, then accept the prompt on the phone. If it doesn't appear, run `adb kill-server` and try again |
| "Device timed out" | Wake the phone and check the cable or Wi-Fi link |
| Some values show "–" or "not exposed" | Some phones don't let ADB read certain readings (for example battery capacity or thermal sensors) without root. This is normal |
| Navigation bar looks plain | Upgrade Streamlit: `pip install -U streamlit` |

## Notes

- The app only reads information from the phone. It does not change anything on it.
- Readings come from standard Android commands (`dumpsys`, `/proc`, `/sys`), so which values are available depends on the phone's make and Android version.
- The health score is an estimate based on the readings the phone provides, not a manufacturer diagnosis.

## Project structure

Each part of the phone has its own file, so you can change one metric without touching the rest.

```
android-monitor/
├── app.py                  Entry point: sidebar, header, navigation, live refresh
├── requirements.txt
├── README.md
│
├── core/                   Talking to the phone and scoring it
│   ├── adb.py              Run adb commands, list devices
│   ├── commands.py         The shell commands sent to the phone
│   ├── monitor.py          Background polling threads and history
│   ├── assessment.py       Overall health score and findings
│   ├── utils.py            Small shared helpers
│   └── config.py           Settings (history size)
│
├── metrics/                One file per metric: turns raw phone output into numbers
│   ├── battery.py          Level, health, temperature, current, voltage, cycles
│   ├── cpu.py              CPU load, per-core load, clock speeds, thermal zones
│   ├── memory.py           RAM, swap/zRAM, storage
│   ├── network.py          Download and upload bytes
│   ├── processes.py        Busiest processes
│   └── diagnostics.py      Device info, security checks, packages, Wi-Fi, crashes
│
├── views/                  One file per dashboard page
│   ├── __init__.py         Page list and navigation icons
│   ├── overview.py
│   ├── battery.py
│   ├── cpu.py
│   ├── memory.py
│   ├── network.py
│   ├── diagnostics.py
│   └── processes.py
│
└── ui/                     Look and feel
    ├── theme.py            Colours and number formatting
    ├── charts.py           Gauge, donut, line, bar and column charts
    ├── components.py       Cards, badges, score bars, findings list
    └── styles.py           CSS and the sidebar logo
```

### Where to change things

| I want to change… | Edit this file |
| --- | --- |
| How a chart looks (size, fonts, axis) | `ui/charts.py` |
| Colours | `ui/theme.py` |
| Navigation bar or logo styling | `ui/styles.py` |
| What a page shows | the matching file in `views/` |
| How a reading is calculated | the matching file in `metrics/` |
| Health score rules | `core/assessment.py` |
| Which commands run on the phone | `core/commands.py` |

### Adding a new page

1. Create `views/mypage.py` with a function `page_mypage(c)`.
2. Add it to `PAGES` (and an icon to `NAV_ICONS`) in `views/__init__.py`.
