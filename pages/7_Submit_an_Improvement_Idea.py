"""Staff improvement-idea intake for Trimera AI."""

import streamlit as st

from auth import current_user_email, logout_user, require_auth
from idea_submissions import submit_idea
from theme import apply_trimera_theme, page_header, render_topbar, sidebar_label, sidebar_reminder


st.set_page_config(
    page_title="Submit an Improvement Idea | Trimera AI",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_trimera_theme()
require_auth("Submit an Improvement Idea", "Internal Trimera Health improvement workspace")
render_topbar()

with st.sidebar:
    sidebar_label("Quick actions")
    st.caption(current_user_email())
    if st.button("Sign out"):
        logout_user()
    sidebar_reminder("Ideas welcome", "Show us the outcome you want—not a finished technical solution.")

page_header(
    "idea",
    "Submit an Improvement Idea",
    "Help us identify workflows where AI or automation could make Trimera work better.",
)

st.markdown(
    """
Describe the process you would like to improve and the result you hope to achieve. Clearly include:

- the **current workflow** and where time or effort is being spent;
- the **desired end goal**; and
- what you think **AI or automation could assist with**.

Screenshots, documents, sample forms, and other examples are highly suggested because they help us understand the real workflow. You may attach any relevant file type. Please avoid including *unnecessary* patient information.
"""
)

attachments = st.file_uploader(
    "Supporting files (optional)",
    accept_multiple_files=True,
    help="Attach screenshots, images, PDFs, documents, spreadsheets, or other useful examples.",
)
idea = st.text_area(
    "Describe your improvement idea",
    height=220,
    placeholder=(
        "Current workflow: Briefly describe how the work is completed today.\n\n"
        "Desired end goal: Describe what a successful improvement would accomplish.\n\n"
        "How AI could help: Explain what you would like AI or automation to assist with."
    ),
)

if st.button("Submit idea", type="primary", use_container_width=True):
    if not idea.strip():
        st.warning("Please describe the current workflow, desired end goal, and how AI could assist.")
    else:
        try:
            with st.spinner("Submitting your idea securely..."):
                reference = submit_idea(current_user_email(), idea.strip(), attachments or [])
            st.success(f"Thank you—your idea was submitted successfully. Reference: {reference}")
        except Exception:
            st.error(
                "Your idea could not be submitted right now. Please keep this page open and try again, "
                "or contact the Trimera AI administrator."
            )
