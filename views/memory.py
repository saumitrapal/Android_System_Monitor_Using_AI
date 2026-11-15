"""Memory & Storage page."""

import streamlit as st

from ui.charts import area, donut, plot
from ui.components import card
from ui.theme import P, fmt_mb


def page_memory(c):
    s = c.s
    l, m, r = st.columns(3)
    with l:
        with card("System RAM", "🧠"):
            plot(donut(["Used", "Available"], [s["ram_used"], s["ram_total"] - s["ram_used"]],
                       [P["ram"], P["track"]], f"{s['ram']:.0f}%"), "m_ram")
            st.caption(f"**{fmt_mb(s['ram_used'])}** active · **{fmt_mb(s['ram_total'] - s['ram_used'])}** available of **{fmt_mb(s['ram_total'])}**")
    with m:
        with card("Swap / zRAM", "🔄"):
            if s["swap_total"]:
                pct = s["swap_used"] / s["swap_total"] * 100
                plot(donut(["Used", "Free"], [s["swap_used"], s["swap_total"] - s["swap_used"]],
                           [P["tmp"], P["track"]], f"{pct:.0f}%"), "m_swap")
                st.caption(f"**{fmt_mb(s['swap_used'])}** compressed in zRAM of **{fmt_mb(s['swap_total'])}**")
            else:
                st.info("No swap / zRAM configured.")
    with r:
        with card("User Partition (/data)", "💾"):
            plot(donut(["Used", "Free"], [s["st_used"], s["st_free"]], [P["sto"], P["track"]], f"{s['storage']:.0f}%"), "m_sto")
            st.caption(f"**{s['st_used']:.1f} GB** used · **{s['st_free']:.1f} GB** free of **{s['st_total']:.1f} GB**")

    with card("Memory Allocation Timeline", "📉"):
        d = c.df.assign(ram_gb=c.df["ram_used"] / 1024, swap_gb=c.df["swap_used"] / 1024)
        plot(area(d, [("RAM Used", "ram_gb", P["ram"]), ("Swap Used", "swap_gb", P["tmp"])], unit=" GB", h=265), "m_hist")
