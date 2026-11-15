"""CPU & Thermal page."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.charts import area, bars, base_layout, plot
from ui.components import card
from ui.theme import P, stretch


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
