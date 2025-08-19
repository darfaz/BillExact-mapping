"""
pages/index.py
----------------

This is the home page of the Passive Activity‑to‑LEDES Translator app. It
provides a live view of all captured activities that have been
ingested into the database. The page displays a table of recent time
entries, including the date, description, duration, mapped UTBMS
codes, and confidence scores.

Users can refresh the data on demand and filter by client or matter
using simple input fields. This page acts as a dashboard for
attorneys to verify that ActivityWatch is capturing their work
accurately and that the categorisation engine is assigning
appropriate UTBMS codes.
"""

import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from ingest import _initialise_db


DB_PATH = Path("data.db")


def load_entries(client_id: str = "", matter_id: str = "") -> pd.DataFrame:
    """Load time entries from the SQLite database.

    Parameters
    ----------
    client_id : str, optional
        If provided, filter entries by this client ID.
    matter_id : str, optional
        If provided, filter entries by this matter ID.

    Returns
    -------
    pandas.DataFrame
        A dataframe containing the time entries.
    """
    if not DB_PATH.exists():
        # Initialise database if it doesn't exist yet
        _initialise_db()
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT date, description, duration_hours, task_code, activity_code, confidence FROM time_entries"
    params = []
    where_clauses = []
    if client_id:
        where_clauses.append("client_id = ?")
        params.append(client_id)
    if matter_id:
        where_clauses.append("matter_id = ?")
        params.append(matter_id)
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY timestamp DESC LIMIT 100"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def main() -> None:
    st.set_page_config(page_title="Activity Feed", page_icon="🕒", layout="wide")
    st.title("Activity Feed")
    st.markdown(
        "This page shows your recent computer activities that have been captured by ActivityWatch and mapped to UTBMS codes.")

    with st.sidebar:
        st.header("Filters")
        client_id = st.text_input("Client ID filter (optional)")
        matter_id = st.text_input("Matter ID filter (optional)")
        if st.button("Refresh"):
            st.experimental_rerun()

    df = load_entries(client_id, matter_id)
    if df.empty:
        st.info("No entries found. Make sure the ingestion task has run and ActivityWatch is active on your computer.")
    else:
        # Rename columns for display
        df_display = df.rename(columns={
            "date": "Date",
            "description": "Description",
            "duration_hours": "Hours",
            "task_code": "Task Code",
            "activity_code": "Activity Code",
            "confidence": "Confidence",
        })
        st.dataframe(df_display, use_container_width=True)


if __name__ == "__main__":
    main()