"""
Calendar Agent — Streamlit app entry point.

Run with:  streamlit run dashboard.py

Two pages:
- Chat     (app_pages/chat.py)          -- talk to the agent
- Calendar (app_pages/calendar_view.py) -- plain, human-readable view
  of what's actually on the calendar right now, no agent involved
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(page_title="Calendar Agent", page_icon=":material/calendar_month:", layout="wide")

page = st.navigation([
    st.Page("app_pages/chat.py", title="Chat", icon=":material/chat:"),
    st.Page("app_pages/calendar_view.py", title="Calendar", icon=":material/calendar_month:"),
])

st.title(f"{page.icon} {page.title}")
page.run()