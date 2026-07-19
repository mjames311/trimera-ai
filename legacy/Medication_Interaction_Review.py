import os
from typing import Any

import streamlit as st
from openai import OpenAI


st.set_page_config(
    page_title="Medication Interaction Review",
    page_icon="💊",
    layout="wide",
)

APP_TITLE = "Medication Interaction Review"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")
API_KEY = os.getenv("OPENAI_API_KEY", "")
SUPPORTED_FILE_TYPES = ["pdf", "docx", "txt", "rtf"]

SYSTEM_INSTRUCTIONS = """
You are Trimera Medication Interaction Review, a clinician-facing support tool
for an outpatient psychiatry practice.

Review one patient note, identify the patient's CURRENT medications, and assess
potential medication-related safety concerns.

Rules:
1. Do not treat discontinued medications, past trials, allergies, medications
   merely discussed, or family-history medications as active.
2. Put ambiguous medications under "Uncertain medication status."
3. Include prescription drugs, OTC drugs, supplements, cannabis products, and
   PRN medications when present.
4. Preserve dose, route, frequency, and PRN status when documented.
5. Review for drug-drug interactions, duplicate therapy, CNS or respiratory
   depression, serotonin burden, QT concerns, seizure-threshold concerns,
   blood-pressure or heart-rate effects, bleeding risk, CYP effects,
   lithium-related concerns, stimulant-related concerns, and meaningful
   alcohol, cannabis, food, or supplement interactions.
6. Do not invent medications, diagnoses, doses, labs, or patient facts.
7. Do not repeat patient identifiers in the response.
8. Do not make autonomous treatment changes. Give clinician-facing monitoring
   or verification considerations only.
9. State clearly that the review requires clinician verification against the
   current medication list, prescribing information, pharmacy record, or a
   pharmacist.

Use this structure:

# Medication Interaction Review

## Current medications identified
Table: Medication | Dose | Frequency/Route | Status

## Highest-priority concerns
For each: Severity, combination or issue, why it matters, and clinician
consideration.

## Additional medication-safety findings

## Uncertain medication status

## Clinician verification
""".strip()


def password_gate() -> None:
    if st.session_state.get("authenticated"):
        return

    if not TEST_PASSWORD:
        st.error("TRIMERA_QA_PASSWORD is not configured.")
        st.stop()

    st.title(APP_TITLE)
    st.caption("Internal Trimera Health clinician tool")
    entered = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        if entered == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Incorrect password.")

    st.stop()


def get_client() -> OpenAI:
    if not API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()
    return OpenAI(api_key=API_KEY)


def upload_note(client: OpenAI, uploaded_file: Any) -> str:
    uploaded_file.seek(0)
    created = client.files.create(
        file=(
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        ),
        purpose="user_data",
    )
    return created.id


def delete_note(client: OpenAI, file_id: str | None) -> None:
    if not file_id:
        return
    try:
        client.files.delete(file_id)
    except Exception:
        pass


def build_input(
    pasted_note: str,
    file_id: str | None,
    additional_request: str,
) -> list[dict[str, Any]]:
    content: list[dict[str, str]] = []

    if file_id:
        content.append({"type": "input_file", "file_id": file_id})

    if pasted_note.strip():
        content.append(
            {
                "type": "input_text",
                "text": "PATIENT NOTE:\n\n" + pasted_note.strip(),
            }
        )

    request_text = (
        "Extract the CURRENT medication list from the uploaded or pasted note "
        "and perform the medication interaction and safety review described in "
        "the instructions."
    )

    if additional_request.strip():
        request_text += "\n\nAdditional focus: " + additional_request.strip()

    content.append({"type": "input_text", "text": request_text})
    return [{"role": "user", "content": content}]


password_gate()

with st.sidebar:
    st.markdown("### Medication Interaction Review")
    st.caption(
        "Upload or paste one patient note. The tool extracts active "
        "medications and produces a clinician-facing interaction review."
    )

    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.title("💊 Medication Interaction Review")
st.caption(
    "Upload a patient note or paste the note below, then run the review."
)

st.warning(
    "Clinician review required. Confirm the active medication list and verify "
    "important findings against current prescribing information or a pharmacist."
)

uploaded_note = st.file_uploader(
    "Upload patient note",
    type=SUPPORTED_FILE_TYPES,
    accept_multiple_files=False,
    help="Supported formats: PDF, DOCX, TXT, and RTF.",
)

st.markdown("**Or paste the note**")

pasted_note = st.text_area(
    "Paste patient note",
    height=320,
    placeholder=(
        "Paste the progress note, medication-management note, or current "
        "medication section here..."
    ),
    label_visibility="collapsed",
)

additional_request = st.text_input(
    "Optional focus",
    placeholder="Example: Focus on QT risk, serotonin burden, or sedation.",
)

has_note = bool(uploaded_note) or bool(pasted_note.strip())

if st.button(
    "Run medication interaction review",
    type="primary",
    use_container_width=True,
    disabled=not has_note,
):
    client = get_client()
    temporary_file_id: str | None = None

    try:
        if uploaded_note is not None:
            with st.spinner("Uploading and reading the patient note..."):
                temporary_file_id = upload_note(client, uploaded_note)

        api_input = build_input(
            pasted_note=pasted_note,
            file_id=temporary_file_id,
            additional_request=additional_request,
        )

        with st.spinner(
            "Extracting current medications and reviewing interactions..."
        ):
            response = client.responses.create(
                model=MODEL,
                instructions=SYSTEM_INSTRUCTIONS,
                input=api_input,
            )

        st.session_state["medication_review_result"] = (
            response.output_text
            or "No review was returned. Please verify the note and try again."
        )

    except Exception as exc:
        st.error(f"Medication review failed:\n\n{exc}")

    finally:
        delete_note(client, temporary_file_id)

if st.session_state.get("medication_review_result"):
    st.divider()
    st.markdown(st.session_state["medication_review_result"])

    st.download_button(
        "Download review as text",
        data=st.session_state["medication_review_result"],
        file_name="medication_interaction_review.txt",
        mime="text/plain",
        use_container_width=True,
    )

    if st.button("Clear review", use_container_width=True):
        st.session_state.pop("medication_review_result", None)
        st.rerun()
