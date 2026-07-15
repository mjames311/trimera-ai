import os
import re
from typing import List

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

st.set_page_config(
    page_title="TRD Prior Authorization Assistant",
    page_icon="📄",
    layout="wide",
)

st.title("📄 TRD Prior Authorization Assistant")
st.caption(
    "Extract useful prior authorization information from a completed provider note."
)

st.divider()

treatment = st.radio(
    "Treatment",
    ["TMS", "Spravato"],
    horizontal=True,
)

method = st.radio(
    "Provider Note",
    ["Upload PDF", "Paste Text"],
    horizontal=True,
)

note_text = ""

def extract_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    pages = []

    for i, page in enumerate(reader.pages, start=1):
        pages.append(
            f"[Page {i}]\n{page.extract_text() or ''}"
        )

    return "\n\n".join(pages)

if method == "Upload PDF":

    uploaded = st.file_uploader(
        "Upload Provider Note",
        type=["pdf"],
    )

    if uploaded:

        try:
            note_text = extract_pdf(uploaded)
            st.success("PDF text extracted successfully.")

        except Exception as exc:
            st.error(exc)

else:

    note_text = st.text_area(
        "Paste Provider Note",
        height=350,
    )

st.divider()

extract = st.button(
    "Extract PA Information",
    type="primary",
    use_container_width=True,
)

PROMPT = """
You are assisting a psychiatric prior authorization coordinator.

Your job is NOT to determine eligibility.

Your job is NOT to determine medical necessity.

Do NOT recommend approval or denial.

Do NOT state whether criteria are met.

Do NOT invent information.

Only organize documented information.

Diagnosis should ALWAYS be displayed as:

F33.2

Return the information using these exact headings.

Diagnosis

Previous Medication Trials

Depressive History

Therapy History

Treatment Safety

Pertinent Medical History

Other Useful Information

----------------------------

Previous Medication Trials

Include:

Medication

Medication Class

Dose (if documented)

Duration (if documented)

Outcome

If side effects are documented,
list the side effects.

Otherwise use

No response documented

----------------------------

Depressive History

Extract:

Approximate depression onset

Current depressive episode

Timeline information

Depressive symptoms

PHQ-9 or other depression scales

----------------------------

Therapy History

Extract:

Therapy type

Dates

Duration

Frequency

----------------------------

Treatment Safety

IF TMS

Extract only documented information regarding:

Seizure history

Ferromagnetic metal

Cochlear implants

Deep brain stimulators

Head trauma

Psychosis

Mania

IF SPRAVATO

Extract only documented information regarding:

Blood pressure

Hypertension

Aneurysm

AVM

Intracranial hemorrhage

Psychosis

Pregnancy

Substance use

----------------------------

Pertinent Medical History

Extract important medical diagnoses that could
be relevant to prior authorization.

Examples include:

Hypertension

Diabetes

Stroke

CAD

Migraine

Sleep apnea

Thyroid disease

Neurologic disease

----------------------------

Other Useful Information

Extract any additional information that may
assist a prior authorization coordinator.

Keep the response concise.

Use bullet points whenever appropriate.
"""

if extract:

    if not note_text.strip():

        st.error("Please upload or paste a provider note.")

        st.stop()

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )

    with st.spinner("Extracting prior authorization information..."):

        try:

            response = client.responses.create(

                model=MODEL,

                instructions=PROMPT,

                input=f"""
Treatment Requested

{treatment}

Provider Note

{note_text}
""",
            )

            result = response.output_text

        except Exception as exc:

            st.error(exc)

            st.stop()
            ###############################################################
# Display Results
###############################################################

    st.divider()

    st.success("Extraction Complete")

    st.download_button(
        "Download Extracted Information",
        result,
        file_name="TRD_PA_Extraction.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.divider()

    sections = [
        "Diagnosis",
        "Previous Medication Trials",
        "Depressive History",
        "Therapy History",
        "Treatment Safety",
        "Pertinent Medical History",
        "Other Useful Information",
    ]

    remaining = result

    for i, heading in enumerate(sections):

        pattern = rf"{heading}\s*"

        match = re.search(pattern, remaining, flags=re.IGNORECASE)

        if not match:
            continue

        start = match.start()

        next_start = len(remaining)

        for other in sections[i + 1:]:

            m2 = re.search(
                rf"{other}\s*",
                remaining[start + 1 :],
                flags=re.IGNORECASE,
            )

            if m2:
                next_start = start + 1 + m2.start()
                break

        block = remaining[start:next_start].strip()

        with st.expander(heading, expanded=(heading == "Diagnosis")):
            st.markdown(block)

    st.divider()

    st.caption(
        "This tool extracts documented information only. "
        "It does not determine payer eligibility or medical necessity."
    )