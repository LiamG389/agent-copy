"""
Calendar page -- a plain, human-readable view of what's on the
calendar right now. No agent involved here on purpose: this page
exists for a person to glance at, not to be talked to.
"""

import streamlit as st
import pandas as pd

from agent_wk4 import MOCK_CALENDAR

if not MOCK_CALENDAR:
    st.info("No events on the calendar yet.")
else:
    events = pd.DataFrame(MOCK_CALENDAR)
    events["start"] = pd.to_datetime(events["start"])
    events["end"] = pd.to_datetime(events["end"])
    events = events.sort_values("start")

    for day, day_events in events.groupby(events["start"].dt.date):
        st.markdown(f"**{day.strftime('%A, %B %d')}**")
        for _, event in day_events.iterrows():
            with st.container(border=True):
                cols = st.columns([3, 2])
                cols[0].write(f"**{event['title']}**")
                cols[1].write(
                    f":material/schedule: {event['start'].strftime('%I:%M %p').lstrip('0')}"
                    f" \u2013 {event['end'].strftime('%I:%M %p').lstrip('0')}"
                )

    with st.expander("All events (table view)"):
        st.dataframe(
            events[["title", "start", "end"]],
            column_config={
                "title": st.column_config.TextColumn("Title"),
                "start": st.column_config.DatetimeColumn("Start", format="MMM D, h:mm a"),
                "end": st.column_config.DatetimeColumn("End", format="MMM D, h:mm a"),
            },
            hide_index=True,
        )