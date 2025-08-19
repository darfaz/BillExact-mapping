"""
pages/keywords.py
------------------

Administrative page for managing keyword mappings used by the
catergorisation engine. This Streamlit page displays all current
keyword entries from the database and provides a form for adding new
keywords with associated task and activity codes and a confidence
boost. In the future this page could be extended to support editing
and deleting mappings.
"""

import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from ingest import _initialise_db


DB_PATH = Path("data.db")


def load_keywords() -> pd.DataFrame:
    if not DB_PATH.exists():
        # Initialise the database if not present
        _initialise_db()
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT id, keyword, task_code, activity_code, confidence_boost, created_at FROM utbms_keywords ORDER BY keyword",
        conn,
    )
    conn.close()
    return df


def add_keyword(keyword: str, task_code: str, activity_code: str, boost: float) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO utbms_keywords (keyword, task_code, activity_code, confidence_boost) VALUES (?, ?, ?, ?)",
        (keyword.strip().lower(), task_code.strip().upper(), activity_code.strip().upper(), boost),
    )
    conn.commit()
    conn.close()


def main() -> None:
    st.set_page_config(page_title="Keyword Manager", page_icon="🔑", layout="centered")
    st.title("UTBMS Keyword Manager")
    st.markdown("Add or view keyword mappings for the categorisation engine.")

    with st.expander("Add New Keyword", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("Keyword", help="A word or phrase that appears in an activity description.")
            task_code = st.text_input("Task Code", help="UTBMS task code, e.g. L330").upper()
            activity_code = st.text_input("Activity Code", help="UTBMS activity code, e.g. A103").upper()
        with col2:
            boost = st.slider("Confidence Boost", min_value=0.0, max_value=1.0, value=0.8, step=0.05)
        if st.button("Add Keyword"):
            if not keyword or not task_code or not activity_code:
                st.error("Keyword, Task Code and Activity Code are required.")
            else:
                add_keyword(keyword, task_code, activity_code, boost)
                st.success(f"Added mapping for '{keyword}'.")

    st.subheader("Current Keywords")
    df = load_keywords()
    if df.empty:
        st.info("No keywords defined yet.")
    else:
        df_display = df.rename(columns={
            "keyword": "Keyword",
            "task_code": "Task Code",
            "activity_code": "Activity Code",
            "confidence_boost": "Boost",
            "created_at": "Created",
        })
        st.dataframe(df_display, use_container_width=True)


if __name__ == "__main__":
    main()