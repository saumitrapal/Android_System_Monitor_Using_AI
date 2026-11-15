"""Processes page."""

import pandas as pd
import streamlit as st

from ui.charts import plot, proc_columns
from ui.components import card
from ui.theme import P, stretch


def page_procs(c):
    if not c.procs:
        st.info("Sampling process table (`top`)…")
        return
    df = pd.DataFrame(c.procs)
    l, r = st.columns([3, 2])
    with l:
        with card("Active Processes (Top 12 by CPU)", "⚙️"):
            stretch(st.dataframe, df, hide_index=True, column_config={
                "PID": st.column_config.NumberColumn("PID", format="%d"),
                "Process": st.column_config.TextColumn("Package / Binary"),
                "CPU %": st.column_config.ProgressColumn("CPU %", min_value=0, max_value=max(100.0, float(df["CPU %"].max())), format="%.1f%%"),
                "MEM %": st.column_config.NumberColumn("MEM %", format="%.1f%%"),
            })
    with r:
        with card("Top CPU Consumers", "📊"):
            plot(proc_columns(df.head(8), P["cpu"]), "p_bar")
            st.caption("Hover a column to see which process it is.")
