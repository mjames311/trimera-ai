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

Preserve exact medication names, documented doses, start dates, end dates,
durations, outcomes, adverse effects, and reasons for discontinuation when stated.

You may infer a medication's pharmacologic class from standard pharmacology.
When a patient-specific dose is absent, you may provide a clearly labeled typical
adult therapeutic dose range as general reference information. Never present a
reference range as if it were documented for the patient.

Clearly separate what is documented from what the payer requires.
Do not create a standalone Missing / Not Documented section.

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
Return exactly this structure using valid Markdown headings and tables:

# TRIMERA TRD PRIOR AUTHORIZATION REVIEW

## Request Type
[TMS or Spravato / Esketamine]

## Patient / Plan
- **Patient:** [value]
- **DOB:** [value]
- **Insurance / Plan:** [value]
- **Plan Type:** [value]
- **Member ID:** [value]
- **Group Number:** [value]
- **Requesting Provider:** [value]
- **Authorization / Reference Number:** [value]

## Requested Treatment
- **Requested Service / Medication:** [value]
- **Dose / Protocol:** [value]
- **Frequency:** [value]
- **Requested Units / Sessions:** [value]
- **Requested Start Date:** [value]
- **Benefit Route:** [value]
- **Current Status:** [value]

## Diagnosis
- **Primary Diagnosis:** [value]
- **ICD-10:** [value]
- **Severity / Episode:** [value]
- **Other Relevant Diagnoses:** [value]

## Current Psychiatric Treatment

Use a valid Markdown table:

| Medication | Dose / Directions | Status |
|---|---|---|

Only include medications that appear current in the document.

## Prior Antidepressant / Psychiatric Medication Trials

Use a valid Markdown table:

| Medication | Pharmacologic Class | Documented Dose | Typical Adult Therapeutic Dose Range* | Duration / Timing | Documented Outcome |
|---|---|---|---|---|---|

For every psychiatric medication trial:

- Preserve the exact medication name from the uploaded document.
- Infer the pharmacologic class from standard pharmacology even if the provider did not explicitly document the class.
- Examples:
  - Lexapro, Zoloft, Prozac, Celexa, Paxil → SSRI
  - Cymbalta, Effexor XR, Pristiq → SNRI
  - Wellbutrin / bupropion → NDRI
  - Remeron / mirtazapine → NaSSA
  - Trintellix / vortioxetine → Serotonin modulator
  - Viibryd / vilazodone → Serotonin partial agonist/reuptake inhibitor
  - Abilify, Vraylar, Seroquel, olanzapine → Atypical antipsychotic
  - Lamictal / lamotrigine, lithium → Mood stabilizer
  - Buspirone → Anxiolytic
  - Propranolol → Beta blocker
  - Clonidine, guanfacine → Alpha-2 agonist
  - Ativan, Xanax, Klonopin, Valium → Benzodiazepine
  - Trazodone → Serotonin antagonist/reuptake inhibitor
  - Belsomra → Orexin receptor antagonist
- For Documented Dose, use only the dose stated in the uploaded record. If absent, write "Not documented."
- If the patient-specific dose is absent, populate Typical Adult Therapeutic Dose Range using standard FDA labeling and widely accepted clinical references.
- If a patient-specific dose is documented, write "Not needed — dose documented" in the Typical Adult Therapeutic Dose Range column.
- Never imply a reference range was the patient's actual dose.
- Duration / Timing and Documented Outcome must come only from the uploaded document.
- Include side effects, treatment failure, loss of effectiveness, or reason stopped inside Documented Outcome.
- Do not include separate rows for items completely absent from the document.

*Typical Adult Therapeutic Dose Range is general clinical reference information only. It is not extracted from the patient's record unless specifically documented.

## Distinct Antidepressant Classes Documented
- [Class]
- [Class]
- **Class Count:** [number]
- **At least two distinct classes documented:** YES | NO | UNCLEAR

## Psychotherapy History
- **Type:** [value]
- **Frequency:** [value]
- **Duration:** [value]
- **Outcome:** [value]
- **Meets stated payer requirement:** YES | NO | UNCLEAR

## Severity Measures

Use a valid Markdown table:

| Scale | Score | Date | Interpretation if explicitly stated |
|---|---|---|---|

## Rule-Outs / Contraindications

Use a valid Markdown table:

| Criterion | Documented Status | Supporting Text |
|---|---|---|

Only include criteria actually addressed in the document or clearly required by the selected treatment type.
Do not create a separate Missing / Not Documented section.

## Prior TRD Treatment History
- **Prior TMS:** [value]
- **Prior Ketamine / Esketamine:** [value]
- **Other Neuromodulation:** [value]

## Payer Criteria Identified
- [criterion]
- [criterion]

## Recommended Next Actions
1. [action]
2. [action]
3. [action]

## Bottom Line
[One concise paragraph stating whether the document appears complete, incomplete, or unclear for the selected request type, without guaranteeing approval.]
""".strip()

FOLLOWUP_PROMPT = """
You are Ask Trimera inside the TRD Prior Authorization Assistant.

Use the selected request type, uploaded document, original PA review,
and follow-up conversation.

Never invent facts.
Preserve medication names, inferred pharmacologic classes, dates, durations,
outcomes, and rule-outs. Clearly distinguish patient-specific documented doses
from general therapeutic-dose reference ranges.
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

    st.markdown(report)

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
