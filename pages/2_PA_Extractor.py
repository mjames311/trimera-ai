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
    """Read a setting from environment variables or Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value

    try:
        secret_value = st.secrets.get(name, default)
        return str(secret_value) if secret_value is not None else default
    except Exception:
        return default


MODEL = get_setting("OPENAI_MODEL", "gpt-5.5")
TEST_PASSWORD = get_setting("TRIMERA_QA_PASSWORD")
OPENAI_API_KEY = get_setting("OPENAI_API_KEY")


def password_gate() -> None:
    """Require the same password used by the Documentation QA tool."""
    if not TEST_PASSWORD:
        st.warning("Set TRIMERA_QA_PASSWORD in the Streamlit app secrets.")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("TRD Prior Authorization Assistant")
    st.caption("Internal Trimera Health tool")

    entered = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        if entered == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


def extract_pdf(uploaded_file: Any) -> str:
    """Extract selectable text from an uploaded PDF."""
    reader = PdfReader(uploaded_file)
    pages: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"[Page {page_number}]\n{text}")

    return "\n\n".join(pages).strip()


def clean_json_text(raw_text: str) -> str:
    """Remove Markdown code fences before JSON parsing."""
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def render_bullets(items: Any, empty_text: str = "None documented.") -> None:
    values = as_list(items)
    if not values:
        st.write(empty_text)
        return

    for item in values:
        if isinstance(item, dict):
            label = str(item.get("item", item.get("name", ""))).strip()
            status = str(item.get("status", "")).strip()
            details = str(item.get("details", "")).strip()

            line = " — ".join(part for part in [label, status, details] if part)
            st.markdown(f"- {line}" if line else "- Not documented")
        else:
            st.markdown(f"- {item}")


EXTRACTION_PROMPT = r"""
You assist a psychiatric prior-authorization coordinator by extracting facts
from a completed provider note for either TMS or Spravato.

This is an extraction task only.

Rules:
- Do not determine eligibility, approval, medical necessity, or whether payer
  criteria are met.
- Do not recommend approval or denial.
- Do not invent facts.
- Diagnosis must always be returned as F33.2, regardless of diagnoses stated
  in the note.
- Do not create an "information not found" or "missing information" section.
- Keep the result concise and practical for staff completing a PA form.
- Return valid JSON only. Do not use Markdown code fences.

Medication rules:
- Extract antidepressants and other psychiatric medications relevant to a
  TMS or Spravato PA, including augmentation agents when documented.
- Include medication class.
- Include dose and duration when documented.
- If dose or duration is absent, write "Not documented".
- If a side effect, intolerance, lack of benefit, partial response, loss of
  effect, or other outcome is documented, report it.
- If no specific outcome or side effect is documented, write
  "No response documented".
- Do not include unrelated medications unless they are pertinent to the PA.

Depressive history:
- Extract depression onset, current episode duration, prior episode timelines,
  meaningful dates or approximate years, depressive symptoms, functional
  impairment, suicidality, and rating-scale results such as PHQ-9 when present.

Therapy:
- Extract therapy type, start date or approximate year, duration, frequency,
  response, and whether it is current when documented.

TMS safety items:
- Seizure history
- Ferromagnetic metal in or near the head
- Cochlear implant
- Deep brain stimulator
- Implanted cranial hardware or other implanted device relevant to TMS
- Significant head trauma
- Psychosis
- Mania

Spravato safety items:
- Blood-pressure readings
- Hypertension
- Aneurysm
- Arteriovenous malformation
- Intracranial hemorrhage
- Psychosis
- Pregnancy
- Substance-use concerns

For the selected treatment, include every listed safety item. Use one of:
- "Explicitly denied"
- "Present"
- "Not documented"
Add concise details when available.

Also extract pertinent medical diagnoses or medical history that may help staff
complete the authorization.

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
    st.info("The API key remains in the server-side app secrets.")

st.title("📄 TRD Prior Authorization Assistant")
st.caption(
    "Extract useful TMS or Spravato authorization information from a provider note."
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

if st.button(
    "Extract PA Information",
    type="primary",
    use_container_width=True,
):
    if not note_text.strip():
        st.error("Paste or upload a provider note.")
        st.stop()

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is not configured in the app secrets.")
        st.stop()

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_input = f"""
SELECTED TREATMENT:
{treatment}

PROVIDER NOTE:
{note_text}
""".strip()

    with st.spinner("Extracting prior-authorization information..."):
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=EXTRACTION_PROMPT,
                input=user_input,
            )
            raw_result = response.output_text
            result = json.loads(clean_json_text(raw_result))
        except json.JSONDecodeError:
            st.error("The extraction completed, but the result was not valid JSON.")
            with st.expander("Show raw model response"):
                st.text(raw_result if "raw_result" in locals() else "")
            st.stop()
        except Exception as exc:
            st.error(f"OpenAI request failed: {exc}")
            st.stop()

    st.success("Extraction complete")

    st.subheader("Diagnosis")
    st.code("F33.2", language=None)

    with st.expander("Previous Medication Trials", expanded=True):
        medications = as_list(result.get("medications"))

        if medications:
            normalized_medications = []
            for medication in medications:
                if not isinstance(medication, dict):
                    continue

                normalized_medications.append(
                    {
                        "Medication": medication.get("medication", ""),
                        "Class": medication.get("class", ""),
                        "Dose": medication.get("dose", "Not documented"),
                        "Duration": medication.get("duration", "Not documented"),
                        "Outcome": medication.get(
                            "outcome", "No response documented"
                        ),
                    }
                )

            if normalized_medications:
                st.dataframe(
                    normalized_medications,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.write("No relevant medication trials were extracted.")
        else:
            st.write("No relevant medication trials were extracted.")

    with st.expander("Depressive History", expanded=True):
        render_bullets(result.get("depressive_history"))

    with st.expander("Therapy History"):
        render_bullets(result.get("therapy_history"))

    with st.expander(f"{treatment} Safety Screening", expanded=True):
        render_bullets(result.get("treatment_safety"))

    with st.expander("Pertinent Medical History"):
        render_bullets(result.get("pertinent_medical_history"))

    with st.expander("Other Useful Information"):
        render_bullets(result.get("other_useful_information"))

    download_text = json.dumps(result, indent=2, ensure_ascii=False)

    st.download_button(
        "Download Extracted Information",
        data=download_text,
        file_name=f"{treatment.lower()}_pa_extraction.json",
        mime="application/json",
        use_container_width=True,
    )

    st.caption(
        "This tool organizes documented information only. "
        "It does not determine payer eligibility or medical necessity."
    )