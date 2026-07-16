import streamlit as st
from openai import OpenAI
from pypdf import PdfReader
import os

st.title("ERA Analyzer")
st.caption("Upload an ERA and receive an AI billing analysis.")

uploaded_file = st.file_uploader(
    "Upload ERA PDF",
    type=["pdf"]
)

if uploaded_file:

    reader = PdfReader(uploaded_file)

    era_text = ""

    for page in reader.pages:
        text = page.extract_text()
        if text:
            era_text += text + "\n"

    st.success("ERA successfully read.")

    if st.button("Analyze ERA"):

        client = OpenAI()

        prompt = f"""
You are an expert outpatient behavioral health medical biller.

Analyze this ERA.

Produce:

1. Executive Summary

2. Every denied claim in a table:
- Patient Name
- DOS
- CPT
- ICD10 (if present)
- Insurance
- CARC code
- RARC code
- Plain-English explanation
- Suggested next action
- Appeal recommended? (Yes/No)

3. Trends
- Most common denial reason
- Total denied dollars
- Total adjusted dollars
- Total unpaid dollars

4. Billing opportunities

5. High priority items first.

ERA:

{era_text}
"""

        with st.spinner("Analyzing ERA..."):

            response = client.responses.create(
                model="gpt-5.4-mini",
                input=prompt
            )

        st.markdown(response.output_text)
