import os
from typing import Any

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader


st.set_page_config(
    page_title="ERA Analyzer",
    page_icon="💳",
    layout="wide",
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

MAX_FILES = 20
MAX_TOTAL_CHARACTERS = 220000


ANALYSIS_PROMPT = """
You are Trimera ERA Analyzer, an experienced outpatient behavioral-health
billing and payment analyst.

The user may upload one or multiple remittance documents, Availity claim-detail
reports, ERAs, payer letters, or related claim records.

Analyze the complete document packet together.

Important rules:
- Use only information present in the uploaded documents.
- Never invent missing claim facts, codes, payer rules, payment amounts, or
  relationships between documents.
- Preserve the source filename for material findings whenever possible.
- When multiple documents concern the same claim, synthesize them into one
  consolidated claim analysis.
- When documents concern different claims, keep the claims separate.
- Identify duplicate records and do not double-count billed, paid, adjusted,
  denied, or patient-responsibility amounts.
- Identify conflicts between documents and state which source contains each
  conflicting value.
- Do not label normal contractual write-offs as denials.
- Distinguish among:
  1. Paid correctly or apparently paid correctly
  2. Paid with contractual adjustment
  3. Paid but reduced or downcoded
  4. Fully denied
  5. Partially denied
  6. Patient responsibility
  7. Pending or unclear
- Explain CARC, RARC, payer remark codes, and payer-specific edit codes in
  plain English when their meaning is supplied or reliably identifiable.
- When the documents are insufficient, state exactly what additional item
  should be reviewed, such as the 837P, clinical note, authorization,
  eligibility response, payer policy, or provider enrollment.
- Do not guarantee that an appeal or corrected claim will succeed.
- Prioritize actionable and financially meaningful items.
- Preserve patient names when present because this is an internal work tool,
  but do not repeat DOB, member ID, or other identifiers unless operationally
  necessary.
- Be concise enough for a biller to review quickly.

Return the report in this structure:

# ERA Packet Analysis

## Packet Summary
- Number of source files:
- Source files:
- Number of distinct claims identified:
- Number of distinct patients identified:
- Payer(s):
- Total billed across unique claims:
- Total paid across unique claims:
- Total patient responsibility:
- Total contractual adjustment:
- Estimated unpaid provider amount:
- Duplicate records identified:
- Conflicts identified:
- Overall packet classification:

## Claim-by-Claim Summary

Create one subsection for every distinct claim.

### Claim: [claim number or best available identifier]

- Source file(s):
- Payer:
- Patient:
- Date(s) of service:
- Billing provider:
- Rendering provider:
- Claim status:
- Total billed:
- Total paid:
- Patient responsibility:
- Contractual adjustment:
- Estimated unpaid provider amount:
- Overall classification:

#### Line-Level Analysis

Create a valid Markdown table with one row for each CPT/HCPCS line:

| Source | DOS | CPT/HCPCS | Modifier | Units | ICD-10 | Billed | Paid | Adjustment/Ineligible | Patient Responsibility | Remark Codes | Classification |
|---|---|---|---|---:|---|---:|---:|---:|---:|---|---|

#### What Happened

Explain the payment outcome in plain English. Clearly distinguish ordinary
fee-schedule reductions from denials, downcoding, bundling, or other adverse
payment actions.

#### Codes and Payer Rationale

For every CARC, RARC, payer remark code, status code, or coding edit:
- Code
- Plain-English meaning
- How it affected this claim
- Whether further investigation is needed

#### Potential Issues

List only meaningful issues.

#### Recommended Next Actions

Provide a numbered worklist. For each action include:
- Priority: HIGH, MEDIUM, or LOW
- Action
- Why
- What document or system to review next

#### Appeal or Correction Assessment

- Recommended path: No action | Verify posting | Correct and resubmit |
  Appeal | Contact payer | Review 837P | More information needed
- Rationale:
- Confidence: 0-100%

#### Draft Internal Billing Note

Write a concise note Crystal can paste into the billing tracker.

## Cross-Document Findings

Include only when applicable:
- Duplicate documents or duplicate claim lines
- Conflicting payment or status information
- Claims that appear related
- Patterns across claims, payers, CPT codes, or denial reasons
- Highest-priority financial items

## Optional Support Message

When the facts support it, draft a concise technical message to the payer,
DrChrono, or clearinghouse. If no outside message is presently appropriate,
state that no message is recommended until the identified records are reviewed.
""".strip()


FOLLOWUP_PROMPT = """
You are Ask Trimera inside the ERA Analyzer.

You are given:
1. The complete text from every uploaded ERA or claim-detail document.
2. The original consolidated ERA packet analysis.
3. The user's follow-up conversation.

Answer questions about this specific document packet.

Rules:
- Use only the supplied documents and analysis for claim-specific facts.
- Never invent patient details, codes, payment amounts, denial reasons,
  payer rules, or claim status.
- Identify the source filename when answering about a specific fact.
- Do not double-count duplicate documents or repeated claim lines.
- Clearly distinguish contractual adjustments from denials.
- Clearly distinguish facts in the documents from reasonable next-step
  suggestions.
- You may compare documents, identify conflicts, explain CARC/RARC codes,
  summarize payment reductions, identify downcoding or bundling, calculate
  totals from the supplied records, and draft billing notes, payer messages,
  corrected-claim checklists, or appeal outlines.
- Do not guarantee payment or appeal success.
- Keep responses concise and operationally useful.
""".strip()


def password_gate() -> None:
    if not TEST_PASSWORD:
        st.warning("TRIMERA_QA_PASSWORD is not configured.")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("Trimera ERA Analyzer")
    st.caption("Internal Trimera Health billing tool")

    entered = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        if entered == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


def extract_pdf(uploaded_file: Any) -> str:
    reader = PdfReader(uploaded_file)
    pages: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"[PAGE {page_number}]\n{text}")

    return "\n\n".join(pages).strip()


def reset_era_session() -> None:
    for key in [
        "era_packet_text",
        "era_result",
        "era_filenames",
        "era_followup_messages",
    ]:
        st.session_state.pop(key, None)


password_gate()

with st.sidebar:
    if st.button("Start new ERA review", use_container_width=True):
        reset_era_session()
        st.rerun()

    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.write(f"Model: `{MODEL}`")
    st.info("Upload related payer documents together for a consolidated review.")


st.title("💳 ERA Analyzer")
st.caption(
    "Upload one or multiple ERA, remittance, or claim-detail PDFs. "
    "The analyzer will synthesize related records and keep unrelated claims separate."
)

st.warning(
    "Prototype environment: use fictional or fully de-identified documents "
    "until all required BAAs and production safeguards are active."
)

uploaded_files = st.file_uploader(
    "Upload ERA or claim-detail PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

packet_parts: list[str] = []
file_summaries: list[dict] = []
read_errors: list[str] = []

if uploaded_files:
    if len(uploaded_files) > MAX_FILES:
        st.error(f"Upload no more than {MAX_FILES} files at one time.")
        st.stop()

    for uploaded_file in uploaded_files:
        try:
            extracted_text = extract_pdf(uploaded_file)

            if not extracted_text:
                read_errors.append(
                    f"{uploaded_file.name}: no selectable text was found."
                )
                continue

            file_summaries.append(
                {
                    "name": uploaded_file.name,
                    "characters": len(extracted_text),
                }
            )

            packet_parts.append(
                f"""
============================================================
SOURCE FILE: {uploaded_file.name}
============================================================

{extracted_text}
""".strip()
            )

        except Exception as exc:
            read_errors.append(f"{uploaded_file.name}: {exc}")

    total_characters = sum(item["characters"] for item in file_summaries)

    if file_summaries:
        st.success(
            f"{len(file_summaries)} file(s) read successfully — "
            f"{total_characters:,} total characters extracted."
        )

        st.markdown("#### Files included")
        for item in file_summaries:
            st.write(
                f"- **{item['name']}** — {item['characters']:,} characters"
            )

        if total_characters > MAX_TOTAL_CHARACTERS:
            st.error(
                "This packet is too large for one analysis. "
                f"Keep the combined extracted text under approximately "
                f"{MAX_TOTAL_CHARACTERS:,} characters by splitting it into "
                "two related batches."
            )

        with st.expander("Preview extracted packet text"):
            preview = "\n\n".join(packet_parts)
            st.text(preview[:20000])

    if read_errors:
        for error in read_errors:
            st.warning(error)


packet_text = "\n\n".join(packet_parts)
total_characters = len(packet_text)


if st.button(
    "Analyze ERA packet",
    type="primary",
    use_container_width=True,
):
    if not packet_text:
        st.error("Upload at least one readable PDF first.")
        st.stop()

    if total_characters > MAX_TOTAL_CHARACTERS:
        st.error(
            "The combined packet is too large. Split the files into smaller, "
            "related batches and try again."
        )
        st.stop()

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()

    client = OpenAI(api_key=OPENAI_API_KEY)

    filenames = [item["name"] for item in file_summaries]

    user_input = f"""
DOCUMENT PACKET INFORMATION:
- Number of files: {len(filenames)}
- Filenames: {filenames}

UPLOADED ERA OR CLAIM-DETAIL DOCUMENT PACKET:

{packet_text}
""".strip()

    with st.spinner(
        f"Analyzing {len(filenames)} document(s) and matching related claims..."
    ):
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=ANALYSIS_PROMPT,
                input=user_input,
            )
            result = response.output_text
        except Exception as exc:
            st.error(f"OpenAI request failed: {exc}")
            st.stop()

    st.session_state["era_packet_text"] = packet_text
    st.session_state["era_result"] = result
    st.session_state["era_filenames"] = filenames
    st.session_state["era_followup_messages"] = []


if st.session_state.get("era_result"):
    result = st.session_state["era_result"]

    st.divider()
    st.success("Analysis complete")
    st.markdown(result)

    st.download_button(
        "Download ERA packet analysis",
        data=result,
        file_name="trimera_era_packet_analysis.md",
        mime="text/markdown",
        use_container_width=True,
    )

    st.divider()
    st.subheader("💬 Ask Trimera about this ERA packet")
    st.caption(
        "Compare files, ask which claims were denied or reduced, request totals, "
        "or draft a billing note, payer message, or appeal outline."
    )

    if "era_followup_messages" not in st.session_state:
        st.session_state["era_followup_messages"] = []

    for message in st.session_state["era_followup_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    followup_question = st.chat_input(
        "Ask a follow-up about these ERA documents..."
    )

    if followup_question:
        st.session_state["era_followup_messages"].append(
            {
                "role": "user",
                "content": followup_question,
            }
        )

        with st.chat_message("user"):
            st.markdown(followup_question)

        conversation = "\n\n".join(
            f"{message['role'].upper()}:\n{message['content']}"
            for message in st.session_state["era_followup_messages"]
        )

        followup_context = f"""
SOURCE FILES:
{st.session_state.get("era_filenames", [])}

ORIGINAL ERA OR CLAIM-DETAIL DOCUMENT PACKET:
{st.session_state["era_packet_text"]}

ORIGINAL ERA PACKET ANALYSIS:
{st.session_state["era_result"]}

FOLLOW-UP CONVERSATION:
{conversation}
""".strip()

        client = OpenAI(api_key=OPENAI_API_KEY)

        with st.chat_message("assistant"):
            with st.spinner("Reviewing the complete ERA packet..."):
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

        st.session_state["era_followup_messages"].append(
            {
                "role": "assistant",
                "content": answer,
            }
        )
