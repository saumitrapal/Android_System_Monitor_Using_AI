"""Network page."""

import streamlit as st

from core.utils import interp
from ui.charts import area, gauge, plot
from ui.components import card
from ui.theme import P, fmt_bytes, fmt_rate


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
