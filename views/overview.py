"""Overview page."""

import streamlit as st

from ui.charts import area, gauge, plot
from ui.components import card, render_comp_bars, render_findings
from ui.theme import P, fmt_dur, fmt_mb, level_color, v_or


def page_overview(c):
    s, a = c.s, c.assess
    left, right = st.columns([1.05, 1.95], gap="medium")
    with left:
        with card("Overall Device Health", "🛡️"):
            plot(gauge(a["score"], level_color(a["level"]), suffix="", h=205), "g_overall")
            st.markdown(
                f"<div style='text-align:center;margin-top:-6px;margin-bottom:8px'>"
                f"<span class='badge' style='--c:{level_color(a['level'])}'>{a['label']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.caption("Weighted composite score across battery wear, thermals, memory pressure, storage, CPU load, and OS security.")
    with right:
        with card("Subsystem Breakdown", "📊"):
            render_comp_bars(a["components"])
        with card("Active Diagnostic Findings", "🔍"):
            render_findings(a["findings"])

    cols = st.columns(6)
    b = s["battery"]
    cols[0].metric("CPU Load", f"{s['cpu']:.0f}%", f"{len(s['cores'])} cores" if s["cores"] else None, delta_color="off")
    cols[1].metric("RAM Usage", f"{s['ram']:.0f}%", f"{fmt_mb(s['ram_used'])} / {fmt_mb(s['ram_total'])}", delta_color="off")
    cols[2].metric("Battery", f"{b['level']}%", b["status"], delta_color="off")
    cols[3].metric("Thermals", v_or(b["temp"], "{:.1f} °C"), f"CPU {s['cpu_temp']:.0f} °C" if s["cpu_temp"] else "Battery sensor", delta_color="off")
    cols[4].metric("Free Storage", f"{s['st_free']:.1f} GB", f"{100 - s['storage']:.0f}% available", delta_color="off")
    cols[5].metric("System Uptime", fmt_dur(s["uptime"]), f"Load {s['load'][0]:.2f}" if s["load"] else None, delta_color="off")

    l, r = st.columns(2)
    with l:
        with card("CPU & Memory Utilisation", "⚡"):
            plot(area(c.df, [("CPU", "cpu", P["cpu"]), ("Memory", "ram", P["ram"])], ymax=100, unit="%"), "o_cm")
    with r:
        with card("Network Throughput", "🌐"):
            plot(area(c.df, [("Download", "rx", P["rx"]), ("Upload", "tx", P["tx"])], unit=" KB/s"), "o_net")
