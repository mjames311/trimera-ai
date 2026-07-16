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

BASE_RULES = """
You are Trimera Health's TRD prior authorization assistant.

Use only the uploaded document.
Never invent medications, dates, durations, outcomes, diagnoses, payer criteria,
contraindications, authorization numbers, or patient facts.

Preserve exact medication names, drug classes, doses, start dates, end dates,
durations, outcomes, adverse effects, and reasons for discontinuation when stated.

Clearly separate:
1. What is documented
2. What the payer requires
3. What is missing or unclear

Do not guarantee approval.
""".strip()

TMS_PROMPT = """
The selected request type is TMS.

Extract:
- Patient, payer, member ID, group number, provider, authorization number
- Requested TMS type, CPT codes, number of sessions, start date
- Diagnosis and ICD-10
- Every antidepressant trial with:
  medication, class, dose, start date, end date, duration, outcome,
  reason stopped, and whether adequacy is clear
- Distinct antidepressant class count
- Augmentation trials
- Psychotherapy type, frequency, duration, outcome
- PHQ-9, MADRS, HAM-D, or other scale with score and date
- TMS rule-outs and contraindications:
  seizure disorder, implanted metal/electronic devices near the head,
  cochlear implants, aneurysm clips/coils, deep brain stimulator,
  vagus nerve stimulator, bipolar/mania, psychosis, substance concerns,
  and any payer-specific exclusions
- Prior TMS history
- Exact payer criteria
- Missing information
""".strip()

SPRAVATO_PROMPT = """
The selected request type is Spravato / Esketamine.

Extract:
- Patient, payer, member ID, group number, provider, authorization number
- Requested dose, induction vs maintenance, frequency, start date,
  pharmacy vs medical benefit
- Diagnosis and ICD-10
- Every antidepressant trial with:
  medication, class, dose, start date, end date, duration, outcome,
  reason stopped, and whether adequacy is clear
- Distinct antidepressant class count
- Augmentation trials
- Current oral antidepressant and dose
- Psychotherapy history
- PHQ-9, MADRS, HAM-D, or other scale with score and date
- Spravato rule-outs and contraindications:
  aneurysmal vascular disease, AV malformation, intracerebral hemorrhage,
  hypersensitivity, uncontrolled hypertension, pregnancy if addressed,
  active psychosis if addressed, substance concerns if addressed,
  and any payer-specific exclusions
- REMS/site-of-care requirements
- Prior ketamine/esketamine history
- Exact payer criteria
- Missing information
""".strip()

OUTPUT_FORMAT = """
Return exactly this format:

TRIMERA TRD PRIOR AUTHORIZATION REVIEW

REQUEST TYPE
[TMS or Spravato / Esketamine]

PATIENT / PLAN
Patient:
DOB:
Insurance / Plan:
Plan Type:
Member ID:
Group Number:
Requesting Provider:
Authorization / Reference Number:

REQUESTED TREATMENT
Requested Service / Medication:
Dose / Protocol:
Frequency:
Requested Units / Sessions:
Requested Start Date:
Benefit Route:
Current Status:

DIAGNOSIS
Primary Diagnosis:
ICD-10:
Severity / Episode:
Other Relevant Diagnoses:

ANTIDEPRESSANT TRIALS
Use a table:
Medication | Class | Dose | Start Date | End Date | Duration | Outcome | Reason Stopped | Adequate Trial?

DISTINCT ANTIDEPRESSANT CLASSES DOCUMENTED
- [Class]
- [Class]
Class Count:
At least two distinct classes documented: YES | NO | UNCLEAR

AUGMENTATION / OTHER PSYCHIATRIC TRIALS
Use a table:
Medication / Therapy | Class or Type | Dose | Duration | Outcome

CURRENT TREATMENT
Current Antidepressant:
Current Dose:
Other Current Psychiatric Medications:
Concurrent Treatment Requirement Met: YES | NO | UNCLEAR

PSYCHOTHERAPY HISTORY
Type:
Frequency:
Duration:
Outcome:
Meets stated payer requirement: YES | NO | UNCLEAR

SEVERITY MEASURES
Use a table:
Scale | Score | Date | Interpretation if explicitly stated

RULE-OUTS / CONTRAINDICATIONS
Use a table:
Criterion | Documented Status | Supporting Text or Location

PRIOR TRD TREATMENT HISTORY
Prior TMS:
Prior Ketamine / Esketamine:
Other Neuromodulation:

PAYER CRITERIA IDENTIFIED
- [Exact criterion]
- [Exact criterion]

MISSING OR UNCLEAR ITEMS
- [Specific missing item]
- [Specific missing item]

DEADLINE / CONTACT INFORMATION
Deadline:
Phone:
Fax:
Portal / Address:

RECOMMENDED NEXT ACTIONS
1. [Action]
2. [Action]
3. [Action]

BOTTOM LINE
[One concise paragraph stating whether the document appears complete,
incomplete, or unclear for the selected request type, without guaranteeing approval.]
""".strip()

FOLLOWUP_PROMPT = """
You are Ask Trimera inside the TRD Prior Authorization Assistant.

Use the selected request type, uploaded document, original PA review,
and follow-up conversation.

Never invent facts.
Preserve medication names, classes, dates, durations, outcomes, and rule-outs.
Clearly distinguish documented facts from missing information.
You may draft provider messages, fax cover sheets, payer responses,
appeal outlines, internal notes, and checklists.
Do not guarantee authorization.
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
        pages.append(f"[Page {page_number}]\n{page.extract_text() or ''}")

    return "\n\n".join(pages)


def reset_pa_session() -> None:
    for key in [
        "pa_request_type",
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
    "Select TMS or Spravato, then upload the PA document for a detailed review."
)

request_type = st.radio(
    "Select request type",
    ["TMS", "Spravato / Esketamine"],
    horizontal=True,
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
            st.success(f"PDF text extracted from {uploaded.name}.")
        else:
            st.warning(
                "The PDF did not contain selectable text. It may be an image-only scan."
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

    request_prompt = TMS_PROMPT if request_type == "TMS" else SPRAVATO_PROMPT
    instructions = f"{BASE_RULES}\n\n{request_prompt}\n\n{OUTPUT_FORMAT}"

    client = OpenAI(api_key=OPENAI_API_KEY)

    with st.spinner("Analyzing prior authorization..."):
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=instructions,
                input=document_text,
            )
            report = response.output_text
        except Exception as exc:
            st.error(f"OpenAI request failed: {exc}")
            st.stop()

    st.session_state["pa_request_type"] = request_type
    st.session_state["pa_document_text"] = document_text
    st.session_state["pa_report"] = report
    st.session_state["pa_filename"] = uploaded.name
    st.session_state["pa_followup_messages"] = []


if st.session_state.get("pa_report"):
    report = st.session_state["pa_report"]

    st.divider()
    st.subheader("Detailed PA review")

    st.text_area(
        "Report",
        value=report,
        height=760,
    )

    st.download_button(
        "Download PA review",
        data=report,
        file_name="trimera_trd_pa_review.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.divider()
    st.subheader("💬 Ask Trimera about this PA")
    st.caption(
        "Ask about medication classes, trial duration, rule-outs, missing criteria, "
        "or request a provider message, fax cover sheet, or appeal outline."
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
            {"role": "user", "content": followup_question}
        )

        with st.chat_message("user"):
            st.markdown(followup_question)

        conversation = "\n\n".join(
            f"{message['role'].upper()}:\n{message['content']}"
            for message in st.session_state["pa_followup_messages"]
        )

        followup_context = f"""
REQUEST TYPE:
{st.session_state["pa_request_type"]}

SOURCE FILE:
{st.session_state.get("pa_filename", "Unknown")}

ORIGINAL PA DOCUMENT:
{st.session_state["pa_document_text"]}

ORIGINAL PA REVIEW:
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
            {"role": "assistant", "content": answer}
        )
