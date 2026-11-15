"""Android System Monitor - app entry point.

Run with:  streamlit run app.py"""

from datetime import datetime
from types import SimpleNamespace
import json

import streamlit as st

from core.adb import list_devices
from core.assessment import assess
from core.config import MAX_HISTORY
from core.monitor import Monitor
from ui.components import card, to_df
from ui.styles import CSS, brand_html
from ui.theme import P, refresh_palette
from views import NAV_ICONS, PAGES


@st.cache_resource
def get_monitor():
    m = Monitor()
    m.start()
    return m


def main():
    st.set_page_config(page_title="Android System Monitor", page_icon="📱", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    refresh_palette()

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
        refresh_palette()
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
