"""Page CSS and the sidebar brand logo."""


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    padding-top: 1.8rem;
    padding-bottom: 2.5rem;
    max-width: 1440px;
}
footer { visibility: hidden; }

/* Hero Header Banner */
.hero-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    border-radius: 18px;
    background: linear-gradient(135deg, color-mix(in srgb, #60a5fa 10%, transparent), color-mix(in srgb, #a78bfa 8%, transparent) 60%, color-mix(in srgb, #f472b6 6%, transparent));
    border: 1px solid color-mix(in srgb, currentColor 11%, transparent);
    box-shadow: 0 8px 30px -12px rgba(0, 0, 0, 0.12);
}
.hero-title {
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.15;
    background: linear-gradient(90deg, #60a5fa, #a78bfa 55%, #f472b6);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}
.hero-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
}
.meta-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    background: color-mix(in srgb, currentColor 7%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 10%, transparent);
    opacity: 0.88;
}

/* Live Status Pill */
.live-pill {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    padding: 7px 15px;
    border-radius: 99px;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    background: color-mix(in srgb, var(--c) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 30%, transparent);
    color: var(--c);
}
.live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--c);
    display: inline-block;
    animation: pulse-ring 1.8s infinite;
}
@keyframes pulse-ring {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--c) 65%, transparent); }
    100% { box-shadow: 0 0 0 8px transparent; }
}

/* Card Containers */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid color-mix(in srgb, currentColor 10%, transparent) !important;
    background: color-mix(in srgb, currentColor 2.2%, transparent) !important;
    box-shadow: 0 4px 20px -6px rgba(0, 0, 0, 0.06);
    transition: border-color 0.2s ease, transform 0.2s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: color-mix(in srgb, currentColor 18%, transparent) !important;
}
.card-hdr {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.94rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid color-mix(in srgb, currentColor 8%, transparent);
}
.card-ico {
    font-size: 1.05rem;
}

/* KPI Metric Cards */
[data-testid="stMetric"] {
    background: linear-gradient(145deg, color-mix(in srgb, currentColor 4.5%, transparent), color-mix(in srgb, currentColor 2%, transparent));
    border: 1px solid color-mix(in srgb, currentColor 10%, transparent);
    padding: 14px 16px;
    border-radius: 14px;
    transition: transform 0.15s ease, border-color 0.15s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, currentColor 22%, transparent);
}
[data-testid="stMetricLabel"] {
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.68;
}
[data-testid="stMetricValue"] {
    font-weight: 800 !important;
    letter-spacing: -0.025em;
    font-size: 1.55rem !important;
}
[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem !important;
    opacity: 0.75;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 4px 13px;
    border-radius: 99px;
    font-weight: 700;
    font-size: 0.8rem;
    letter-spacing: 0.02em;
    background: color-mix(in srgb, var(--c) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 32%, transparent);
    color: var(--c);
}

/* Custom Health Progress Bars */
.comp-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 4px 0 6px 0;
}
.comp-row {
    display: flex;
    flex-direction: column;
    gap: 5px;
}
.comp-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
    font-size: 0.86rem;
}
.comp-name {
    font-weight: 700;
}
.comp-detail {
    flex: 1;
    opacity: 0.65;
    font-size: 0.8rem;
    text-align: right;
    font-family: 'JetBrains Mono', monospace;
}
.comp-score {
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    min-width: 48px;
    text-align: right;
}
.comp-score small {
    opacity: 0.55;
    font-weight: 500;
}
.comp-track {
    height: 7px;
    width: 100%;
    border-radius: 99px;
    background: color-mix(in srgb, currentColor 10%, transparent);
    overflow: hidden;
}
.comp-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.4s ease;
}

/* Findings Alert Items */
.finding-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.finding-item {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 9px 13px;
    border-radius: 11px;
    background: color-mix(in srgb, var(--c) 10%, transparent);
    border-left: 3.5px solid var(--c);
    font-size: 0.86rem;
    font-weight: 500;
}
.finding-ico {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--c) 22%, transparent);
    color: var(--c);
    font-weight: 800;
    font-size: 0.75rem;
    flex-shrink: 0;
}

/* Key-Value & Security Lists */
.kv-list, .sec-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.kv-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 10px;
    border-radius: 9px;
    background: color-mix(in srgb, currentColor 3.5%, transparent);
    font-size: 0.85rem;
}
.kv-k {
    opacity: 0.68;
    font-weight: 600;
}
.kv-v {
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
}
.sec-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-radius: 10px;
    background: color-mix(in srgb, currentColor 3.5%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 7%, transparent);
}
.sec-title {
    font-weight: 700;
    font-size: 0.86rem;
}
.sec-note {
    font-size: 0.76rem;
    opacity: 0.62;
    font-family: 'JetBrains Mono', monospace;
}

/* Empty State Box */
.empty-stat {
    text-align: center;
    padding: 42px 12px 32px 12px;
}
.empty-val {
    font-size: 2.1rem;
    font-weight: 800;
    letter-spacing: -0.02em;
}
.empty-lbl {
    font-size: 0.8rem;
    opacity: 0.6;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 4px;
}

/* Status Footer Bar */
.status-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 18px;
    padding: 10px 16px;
    border-radius: 12px;
    background: color-mix(in srgb, currentColor 3.5%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 8%, transparent);
    font-size: 0.78rem;
    opacity: 0.75;
    font-family: 'JetBrains Mono', monospace;
}

/* ---------- Sidebar brand ---------- */
[data-testid="stSidebar"] {
    border-right: 1px solid color-mix(in srgb, currentColor 9%, transparent);
}
.brand {
    display: flex;
    align-items: center;
    gap: 13px;
    padding: 6px 2px 14px 2px;
}
.brand-logo {
    width: 46px;
    height: 46px;
    flex-shrink: 0;
    filter: drop-shadow(0 6px 14px rgba(124, 92, 255, 0.35));
}
.brand-logo .ecg {
    stroke-dasharray: 60;
    stroke-dashoffset: 60;
    animation: ecg-draw 2.8s ease-in-out infinite;
}
@keyframes ecg-draw {
    0%   { stroke-dashoffset: 60; opacity: 0.2; }
    45%  { stroke-dashoffset: 0;  opacity: 1; }
    80%  { stroke-dashoffset: 0;  opacity: 1; }
    100% { stroke-dashoffset: -60; opacity: 0.2; }
}
.brand-text { display: flex; flex-direction: column; line-height: 1.1; }
.brand-name {
    font-size: 1.22rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    background: linear-gradient(90deg, #60a5fa, #a78bfa 55%, #f472b6);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}
.brand-name b { font-weight: 500; opacity: 0.9; }
.brand-tag {
    margin-top: 5px;
    font-size: 0.72rem;
    font-weight: 500;
    opacity: 0.6;
    letter-spacing: 0.01em;
}
.brand-rule {
    height: 1px;
    margin: 0 0 6px 0;
    background: linear-gradient(90deg, color-mix(in srgb, #a78bfa 55%, transparent), transparent);
}

/* ---------- Navigation bar ---------- */
.st-key-navbar {
    padding: 5px;
    margin: 0 0 18px 0;
    border-radius: 18px;
    background: color-mix(in srgb, currentColor 4%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 10%, transparent);
    box-shadow: 0 6px 24px -10px rgba(0, 0, 0, 0.18), inset 0 1px 0 color-mix(in srgb, currentColor 6%, transparent);
    backdrop-filter: blur(8px);
    overflow-x: auto;
    scrollbar-width: none;
}
.st-key-navbar::-webkit-scrollbar { display: none; }
.st-key-navbar [data-testid="stButtonGroup"],
.st-key-navbar [role="radiogroup"] {
    display: flex;
    flex-wrap: nowrap;
    gap: 4px;
    width: 100%;
}
.st-key-navbar [data-testid="stButtonGroup"] button {
    flex: 1 1 0;
    min-width: max-content;
    height: 42px;
    padding: 0 16px;
    border: 0 !important;
    border-radius: 13px !important;
    background: transparent !important;
    box-shadow: none !important;
    color: inherit;
    opacity: 0.72;
    font-size: 0.86rem;
    font-weight: 600;
    letter-spacing: -0.005em;
    white-space: nowrap;
    transition: background 0.18s ease, opacity 0.18s ease, transform 0.18s ease;
}
.st-key-navbar [data-testid="stButtonGroup"] button p { font-weight: 600; font-size: 0.86rem; }
.st-key-navbar [data-testid="stButtonGroup"] button:hover {
    opacity: 1;
    background: color-mix(in srgb, currentColor 8%, transparent) !important;
}
.st-key-navbar [data-testid="stButtonGroup"] button[kind="segmented_controlActive"],
.st-key-navbar [data-testid="stButtonGroup"] [data-testid="stBaseButton-segmented_controlActive"] {
    opacity: 1;
    color: #ffffff !important;
    background: linear-gradient(135deg, #3b82f6, #7c5cff 60%, #d946ef) !important;
    box-shadow: 0 6px 16px -6px rgba(124, 92, 255, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
}
.st-key-navbar [data-testid="stButtonGroup"] button[kind="segmented_controlActive"] p,
.st-key-navbar [data-testid="stButtonGroup"] [data-testid="stBaseButton-segmented_controlActive"] p {
    color: #ffffff !important;
}
.st-key-navbar button:focus-visible { outline: 2px solid #a78bfa; outline-offset: 2px; }

/* Radio fallback for older Streamlit */
.st-key-navbar [role="radiogroup"] label {
    flex: 1 1 0;
    justify-content: center;
    padding: 9px 16px;
    border-radius: 13px;
    opacity: 0.72;
    cursor: pointer;
    transition: background 0.18s ease, opacity 0.18s ease;
}
.st-key-navbar [role="radiogroup"] label > div:first-child { display: none; }
.st-key-navbar [role="radiogroup"] label:hover { opacity: 1; background: color-mix(in srgb, currentColor 8%, transparent); }
.st-key-navbar [role="radiogroup"] label:has(input:checked) {
    opacity: 1;
    color: #fff;
    background: linear-gradient(135deg, #3b82f6, #7c5cff 60%, #d946ef);
    box-shadow: 0 6px 16px -6px rgba(124, 92, 255, 0.65);
}
.st-key-navbar [role="radiogroup"] label:has(input:checked) p { color: #fff; }

@media (max-width: 760px) {
    .st-key-navbar [data-testid="stButtonGroup"] button { height: 38px; padding: 0 12px; }
}
@media (prefers-reduced-motion: reduce) {
    .brand-logo .ecg { animation: none; stroke-dashoffset: 0; opacity: 1; }
}
</style>
"""


def brand_html():
    logo = (
        "<svg class='brand-logo' viewBox='0 0 48 48' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>"
        "<defs>"
        "<linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0' stop-color='#3b82f6'/><stop offset='0.6' stop-color='#7c5cff'/><stop offset='1' stop-color='#d946ef'/>"
        "</linearGradient>"
        "</defs>"
        "<rect x='1' y='1' width='46' height='46' rx='14' fill='url(#bg)'/>"
        "<rect x='1' y='1' width='46' height='46' rx='14' fill='none' stroke='white' stroke-opacity='0.28'/>"
        "<rect x='14.5' y='8' width='19' height='32' rx='4.5' fill='none' stroke='white' stroke-width='2.2'/>"
        "<line x1='21' y1='11.5' x2='27' y2='11.5' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-opacity='0.85'/>"
        "<polyline class='ecg' points='16.5,26 21,26 23,19.5 26,32.5 28.2,26 31.5,26' fill='none' stroke='white' "
        "stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/>"
        "</svg>"
    )
    return (
        "<div class='brand'>" + logo +
        "<div class='brand-text'>"
        "<span class='brand-name'>Android <b>Telemetry</b></span>"
        "<span class='brand-tag'>Live ADB monitor &amp; health diagnostics</span>"
        "</div></div><div class='brand-rule'></div>"
    )
