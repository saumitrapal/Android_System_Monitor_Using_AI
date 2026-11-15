"""Battery page."""

import streamlit as st

from ui.charts import area, gauge, plot
from ui.components import card
from ui.theme import P, rgba, v_or


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
