"""Diagnostics page."""

from datetime import datetime

import streamlit as st

from ui.components import card, render_findings
from ui.theme import P, v_or


def page_diag(c):
    d, props = c.diag, c.diag.get("props", {})
    if not d:
        st.info("Gathering deep hardware & security diagnostics…")
        return
    g = props.get
    l, r = st.columns(2)
    with l:
        with card("Hardware & OS Profile", "📱"):
            rows = [
                ("Model", f"{(g('ro.product.manufacturer') or '').title()} {g('ro.product.model', '')}".strip()),
                ("Codename", g("ro.product.device", "–")),
                ("Android Version", f"Android {g('ro.build.version.release', '–')} (API {g('ro.build.version.sdk', '–')})"),
                ("Security Patch", g("ro.build.version.security_patch", "–")),
                ("Build Type", f"{g('ro.build.type', '–')} · {g('ro.build.tags', '–')}"),
                ("SoC / Platform", f"{g('ro.board.platform') or g('ro.hardware', '–')} ({g('ro.product.cpu.abi', '–')})"),
                ("Display", " · ".join(x for x in (d["display"].get("size"),
                                                   f"{d['display']['density']} dpi" if d["display"].get("density") else None,
                                                   d["display"].get("state")) if x) or "–"),
                ("Carrier / TZ", f"{g('gsm.operator.alpha') or '–'} · {g('persist.sys.timezone', '–')}"),
            ]
            html = ["<div class='kv-list'>"]
            for k_lbl, val in rows:
                html.append(f"<div class='kv-row'><span class='kv-k'>{k_lbl}</span><span class='kv-v'>{val}</span></div>")
            html.append("</div>")
            st.markdown("".join(html), unsafe_allow_html=True)

    with r:
        with card("Security & Integrity Audit", "🔒"):
            boot = g("ro.boot.verifiedbootstate")
            enc = g("ro.crypto.state")
            checks = [
                ("Verified Boot (AVB)", boot == "green" if boot else None, boot or "unknown"),
                ("Bootloader Status", (g("ro.boot.flash.locked") == "1") if g("ro.boot.flash.locked") else None,
                 {"1": "locked", "0": "unlocked"}.get(g("ro.boot.flash.locked"), "unknown")),
                ("File-Based Encryption", (enc == "encrypted") if enc else None, enc or "unknown"),
                ("SELinux Mode", (d.get("selinux") == "Enforcing") if d.get("selinux") else None,
                 d.get("selinux") or "unknown"),
                ("Root Binaries (su)", not d.get("rooted"), "su binary found" if d.get("rooted") else "clean"),
                ("Build Debuggability", (g("ro.debuggable") == "0") if g("ro.debuggable") else None,
                 "ro.debuggable=0" if g("ro.debuggable") == "0" else f"ro.debuggable={g('ro.debuggable', '?')}"),
            ]
            html = ["<div class='sec-list'>"]
            for name, ok, note in checks:
                lvl = "ok" if ok else "warn" if ok is False else "mut"
                col = P[lvl] if lvl in P else P["mut"]
                pill = "PASS" if ok else "WARN" if ok is False else "N/A"
                html.append(
                    f"<div class='sec-row'>"
                    f"  <div><div class='sec-title'>{name}</div><div class='sec-note'>{note}</div></div>"
                    f"  <span class='badge' style='--c:{col}'>{pill}</span>"
                    f"</div>"
                )
            html.append("</div>")
            st.markdown("".join(html), unsafe_allow_html=True)

    l, r = st.columns(2)
    with l:
        with card("Package & Stability Telemetry", "📦"):
            a = d.get("apps", {})
            m = st.columns(3)
            m[0].metric("User Packages", v_or(a.get("user")))
            m[1].metric("System Packages", v_or(a.get("system")))
            m[2].metric("Disabled", v_or(a.get("disabled")))
            m = st.columns(2)
            m[0].metric("Recent App Crashes", v_or(d.get("crashes")), help="FATAL EXCEPTION entries in logcat crash buffer")
            m[1].metric("Recent ANRs", v_or(d.get("anrs")), help="am_anr events in logcat event buffer")
    with r:
        with card("Diagnostic Summary", "🩺"):
            render_findings(c.assess["findings"])
            st.caption(f"Last deep scan at **{datetime.fromtimestamp(d['time']).strftime('%H:%M:%S')}** · auto-refreshes every 45s")

    with st.expander("View Raw Telemetry Payload (JSON)"):
        st.json({"diagnostics": d, "assessment": c.assess}, expanded=False)
