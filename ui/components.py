"""Reusable page pieces: cards, badges, score bars and findings lists."""

import pandas as pd
import streamlit as st

from ui.theme import level_color


def card(title=None, icon=None):
    box = st.container(border=True)
    if title:
        prefix = f"<span class='card-ico'>{icon}</span>" if icon else ""
        box.markdown(f"<div class='card-hdr'>{prefix}<span>{title}</span></div>", unsafe_allow_html=True)
    return box


def badge(text, level):
    st.markdown(f"<span class='badge' style='--c:{level_color(level)}'>{text}</span>", unsafe_allow_html=True)


def render_comp_bars(components):
    html = ["<div class='comp-list'>"]
    for comp in components:
        sc = comp["score"]
        lvl = "ok" if sc >= 75 else "warn" if sc >= 50 else "bad"
        col = level_color(lvl)
        html.append(
            f"<div class='comp-row'>"
            f"  <div class='comp-top'>"
            f"    <span class='comp-name'>{comp['name']}</span>"
            f"    <span class='comp-detail'>{comp['detail']}</span>"
            f"    <span class='comp-score' style='color:{col}'>{sc:.0f}<small>/100</small></span>"
            f"  </div>"
            f"  <div class='comp-track'><div class='comp-fill' style='width:{sc:.1f}%;background:{col}'></div></div>"
            f"</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_findings(findings):
    icons = {"ok": "✓", "warn": "!", "bad": "✕"}
    html = ["<div class='finding-list'>"]
    for lvl, msg in findings:
        col = level_color(lvl)
        html.append(
            f"<div class='finding-item' style='--c:{col}'>"
            f"  <span class='finding-ico'>{icons[lvl]}</span>"
            f"  <span class='finding-msg'>{msg}</span>"
            f"</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def to_df(hist):
    keep = [{k: v for k, v in s.items() if not isinstance(v, (list, dict))} for s in hist]
    return pd.DataFrame(keep)
