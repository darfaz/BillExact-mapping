"""
pages/invoice.py
-----------------

This page allows attorneys to generate LEDES 1998B invoices from
captured time entries. Users specify the client ID, matter ID and
billing period (start and end dates). When the form is submitted, the
server generates a pipe‑delimited LEDES file using the
``export_ledes1998b`` function and provides a download link. Rate and
total values in the LEDES file are currently zero; attorneys can edit
them in the file or provide rate information in the database using a
future enhancement.
"""

import datetime as dt
import streamlit as st
from export_ledes import export_ledes1998b


def main() -> None:
    st.set_page_config(page_title="LEDES Invoice Export", page_icon="📄", layout="centered")
    st.title("Export LEDES 1998B Invoice")
    st.markdown("Generate a LEDES‑compliant invoice from your captured time entries.")

    with st.form("invoice_form"):
        client_id = st.text_input("Client ID", help="The client identifier used in your billing system.")
        matter_id = st.text_input("Matter ID", help="The matter identifier used in your billing system.")
        today = dt.date.today()
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", value=today - dt.timedelta(days=7))
        with col2:
            end_date = st.date_input("End date", value=today)
        timekeeper_id = st.text_input("Timekeeper ID (optional)")
        timekeeper_name = st.text_input("Timekeeper Name (optional)")
        submitted = st.form_submit_button("Generate LEDES File")

    if submitted:
        if not client_id or not matter_id:
            st.error("Client ID and Matter ID are required.")
        elif start_date > end_date:
            st.error("Start date must be before or on the end date.")
        else:
            file_path = export_ledes1998b(
                client_id=client_id,
                matter_id=matter_id,
                start_date=start_date,
                end_date=end_date,
                timekeeper_id=timekeeper_id or None,
                timekeeper_name=timekeeper_name or None,
            )
            with open(file_path, "rb") as f:
                data = f.read()
            st.success("LEDES file generated successfully!")
            st.download_button(
                label="Download LEDES File",
                data=data,
                file_name=file_path.split("/")[-1],
                mime="text/plain",
            )


if __name__ == "__main__":
    main()
# NOTE: Pilot upgrade expects Validate & Export buttons wired to export_ledes.export_ledes1998b
