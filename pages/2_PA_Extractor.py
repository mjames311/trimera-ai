import os
from typing import List

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader


st.set_page_config(
    page_title="TRD Prior Authorization Assistant",
    page_icon="📄",
    layout="wide",
)

APP_TITLE = "TRD Prior Authorization Assistant"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

EXTRACTOR_PROMPT = """
You are Trimera Health's prior authorization assistant for outpatient
behavioral health and treatment-resistant depression services.

Review the uploaded prior authorization document and produce a practical,
structured summary for Trimera staff.

Rules:
- Use only information contained in the uploaded document.
- Never invent patient facts, payer requirements, diagnoses, medications,
  dates, or authorization criteria.
- Clearly label anything that is not found.
- Preserve exact names, identifiers, dates, phone numbers, fax numbers,
  reference numbers, deadlines, and payer wording when available.
- Distinguish payer instructions from your own suggestions.
- Keep the output concise enough for staff to use operationally.
- Do not guarantee approval.

Return this format:

TRIMERA PRIOR AUTHORIZATION SUMMARY

Patient:
[Name or Not found]

Date of Birth:
[DOB or Not found]

Insurance / Plan:
[Plan name and type or Not found]

Member ID:
[ID or Not found]

Requesting Provider:
[Name or Not found]

Requested Service / Medication:
[Service, medication, dose, frequency, or Not found]

Diagnosis / ICD-10:
[Diagnosis and code or Not found]

Authorization / Reference Number:
[Number or Not found]

Payer Contact Information:
- Phone:
- Fax:
- Portal / Address:

Current Status:
[Pending, denied, additional information requested, approved, or unclear]

Payer Request / Coverage Issue:
[Plain-English explanation]

Required Information or Records:
- [Item]
- [Item]

Missing or Unclear Information:
- [Item]
or
None identified.

Deadline / Time Limit:
[Deadline or Not found]

Recommended Next Actions:
1. [Action]
2. [Action]
3. [Action]

Staff Notes:
[Important operational details, exact payer language, or caution points]
""".strip()

FOLLOWUP_PROMPT = """
You are Ask Trimera inside the Prior Authorization module.

You are given:
1. The original uploaded PA document text.
2. The original PA extraction report.
3. The user's follow-up conversation.

Answer questions about this specific prior authorization.

Rules:
- Use only the supplied document and report for case-specific facts.
- Never invent missing information.
- Clearly distinguish payer instructions from suggested next steps.
- You may explain the payer request, identify missing records, draft a concise
  fax cover sheet, internal note, provider message, or appeal outline when
  asked.
- Do not guarantee approval.
- Keep responses practical and concise.
""".strip()


def password_gate() -> None:
    if not TEST_PASSWORD:
        st.warning("TRIMERA_QA_PASSWORD is not configured.")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title(APP_TITLE)
    st.caption("Internal Trimera Health tool")

    entered = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        if entered == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


def extract_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    pages: List[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        pages.append(
            f"[Page {page_number}]\n{page.extract_text() or ''}"
        )

    return "\n\n".join(pages)


def reset_pa_session() -> None:
    for key in [
        "pa_document_text",
        "pa_report",
        "pa_followup_messages",
        "pa_filename",
    ]:
        st.session_state.pop(key, None)


password_gate()

with st.sidebar:
    if st.button("Start new PA review", use_container_width=True):
        reset_pa_session()
        st.rerun()

    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.write(f"Model: `{MODEL}`")
    st.info("The API key remains server-side.")


st.title("📄 TRD Prior Authorization Assistant")
st.caption(
    "Upload a prior authorization document to extract payer requirements "
    "and next steps."
)

uploaded = st.file_uploader(
    "Upload PA document",
    type=["pdf"],
)

document_text = ""

if uploaded:
    try:
        document_text = extract_pdf(uploaded)

        if document_text.strip():
            st.success(
                f"PDF text extracted from {uploaded.name}."
            )
        else:
            st.warning(
                "The PDF did not contain selectable text. "
                "It may be an image-only scan."
            )

    except Exception as exc:
        st.error(f"Could not read PDF: {exc}")


if st.button(
    "Analyze prior authorization",
    type="primary",
    use_container_width=True,
):
    if not document_text.strip():
        st.error("Upload a readable PA PDF first.")
        st.stop()

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()

    client = OpenAI(api_key=OPENAI_API_KEY)

    with st.spinner("Analyzing prior authorization..."):
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=EXTRACTOR_PROMPT,
                input=document_text,
            )
            report = response.output_text
        except Exception as exc:
            st.error(f"OpenAI request failed: {exc}")
            st.stop()

    st.session_state["pa_document_text"] = document_text
    st.session_state["pa_report"] = report
    st.session_state["pa_filename"] = uploaded.name
    st.session_state["pa_followup_messages"] = []


if st.session_state.get("pa_report"):
    report = st.session_state["pa_report"]

    st.divider()
    st.subheader("PA summary")

    st.text_area(
        "Report",
        value=report,
        height=620,
    )

    st.download_button(
        "Download PA summary",
        data=report,
        file_name="trimera_pa_summary.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.divider()
    st.subheader("💬 Ask Trimera about this PA")
    st.caption(
        "Ask what the payer is requesting, what is missing, or request "
        "a provider message, fax cover sheet, or appeal outline."
    )

    if "pa_followup_messages" not in st.session_state:
        st.session_state["pa_followup_messages"] = []

    for message in st.session_state["pa_followup_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    followup_question = st.chat_input(
        "Ask a follow-up about this prior authorization..."
    )

    if followup_question:
        st.session_state["pa_followup_messages"].append(
            {
                "role": "user",
                "content": followup_question,
            }
        )

        with st.chat_message("user"):
            st.markdown(followup_question)

        conversation = "\n\n".join(
            f"{message['role'].upper()}:\n{message['content']}"
            for message in st.session_state["pa_followup_messages"]
        )

        followup_context = f"""
SOURCE FILE:
{st.session_state.get("pa_filename", "Unknown")}

ORIGINAL PA DOCUMENT:
{st.session_state["pa_document_text"]}

ORIGINAL PA SUMMARY:
{st.session_state["pa_report"]}

FOLLOW-UP CONVERSATION:
{conversation}
""".strip()

        client = OpenAI(api_key=OPENAI_API_KEY)

        with st.chat_message("assistant"):
            with st.spinner("Reviewing the PA context..."):
                try:
                    response = client.responses.create(
                        model=MODEL,
                        instructions=FOLLOWUP_PROMPT,
                        input=followup_context,
                    )
                    answer = response.output_text
                    st.markdown(answer)
                except Exception as exc:
                    st.error(f"OpenAI request failed: {exc}")
                    st.stop()

        st.session_state["pa_followup_messages"].append(
            {
                "role": "assistant",
                "content": answer,
            }
        )
