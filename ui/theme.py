"""Colours, number formatting and Streamlit version helpers."""

import streamlit as st


try:
    _ST_VER = tuple(int(x) for x in st.__version__.split(".")[:2])
except Exception:  # noqa: BLE001
    _ST_VER = (1, 40)


_NEW, _OLD = {"width": "stretch"}, {"use_container_width": True}
STRETCH, STRETCH_ALT = (_NEW, _OLD) if _ST_VER >= (1, 50) else (_OLD, _NEW)


def stretch(fn, *a, **k):
    """Call a Streamlit element full-width across old/new API versions."""
    try:
        return fn(*a, **STRETCH, **k)
    except TypeError:
        return fn(*a, **STRETCH_ALT, **k)


def theme_is_dark():
    try:
        t = {"dark": True, "light": False}.get(st.context.theme.type)
        if t is not None:
            return t
    except Exception:  # noqa: BLE001
        pass
    try:
        return {"dark": True, "light": False}.get(st.get_option("theme.base"))
    except Exception:  # noqa: BLE001
        return None


def make_pal():
    dark = theme_is_dark()
    if dark is None or dark:
        p = dict(
            cpu="#60a5fa", ram="#a78bfa", bat="#34d399", tmp="#fb923c", sto="#f472b6",
            rx="#22d3ee", tx="#facc15", ok="#34d399", warn="#fbbf24", bad="#f87171",
            txt="#f8fafc", mut="#cbd5e1", grid="rgba(148,163,184,0.16)", track="rgba(148,163,184,0.14)",
            hover_bg="rgba(15,23,42,0.92)"
        )
    else:
        p = dict(
            cpu="#2563eb", ram="#7c3aed", bat="#059669", tmp="#ea580c", sto="#db2777",
            rx="#0891b2", tx="#d97706", ok="#059669", warn="#d97706", bad="#e11d48",
            txt="#0f172a", mut="#334155", grid="rgba(100,116,139,0.20)", track="rgba(100,116,139,0.14)",
            hover_bg="rgba(255,255,255,0.95)"
        )
    if dark is None:  # theme unknown: use mid-tones that stay readable on both backgrounds
        p.update(txt="#94a3b8", mut="#8b9ab0")
    return p


P = make_pal()


def refresh_palette():
    """Re-read the Streamlit theme and update the shared palette in place."""
    P.clear()
    P.update(make_pal())


def rgba(hex_color, a):
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def fmt_mb(m):
    return f"{m / 1024:.1f} GB" if m >= 1024 else f"{m:.0f} MB"


def fmt_rate(kb):
    return f"{kb / 1024:.2f} MB/s" if kb >= 1024 else f"{kb:.0f} KB/s"


def fmt_bytes(b):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or unit == "TB":
            return f"{b:.1f} {unit}" if unit != "B" else f"{b:.0f} B"
        b /= 1024


def fmt_dur(sec):
    if sec is None:
        return "–"
    sec = int(sec)
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    return (f"{d}d " if d else "") + f"{h}h {m}m"


def level_color(level):
    return P[level]


def v_or(v, fmt="{}", dash="–"):
    return dash if v is None else fmt.format(v)
