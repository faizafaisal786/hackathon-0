"""
AI Employee — Web Dashboard
==============================
Visual dashboard for hackathon demos and daily monitoring.

Usage:
    pip install streamlit
    streamlit run dashboard_web.py
"""

import json
from pathlib import Path
from datetime import datetime
from collections import Counter

try:
    import streamlit as st
except ImportError:
    print("Install streamlit: pip install streamlit")
    print("Then run: streamlit run dashboard_web.py")
    raise SystemExit(1)


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

BASE = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"
LOGS_DIR = VAULT / "Logs"

PIPELINE_FOLDERS = ["Inbox", "Needs_Action", "Plans", "Pending_Approval", "Approved", "Rejected", "Done"]


# ──────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────

def count_files(folder_name: str) -> int:
    folder = VAULT / folder_name
    if not folder.exists():
        return 0
    return len([f for f in folder.iterdir() if f.is_file()])


def list_files(folder_name: str) -> list[str]:
    folder = VAULT / folder_name
    if not folder.exists():
        return []
    return sorted([f.name for f in folder.iterdir() if f.is_file()])


def load_today_log() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.json"
    if not log_file.exists():
        return []
    try:
        raw = json.loads(log_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "events" in raw:
            return raw["events"]
        if isinstance(raw, list):
            return raw
    except (json.JSONDecodeError, KeyError):
        pass
    return []


def load_all_logs() -> list[dict]:
    if not LOGS_DIR.exists():
        return []
    events = []
    for log_file in sorted(LOGS_DIR.glob("*.json")):
        try:
            raw = json.loads(log_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "events" in raw:
                events.extend(raw["events"])
            elif isinstance(raw, list):
                events.extend(raw)
        except (json.JSONDecodeError, KeyError):
            pass
    return events


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

st.set_page_config(page_title="AI Employee", page_icon="🤖", layout="wide")

st.title("AI Employee Dashboard")
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")

# ── Top metrics ──
col1, col2, col3, col4, col5, col6 = st.columns(6)

done_count = count_files("Done")
pending_count = count_files("Pending_Approval")
inbox_count = count_files("Inbox")
needs_count = count_files("Needs_Action")
approved_count = count_files("Approved")
plans_count = count_files("Plans")

events = load_today_log()
errors_today = sum(1 for e in events if e.get("severity") == "ERROR" or e.get("result") == "FAILED")

col1.metric("Done", done_count)
col2.metric("Pending Approval", pending_count, delta=None if pending_count == 0 else f"{pending_count} waiting")
col3.metric("Needs Action", needs_count)
col4.metric("Inbox", inbox_count)
col5.metric("Plans", plans_count)
col6.metric("Errors Today", errors_today, delta=None if errors_today == 0 else f"{errors_today} issues")

st.divider()

# ── Pipeline visualization ──
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Pipeline Status")

    pipeline_data = {}
    for folder in PIPELINE_FOLDERS:
        pipeline_data[folder] = count_files(folder)

    st.bar_chart(pipeline_data, horizontal=True)

with col_right:
    st.subheader("Channel Distribution")

    all_events = load_all_logs()
    channel_counts = Counter()
    for ev in all_events:
        ch = ""
        if isinstance(ev, dict):
            ch = (ev.get("metadata") or {}).get("channel", "") or ev.get("channel", "")
        if ch:
            channel_counts[ch] += 1

    if channel_counts:
        st.bar_chart(dict(channel_counts))
    else:
        st.info("No channel data yet")

st.divider()

# ── Recent activity ──
st.subheader(f"Today's Activity ({len(events)} events)")

if events:
    # Show last 15 events
    display_events = events[-15:]
    for ev in reversed(display_events):
        ts = ev.get("timestamp", "")[:19]
        action = ev.get("action", ev.get("task", ""))
        severity = ev.get("severity", "INFO")
        result = ev.get("result", ev.get("status", ""))
        details = ev.get("details", "")[:80]

        if severity == "ERROR" or result == "FAILED":
            icon = "🔴"
        elif severity == "WARNING":
            icon = "🟡"
        else:
            icon = "🟢"

        st.text(f"{icon} {ts}  {action:30s}  {result:10s}  {details}")
else:
    st.info("No events logged today. Run the pipeline to generate activity.")

st.divider()

# ── Pending approval details ──
if pending_count > 0:
    st.subheader(f"Awaiting Approval ({pending_count})")
    pending_files = list_files("Pending_Approval")
    for f in pending_files:
        st.warning(f"  {f}")

# ── Footer ──
st.divider()
st.caption(f"AI Employee v2.0 | Vault: {VAULT} | Auto-refresh: reload page")
