import json
import os
import re
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader


st.set_page_config(
    page_title="TRD Prior Authorization Assistant",
    page_icon="📄",
    layout="wide",
)

load_dotenv()


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)

    if value:
        return value

    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return default


MODEL = get_setting("OPENAI_MODEL", "gpt-5.5")
OPENAI_API_KEY = get_setting("OPENAI_API_KEY")
TEST_PASSWORD = get_setting("TRIMERA_QA_PASSWORD")


def password_gate() -> None:
    if not TEST_PASSWORD:
        st.warning(
            "Set TRIMERA_QA_PASSWORD in the Streamlit app secrets."
        )
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("TRD Prior Authorization Assistant")
    st.caption("Internal Trimera Health tool")

    password = st.text_input(
        "Password",
        type="password",
    )

    if st.button("Sign in", type="primary"):
        if password == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


def extract_pdf(uploaded_file: Any) -> str:
    reader = PdfReader(uploaded_file)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"[Page {page_number}]\n{text}")

    return "\n\n".join(pages).strip()


def clean_json(raw_text: str) -> str:
    cleaned = raw_text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    return cleaned.strip()


def as_list(value: Any) -> list:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def show_bullets(items: Any) -> None:
    values = as_list(items)

    if not values:
        st.write("None documented.")
        return

    for item in values:
        if isinstance(item, dict):
            name = str(item.get("item", "")).strip()
            status = str(item.get("status", "")).strip()
            details = str(item.get("details", "")).strip()

            parts = [
                value
                for value in [name, status, details]
                if value
            ]

            if parts:
                st.markdown("- " + " — ".join(parts))
        else:
            st.markdown(f"- {item}")


EXTRACTION_PROMPT = """
You assist a psychiatric prior authorization coordinator.

Extract useful information from a completed provider note for
either TMS or Spravato.

This is an extraction task only.

RULES

- Do not determine eligibility.
- Do not determine medical necessity.
- Do not recommend approval or denial.
- Do not state whether payer criteria are met.
- Do not invent facts.
- Diagnosis must always be F33.2.
- Do not create a missing-information section.
- Keep the output concise.
- Return valid JSON only.
- Do not use Markdown code fences.

MEDICATIONS

Extract antidepressants and other psychiatric medications
relevant to TMS or Spravato prior authorization.

Include:

- Medication name
- Medication class
- Dose, when documented
- Duration or dates, when documented
- Side effects, intolerance, response, or reason stopped

If dose is absent, use "Not documented".

If duration is absent, use "Not documented".

If no response, failure reason, or side effect is documented,
use "No response documented".

Include relevant augmentation medications.

DEPRESSIVE HISTORY

Extract:

- Approximate depression onset
- Current depressive episode duration
- Previous depressive episode timelines
- Dates or approximate years
- Depressive symptoms
- Functional impairment
- Suicidal ideation, when documented
- PHQ-9 or other rating-scale results

THERAPY HISTORY

Extract:

- Therapy type
- Start date or approximate year
- Duration
- Frequency
- Response
- Whether therapy is current

TMS SAFETY SCREENING

For TMS, include every item below:

- Seizure history
- Ferromagnetic metal in or near the head
- Cochlear implant
- Deep brain stimulator
- Implanted cranial hardware
- Other implanted device relevant to TMS
- Significant head trauma
- Psychosis
- Mania

SPRAVATO SAFETY SCREENING

For Spravato, include every item below:

- Blood pressure readings
- Hypertension
- Aneurysm
- Arteriovenous malformation
- Intracranial hemorrhage
- Psychosis
- Pregnancy
- Substance-use concerns

For each safety item use one status:

- Explicitly denied
- Present
- Not documented

Add brief details when available.

PERTINENT MEDICAL HISTORY

Extract pertinent medical diagnoses or history that may help
staff complete the authorization.

Return exactly this JSON structure:

{
  "diagnosis": "F33.2",
  "medications": [
    {
      "medication": "",
      "class": "",
      "dose": "",
      "duration": "",
      "outcome": ""
    }
  ],
  "depressive_history": [],
  "therapy_history": [],
  "treatment_safety": [
    {
      "item": "",
      "status": "",
      "details": ""
    }
  ],
  "pertinent_medical_history": [],
  "other_useful_information": []
}
""".strip()


password_gate()


with st.sidebar:
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()

    st.write(f"Model: `{MODEL}`")
    st.info("The API key remains in the app secrets.")


st.title("📄 TRD Prior Authorization Assistant")

st.caption(
    "Extract useful TMS or Spravato authorization information "
    "from a completed provider note."
)

treatment = st.radio(
    "Treatment",
    ["TMS", "Spravato"],
    horizontal=True,
)

method = st.radio(
    "Provider note",
    ["Paste text", "Upload PDF"],
    horizontal=True,
)

note_text = ""

if method == "Paste text":
    note_text = st.text_area(
        "Paste completed provider note",
        height=360,
        placeholder="Paste the provider note here...",
    )

else:
    uploaded_file = st.file_uploader(
        "Upload completed provider note",
        type=["pdf"],
    )

    if uploaded_file is not None:
        try:
            note_text = extract_pdf(uploaded_file)
            st.success("PDF text extracted.")
        except Exception as exc:
            st.error(f"Could not read the PDF: {exc}")
            