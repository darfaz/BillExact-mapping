"""
pages/categorize_test.py
------------------------

This Streamlit page allows users to experiment with the UTBMS
catergorisation engine. Attorneys can input free‑form descriptions of
their work (for example, an email subject or document title) and view
the suggested UTBMS task and activity codes along with the confidence
score. The page demonstrates the behaviour of the categorisation
algorithm and can be used to fine‑tune the keyword mappings stored in
the database.
"""

import streamlit as st
from categorize import categorize_text


def main() -> None:
    st.set_page_config(page_title="Categorisation Test", page_icon="🧪", layout="centered")
    st.title("Categorisation Test")
    st.write(
        "Enter a description of your activity to see which UTBMS codes the system selects."
    )
    text = st.text_area("Activity description", height=150, placeholder="e.g. Drafting motion for summary judgment")
    if st.button("Categorise"):
        if not text.strip():
            st.warning("Please enter a description before categorising.")
        else:
            result = categorize_text(text)
            st.subheader("Result")
            if result["task_code"] is None:
                st.info(
                    f"No mapping found (confidence {result['confidence']:.2f}). You may want to update the keyword table."
                )
            else:
                st.json(result)


if __name__ == "__main__":
    main()