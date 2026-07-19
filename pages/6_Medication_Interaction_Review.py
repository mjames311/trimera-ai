import os
from typing import Any

import streamlit as st
from openai import OpenAI
from auth import logout_user, require_auth
from research import WEB_SEARCH_TOOLS, with_web_research
from theme import apply_trimera_theme, page_header, render_topbar, sidebar_label, sidebar_model, sidebar_reminder

st.set_page_config(
    page_title="Medication Interaction Review",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "Medication Interaction Review"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
API_KEY = os.getenv("OPENAI_API_KEY", "")
SUPPORTED_FILE_TYPES = ["pdf", "docx", "txt", "rtf"]

SYSTEM_INSTRUCTIONS = """
You are Trimera Medication Interaction Review, a clinician-facing support tool
for an outpatient psychiatry practice.

You will first review one patient note, identify the patient's CURRENT
medications, and assess potential medication-related safety concerns. After the
initial review, continue as a back-and-forth clinical support chat about the same
note and medication list.

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
8. Do not make autonomous treatment changes. Give clinician-facing monitoring,
   verification, and prescribing-information considerations only.
9. Clearly distinguish facts from the note, interaction concerns, and clinical
   inference.
10. Maintain the complete conversation context. When the clinician asks a
    follow-up question, answer based on the uploaded or pasted note and all prior
    messages in this chat.
11. Use web search for the initial review and all follow-up questions when it
    can help verify current prescribing information, FDA labeling, safety
    communications, or reputable interaction information.
12. Prefer authoritative sources such as FDA prescribing information, DailyMed,
    NIH/NLM, manufacturer prescribing information, and other primary clinical
    references.
13. Cite web-supported interaction claims in the response. Do not present a web
    search result as equivalent to a dedicated licensed drug-interaction
    database.
14. State clearly that important findings require clinician verification against
    the current medication list, prescribing information, pharmacy record, or a
    pharmacist.

For the INITIAL review, use this structure:

# Medication Interaction Review

## Current medications identified
Table: Medication | Dose | Frequency/Route | Status

## Highest-priority concerns
For each: Severity, combination or issue, why it matters, and clinician
consideration.

## Additional medication-safety findings

## Uncertain medication status

## Clinician verification

For FOLLOW-UP questions, answer directly and concisely. Do not repeat the full
initial report unless requested.
""".strip()


def initialize_state() -> None:
    st.session_state.setdefault("med_chat_messages", [])
    st.session_state.setdefault("med_note_file_id", None)
    st.session_state.setdefault("med_note_name", "")
    st.session_state.setdefault("med_pasted_note", "")


def get_client() -> OpenAI:
    if not API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()
    return OpenAI(api_key=API_KEY)


def upload_note(client: OpenAI, uploaded_file: Any) -> str:
    uploaded_file.seek(0)
    created = client.files.create(
        file=(uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream"),
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


def clear_review() -> None:
    file_id = st.session_state.get("med_note_file_id")
    if file_id and API_KEY:
        try:
            delete_note(OpenAI(api_key=API_KEY), file_id)
        except Exception:
            pass
    st.session_state["med_chat_messages"] = []
    st.session_state["med_note_file_id"] = None
    st.session_state["med_note_name"] = ""
    st.session_state["med_pasted_note"] = ""


def build_api_input() -> list[dict[str, Any]]:
    api_input: list[dict[str, Any]] = []
    for index, message in enumerate(st.session_state["med_chat_messages"]):
        role = message["role"]
        text = message["content"]
        if role == "assistant":
            api_input.append({"role": "assistant", "content": text})
            continue
        content_parts: list[dict[str, str]] = []
        if index == 0:
            file_id = st.session_state.get("med_note_file_id")
            pasted_note = st.session_state.get("med_pasted_note", "")
            if file_id:
                content_parts.append({"type": "input_file", "file_id": file_id})
            if pasted_note:
                content_parts.append({"type": "input_text", "text": "PATIENT NOTE:\n\n" + pasted_note})
        content_parts.append({"type": "input_text", "text": text})
        api_input.append({"role": "user", "content": content_parts})
    return api_input


def run_response(client: OpenAI) -> str:
    response = client.responses.create(model=MODEL, instructions=with_web_research(SYSTEM_INSTRUCTIONS), input=build_api_input(), tools=WEB_SEARCH_TOOLS)
    return response.output_text or "No response was returned."


apply_trimera_theme()
require_auth(APP_TITLE, "Internal Trimera Health clinician tool")
initialize_state()
render_topbar()

with st.sidebar:
    sidebar_label("Quick actions")
    if st.session_state.get("med_chat_messages"):
        if st.button("Clear review and start over", use_container_width=True):
            clear_review()
            st.rerun()
    if st.button("Sign out", use_container_width=True):
        clear_review()
        logout_user()
    sidebar_model(MODEL)
    sidebar_reminder("Clinician review", "Confirm important findings against current prescribing information or a pharmacist.")

page_header(
    "medication",
    "Medication Interaction Review",
    "Upload or paste one patient note, then continue with patient-specific follow-up questions.",
)
if not st.session_state["med_chat_messages"]:
    uploaded_note = st.file_uploader("Upload patient note", type=SUPPORTED_FILE_TYPES, accept_multiple_files=False, help="Supported formats: PDF, DOCX, TXT, and RTF.")
    st.markdown("**Or paste the note**")
    pasted_note = st.text_area("Paste patient note", height=320, placeholder="Paste the progress note, medication-management note, or current medication section here...", label_visibility="collapsed")
    additional_request = st.text_input("Optional focus", placeholder="Example: Focus on QT risk, serotonin burden, or sedation.")
    has_note = bool(uploaded_note) or bool(pasted_note.strip())
    if st.button("Run medication interaction review", type="primary", use_container_width=True, disabled=not has_note):
        client = get_client()
        try:
            if uploaded_note is not None:
                with st.spinner("Uploading and reading the patient note..."):
                    st.session_state["med_note_file_id"] = upload_note(client, uploaded_note)
                    st.session_state["med_note_name"] = uploaded_note.name
            st.session_state["med_pasted_note"] = pasted_note.strip()
            initial_request = "Extract the CURRENT medication list from the uploaded or pasted note and perform the complete medication interaction and safety review described in the instructions."
            if additional_request.strip():
                initial_request += "\n\nAdditional focus: " + additional_request.strip()
            st.session_state["med_chat_messages"].append({"role": "user", "content": initial_request, "display_content": "Run medication interaction review"})
            with st.spinner("Extracting current medications and reviewing interactions..."):
                answer = run_response(client)
            st.session_state["med_chat_messages"].append({"role": "assistant", "content": answer})
            st.rerun()
        except Exception as exc:
            st.error(f"Medication review failed:\n\n{exc}")
else:
    if st.session_state.get("med_note_name"):
        st.caption(f"Source note: {st.session_state['med_note_name']}")
    elif st.session_state.get("med_pasted_note"):
        st.caption("Source note: pasted text")
    for message in st.session_state["med_chat_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message.get("display_content", message["content"]))
    st.caption("Trimera automatically checks current authoritative medication sources when relevant and cites web-derived information.")
    follow_up = st.chat_input("Ask a follow-up about the medications or interaction review...")
    if follow_up:
        client = get_client()
        st.session_state["med_chat_messages"].append({"role": "user", "content": follow_up})
        with st.chat_message("user"):
            st.markdown(follow_up)
        with st.chat_message("assistant"):
            with st.spinner("Reviewing..."):
                try:
                    answer = run_response(client)
                except Exception as exc:
                    answer = f"Medication review failed:\n\n{exc}"
            st.markdown(answer)
        st.session_state["med_chat_messages"].append({"role": "assistant", "content": answer})
    full_transcript = "\n\n".join(
        f"{message['role'].upper()}:\n{message.get('display_content', message['content'])}"
        for message in st.session_state["med_chat_messages"]
    )
    st.download_button("Download review and chat", data=full_transcript, file_name="medication_interaction_review_chat.txt", mime="text/plain", use_container_width=True)
