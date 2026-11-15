"""Plotly chart builders: gauge, donut, area, bars and the process columns."""

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from ui.theme import P, rgba, stretch


def base_layout(fig, h):
    fig.update_layout(
        height=h, margin=dict(l=14, r=18, t=24, b=14),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=P["mut"], size=13),
        hovermode="x unified", showlegend=False,
        hoverlabel=dict(bgcolor=P["hover_bg"], bordercolor=P["grid"], font=dict(family="Inter, sans-serif", size=12, color=P["txt"])),
    )
    axis = dict(automargin=True, tickfont=dict(size=12, color=P["mut"]), showline=True, linecolor=P["grid"],
                ticks="outside", tickcolor=P["grid"], ticklen=4)
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def gauge(value, color, rng=(0, 100), suffix="%", steps=None, h=200, decimals=0):
    """Half-dial gauge with room around it so the big value and scale numbers are never clipped."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        domain={"x": [0.04, 0.96], "y": [0.14, 0.94]},
        number={"suffix": suffix, "font": {"size": 30, "color": P["txt"], "family": "Inter, sans-serif"},
                "valueformat": f".{decimals}f"},
        gauge={
            "axis": {"range": list(rng), "nticks": 5, "tickcolor": P["mut"],
                     "tickfont": {"color": P["mut"], "size": 12}},
            "bar": {"color": color, "thickness": 0.36},
            "bgcolor": P["track"], "borderwidth": 0,
            "steps": steps or [],
        },
    ))
    fig.update_layout(
        height=h, margin=dict(l=16, r=16, t=16, b=22),
        paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", color=P["txt"]),
    )
    return fig


def donut(labels, values, colors, center, h=260):
    """Compact donut: percentage in the middle with a small label, ring slightly thicker for clarity."""
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.68, sort=False, direction="clockwise", rotation=0,
        marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0)", width=0)),
        textinfo="none", hovertemplate="<b>%{label}</b>: %{value:.1f}<extra></extra>",
        domain=dict(x=[0.16, 0.84], y=[0.04, 0.96]),
    ))
    fig.update_layout(
        height=h, margin=dict(l=6, r=6, t=6, b=6), paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
        annotations=[dict(
            text=f"<b>{center}</b><br><span style='font-size:12px'>{labels[0]}</span>",
            x=0.5, y=0.5, showarrow=False, align="center",
            font=dict(family="Inter, sans-serif", size=22, color=P["txt"]),
        )],
    )
    return fig


def area(df, series, h=250, ymin=0, ymax=None, unit="", fill=True):
    fig = go.Figure()
    x = [datetime.fromtimestamp(t) for t in df["t"]]
    for name, col, color in series:
        fig.add_trace(go.Scatter(
            x=x, y=df[col], name=name, mode="lines",
            line=dict(color=color, width=2.4, shape="spline", smoothing=0.55),
            fill="tozeroy" if fill else None, fillcolor=rgba(color, 0.12),
            hovertemplate=f"<b>{name}</b>: %{{y:.1f}}{unit}<extra></extra>",
        ))
    base_layout(fig, h)
    fig.update_xaxes(showgrid=False, color=P["mut"], tickformat="%H:%M:%S", nticks=6)
    fig.update_yaxes(gridcolor=P["grid"], zeroline=False, range=[ymin, ymax] if ymax is not None else None,
                     color=P["mut"], ticksuffix=unit if len(unit) <= 2 else "")
    if len(series) > 1:
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.14, x=0, font=dict(size=11)))
    return fig


def bars(x, y, color, h=240, unit="", ymax=None, text=True):
    fig = go.Figure(go.Bar(
        x=x, y=y, marker=dict(color=color, cornerradius=5),
        text=[f"{v:.0f}{unit}" for v in y] if text else None, textposition="outside",
        textfont=dict(color=P["mut"], size=12), cliponaxis=False,
        hovertemplate="<b>%{x}</b>: %{y:.1f}" + unit + "<extra></extra>"
    ))
    base_layout(fig, h)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(showgrid=False, color=P["mut"])
    fig.update_yaxes(gridcolor=P["grid"], zeroline=False, color=P["mut"], range=[0, ymax] if ymax else None)
    return fig


def hbars(labels, values, color, h=330, unit=""):
    """Horizontal bars: long names stay readable on the y-axis, biggest value on top."""
    labels = [str(l) if len(str(l)) <= 24 else str(l)[:23] + "…" for l in labels]
    values = [float(v) for v in values]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h", marker=dict(color=color, cornerradius=5),
        text=[f"{v:.1f}{unit}" for v in values], textposition="outside", cliponaxis=False,
        textfont=dict(color=P["mut"], size=12),
        hovertemplate="<b>%{y}</b>: %{x:.1f}" + unit + "<extra></extra>",
    ))
    base_layout(fig, h)
    fig.update_layout(hovermode="closest", margin=dict(l=10, r=48, t=10, b=10), bargap=0.35)
    fig.update_xaxes(gridcolor=P["grid"], zeroline=False, showline=False, ticks="",
                     range=[0, max(max(values, default=1), 1) * 1.2])
    fig.update_yaxes(autorange="reversed", showgrid=False, showline=False, ticks="")
    return fig


def proc_columns(df, color, h=340):
    """Clean column chart: no text on the bars or x-axis; hover shows the full process name."""
    fig = go.Figure(go.Bar(
        x=list(range(1, len(df) + 1)), y=df["CPU %"], marker=dict(color=color, cornerradius=5),
        customdata=list(zip(df["Process"], df["PID"])),
        hovertemplate="<b>%{customdata[0]}</b><br>PID %{customdata[1]} · CPU %{y:.1f}%<extra></extra>",
    ))
    base_layout(fig, h)
    fig.update_layout(hovermode="closest", bargap=0.3, margin=dict(l=14, r=18, t=12, b=10))
    fig.update_xaxes(showticklabels=False, showgrid=False, showline=False, ticks="")
    fig.update_yaxes(gridcolor=P["grid"], zeroline=False, ticksuffix="%", rangemode="tozero")
    return fig


def plot(fig, key):
    stretch(st.plotly_chart, fig, key=key, theme=None, config={"displayModeBar": False})
