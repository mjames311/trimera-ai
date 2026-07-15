import streamlit as st

st.set_page_config(
    page_title="PA Extractor",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Prior Authorization Extractor")

st.write(
    """
This tool will extract everything needed from a payer denial or fax.

### Planned outputs

- Patient Name
- DOB
- Insurance
- Member ID
- Group Number
- Diagnosis
- CPT Codes Requested
- Dates of Service
- Medical Necessity Requirements
- Missing Documentation
- Appeal Deadline
- Auto-generated checklist
"""
)

uploaded_file = st.file_uploader(
    "Upload PA Request / Denial PDF",
    type=["pdf"]
)

if uploaded_file:
    st.success("PDF uploaded successfully.")

    st.info(
        "Next version will automatically extract all relevant information."
    )