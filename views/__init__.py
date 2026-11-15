"""Dashboard pages. Add a new page here and it appears in the navigation bar."""
from views.battery import page_battery
from views.cpu import page_cpu
from views.diagnostics import page_diag
from views.memory import page_memory
from views.network import page_network
from views.overview import page_overview
from views.processes import page_procs

PAGES = {
    "Overview": page_overview,
    "Battery": page_battery,
    "CPU & Thermal": page_cpu,
    "Memory & Storage": page_memory,
    "Network": page_network,
    "Diagnostics": page_diag,
    "Processes": page_procs,
}

NAV_ICONS = {
    "Overview": "🏠", "Battery": "🔋", "CPU & Thermal": "🔥", "Memory & Storage": "💾",
    "Network": "📡", "Diagnostics": "🩺", "Processes": "⚙️",
}
