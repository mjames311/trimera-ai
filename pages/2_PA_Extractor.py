import json
import os
from typing import List
from urllib.parse import urlencode
from urllib.request import urlopen

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader
from auth import logout_user, require_auth
from research import WEB_SEARCH_TOOLS, with_web_research
from theme import apply_trimera_theme, page_header, render_topbar, sidebar_label, sidebar_model, sidebar_reminder


st.set_page_config(
    page_title="Prior Authorization Assistant",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "Prior Authorization Assistant"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
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

MEDICATION_RULES = """
You are Trimera Health's medication prior-authorization readiness assistant.

Review the uploaded provider note for the specifically requested medication. The
uploaded note is the only source of patient-specific facts. Never invent a
diagnosis, medication trial, dose, date, duration, response, adverse effect,
contraindication, lab result, insurance detail, or provider statement.

Research current requirements automatically. Prioritize the named payer's own
current formulary, prior-authorization policy, and coverage criteria. Then use
authoritative sources such as FDA labeling, DailyMed, CMS when relevant, and
recognized professional guidance. Cite every web-derived criterion with a usable
URL and identify when an official payer policy could not be confirmed.

Coverage rules vary by payer, plan, diagnosis, formulation, dose, age, and date.
Do not substitute common requirements for a confirmed payer rule. Clearly label
confirmed payer criteria, general clinical or labeling context, and facts actually
documented in the note. Do not recommend changing treatment and do not guarantee
approval. This is preparation for staff review and entry into CoverMyMeds; it does
not submit a prior authorization.
""".strip()

MEDICATION_OUTPUT_FORMAT = """
Return a concise, detailed review using exactly these Markdown sections:

# TRIMERA MEDICATION PRIOR AUTHORIZATION REVIEW

## Request
- **Medication:** [selected medication]
- **Requested dose / formulation:** [entered value or Not provided]
- **Payer / plan:** [entered value]
- **Patient and provider identifiers found in note:** [values or Not documented]

## Readiness Finding
**READY | NEEDS INFORMATION | CRITERIA NOT CONFIRMED**

[One short explanation. READY means the note appears to document the confirmed
criteria; it is not a guarantee of approval.]

## Patient-Specific Support Documented
Use bullets for relevant diagnosis, symptoms/severity, prior medication trials,
doses, durations, outcomes, adverse effects, contraindications, labs, and other
support. Include only facts present in the note.

## Confirmed Payer Requirements
Use a table:

| Requirement | Documented in note | Supporting note text | Authoritative source |
|---|---|---|---|

If an official current payer policy was not found, state that plainly here and do
not present common requirements as confirmed payer requirements.

## Missing or Unclear Documentation
List only information genuinely missing or unclear relative to confirmed criteria
or the requested drug's official labeling. Distinguish coverage documentation
from clinical safety information.

## Likely CoverMyMeds Preparation Items
List the patient, prescriber, diagnosis, previous therapies, dose/formulation,
quantity, days supply, supporting records, and plan-specific answers staff should
have ready. Do not claim these are the exact electronic questions unless confirmed.

## Recommended Administrative Next Steps
Provide a short numbered list for staff. Include verification with the payer when
current plan-specific criteria could not be located.

## Sources
List the authoritative source title, organization, date when available, and URL.
""".strip()

MEDICATION_FOLLOWUP_PROMPT = """
You are Ask Trimera following a medication prior-authorization readiness review.
Use the selected medication, payer, uploaded provider note, original review, and
conversation. The note remains the only source of patient-specific facts.
Automatically research current authoritative payer, FDA, DailyMed, CMS, or
professional sources when needed and cite web-derived claims with usable URLs.
Clearly distinguish confirmed payer rules from general information. You may draft
provider clarification messages, staff checklists, and CoverMyMeds preparation
notes, but do not submit anything, recommend treatment changes, invent facts, or
guarantee authorization.
""".strip()


@st.cache_data(ttl=86400, show_spinner=False)
def search_rxnorm_medications(query: str) -> List[str]:
    """Return current RxNorm concept names that approximately match a drug search."""
    params = urlencode({"term": query.strip(), "maxEntries": 12, "option": 1})
    with urlopen(
        f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?{params}",
        timeout=8,
    ) as response:
        payload = json.load(response)

    names: List[str] = []
    seen = set()
    candidates = payload.get("approximateGroup", {}).get("candidate", [])
    for candidate in candidates:
        rxcui = candidate.get("rxcui")
        if not rxcui:
            continue
        with urlopen(
            f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/properties.json",
            timeout=8,
        ) as response:
            properties = json.load(response).get("properties", {})
        name = properties.get("name")
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            names.append(name)
    return names


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
        "pa_medication",
        "pa_payer",
        "pa_dose_formulation",
        "pa_initial_request",
    ]:
        st.session_state.pop(key, None)


apply_trimera_theme()
require_auth(APP_TITLE, "Internal Trimera Health tool")
render_topbar()

with st.sidebar:
    sidebar_label("Quick actions")
    if st.button("Start new PA review", use_container_width=True):
        reset_pa_session()
        st.rerun()

    if st.button("Sign out", use_container_width=True):
        logout_user()

    sidebar_model(MODEL)
    sidebar_reminder("Secure workflow", "The API key remains server-side.")


page_header(
    "authorization",
    "Prior Authorization Assistant",
    "Review TMS, Spravato, or medication authorization documentation and readiness.",
)

request_type = st.radio(
    "Select request type",
    ["TMS", "Spravato / Esketamine", "Other Medication"],
    horizontal=True,
)

selected_medication = ""
payer = ""
dose_formulation = ""

if request_type == "Other Medication":
    medication_query = st.text_input(
        "Search requested medication",
        placeholder="Start typing a brand or generic medication name...",
    )
    medication_matches: List[str] = []
    if len(medication_query.strip()) >= 2:
        try:
            medication_matches = search_rxnorm_medications(medication_query)
        except Exception:
            st.warning(
                "Medication search is temporarily unavailable. You can still use "
                "the medication name you entered."
            )

    if medication_matches:
        selected_medication = st.selectbox(
            "Select medication",
            medication_matches,
            help="Search results use the National Library of Medicine RxNorm vocabulary.",
        )
    elif medication_query.strip():
        selected_medication = medication_query.strip()
        st.caption("The entered medication name will be used for this review.")

    payer = st.text_input(
        "Insurance payer and plan",
        placeholder="Example: BCBS Texas PPO, OptumRx, or Medicare Part D plan name",
    )
    dose_formulation = st.text_input(
        "Requested dose and formulation (if known)",
        placeholder="Example: 10 mg tablet, one daily",
    )
    st.caption(
        "Medication names are matched using NLM RxNorm. This review prepares staff "
        "for CoverMyMeds; it does not submit the authorization or guarantee coverage."
    )
    st.caption(
        "RxNorm attribution: This product uses publicly available data from the U.S. "
        "National Library of Medicine (NLM), National Institutes of Health, Department "
        "of Health and Human Services; NLM is not responsible for the product and does "
        "not endorse or recommend this or any other product."
    )

initial_request = st.text_area(
    "Questions or special instructions (optional)",
    placeholder=(
        "Tell Trimera what you want reviewed, ask a question, or identify anything "
        "that deserves special attention in the uploaded note."
    ),
    help=(
        "These instructions guide the review but do not replace the platform's "
        "clinical, payer, documentation, or safety rules."
    ),
    height=100,
)

uploaded = st.file_uploader(
    "Upload provider assessment note"
    if request_type == "Other Medication"
    else "Upload PA document",
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
    "Analyze assessment note",
    type="primary",
    use_container_width=True,
):
    if not document_text.strip():
        st.error(
            "Upload a readable provider-note PDF first."
            if request_type == "Other Medication"
            else "Upload a readable PA PDF first."
        )
        st.stop()

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()

    if request_type == "Other Medication":
        if not selected_medication:
            st.error("Search for and select the requested medication first.")
            st.stop()
        if not payer.strip():
            st.error("Enter the patient's insurance payer and plan first.")
            st.stop()
        instructions = f"{MEDICATION_RULES}\n\n{MEDICATION_OUTPUT_FORMAT}"
        analysis_input = f"""
REQUESTED MEDICATION: {selected_medication}
REQUESTED DOSE / FORMULATION: {dose_formulation.strip() or "Not provided"}
PAYER / PLAN: {payer.strip()}

USER'S QUESTIONS OR SPECIAL INSTRUCTIONS:
{initial_request.strip() or "No additional instructions provided"}

UPLOADED PROVIDER NOTE:
{document_text}
""".strip()
    else:
        request_prompt = TMS_PROMPT if request_type == "TMS" else SPRAVATO_PROMPT
        instructions = f"{BASE_RULES}\n\n{request_prompt}\n\n{OUTPUT_FORMAT}"
        analysis_input = f"""
USER'S QUESTIONS OR SPECIAL INSTRUCTIONS:
{initial_request.strip() or "No additional instructions provided"}

UPLOADED PA DOCUMENT:
{document_text}
""".strip()

    client = OpenAI(api_key=OPENAI_API_KEY)

    with st.spinner("Analyzing prior authorization..."):
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=with_web_research(instructions),
                input=analysis_input,
                tools=WEB_SEARCH_TOOLS,
            )
            report = response.output_text
        except Exception as exc:
            st.error(f"OpenAI request failed: {exc}")
            st.stop()

    st.session_state["pa_request_type"] = request_type
    st.session_state["pa_document_text"] = document_text
    st.session_state["pa_report"] = report
    st.session_state["pa_filename"] = uploaded.name
    st.session_state["pa_medication"] = selected_medication
    st.session_state["pa_payer"] = payer.strip()
    st.session_state["pa_dose_formulation"] = dose_formulation.strip()
    st.session_state["pa_initial_request"] = initial_request.strip()
    st.session_state["pa_followup_messages"] = []


if st.session_state.get("pa_report"):
    report = st.session_state["pa_report"]

    st.divider()
    st.subheader("Detailed PA review")

    st.markdown(report)

    st.download_button(
        "Download PA review",
        data=report,
        file_name=(
            "trimera_medication_pa_review.txt"
            if st.session_state.get("pa_request_type") == "Other Medication"
            else "trimera_trd_pa_review.txt"
        ),
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

    st.caption("Trimera automatically checks current authoritative payer and clinical sources when relevant and cites web-derived information.")
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

REQUESTED MEDICATION:
{st.session_state.get("pa_medication", "")}

REQUESTED DOSE / FORMULATION:
{st.session_state.get("pa_dose_formulation", "")}

PAYER / PLAN:
{st.session_state.get("pa_payer", "")}

ORIGINAL QUESTIONS OR SPECIAL INSTRUCTIONS:
{st.session_state.get("pa_initial_request", "") or "None"}

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
                        instructions=with_web_research(
                            MEDICATION_FOLLOWUP_PROMPT
                            if st.session_state.get("pa_request_type") == "Other Medication"
                            else FOLLOWUP_PROMPT
                        ),
                        input=followup_context,
                        tools=WEB_SEARCH_TOOLS,
                    )
                    answer = response.output_text
                    st.markdown(answer)
                except Exception as exc:
                    st.error(f"OpenAI request failed: {exc}")
                    st.stop()

        st.session_state["pa_followup_messages"].append(
            {"role": "assistant", "content": answer}
        )
