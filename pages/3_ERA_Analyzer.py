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


def password_gate() -> None:
    """Use the same password and login session as the other Trimera tools."""
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
    """Extract selectable text from every page of an uploaded PDF."""
    reader = PdfReader(uploaded_file)
    pages: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"[PAGE {page_number}]\n{text}")

    return "\n\n".join(pages).strip()


ANALYSIS_PROMPT = """
You are Trimera ERA Analyzer, an experienced outpatient behavioral-health
billing and payment analyst.

Analyze the uploaded remittance, Availity claim-detail report, ERA, or payer
payment document.

Important rules:
- Use only information present in the uploaded document.
- Never invent missing claim facts, codes, payer rules, or payment amounts.
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
- When the document alone is insufficient, state exactly what additional
  item should be reviewed, such as the 837P, clinical note, authorization,
  eligibility response, payer policy, or provider enrollment.
- Do not guarantee that an appeal or corrected claim will succeed.
- Prioritize actionable and financially meaningful items.
- Preserve patient names when present because this is an internal work tool,
  but do not repeat DOB, member ID, or other identifiers unless operationally
  necessary.
- Be concise enough for a biller to review quickly.

Return the report in this exact structure:

# ERA Analysis

## Claim Summary
- Payer:
- Insurance or plan type:
- Patient:
- Date(s) of service:
- Claim number:
- Billing provider:
- Rendering provider:
- Claim status:
- Total billed:
- Total paid:
- Patient responsibility:
- Total contractual or ineligible adjustment:
- Estimated unpaid provider amount:
- Overall classification:

## Line-Level Analysis

Create a Markdown table with one row for each CPT/HCPCS line:

| DOS | CPT/HCPCS | Modifier | Units | ICD-10 | Billed | Paid | Adjustment/Ineligible | Patient Responsibility | Remark Codes | Classification |
|---|---|---|---:|---|---:|---:|---:|---:|---|---|

## What Happened

Explain the payment outcome in plain English. Clearly distinguish ordinary
fee-schedule reductions from denials, downcoding, bundling, or other adverse
payment actions.

## Codes and Payer Rationale

For every CARC, RARC, payer remark code, status code, or coding edit:
- Code
- Plain-English meaning
- How it affected this claim
- Whether further investigation is needed

## Potential Issues

List only meaningful issues. Examples include:
- Downcoding
- Missing or invalid claim information
- Modifier issue
- Authorization issue
- Eligibility or coordination-of-benefits issue
- Provider enrollment, NPI, or taxonomy issue
- Incorrect patient responsibility
- Underpayment
- Duplicate claim
- Bundling
- No clear issue identified

## Recommended Next Actions

Provide a numbered worklist. For each action include:
- Priority: HIGH, MEDIUM, or LOW
- Action
- Why
- What document or system to review next

## Appeal or Correction Assessment

- Recommended path: No action | Verify posting | Correct and resubmit |
  Appeal | Contact payer | Review 837P | More information needed
- Rationale:
- Confidence: 0-100%

## Draft Internal Billing Note

Write a concise note Crystal can paste into the billing tracker.

## Optional Support Message

When the facts support it, draft a concise technical message to the payer,
DrChrono, or clearinghouse. If no outside message is presently appropriate,
state that no message is recommended until the identified records are reviewed.
""".strip()


password_gate()

with st.sidebar:
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()

    st.write(f"Model: `{MODEL}`")
    st.info("Upload the complete payer document for the best analysis.")


st.title("💳 ERA Analyzer")
st.caption(
    "Upload an ERA or Availity claim-detail PDF to explain payments, "
    "adjustments, denial codes, downcoding, and recommended follow-up."
)

st.warning(
    "Prototype environment: use fictional or fully de-identified documents "
    "until all required BAAs and production safeguards are active."
)

uploaded_file = st.file_uploader(
    "Upload ERA or claim-detail PDF",
    type=["pdf"],
)

era_text = ""

if uploaded_file is not None:
    try:
        era_text = extract_pdf(uploaded_file)

        if not era_text:
            st.error(
                "No selectable text was found. This may be an image-only PDF."
            )
        else:
            st.success(
                f"PDF read successfully: {len(era_text):,} characters extracted."
            )

            with st.expander("Preview extracted text"):
                st.text(era_text[:12000])

    except Exception as exc:
        st.error(f"Could not read the PDF: {exc}")


if st.button(
    "Analyze ERA",
    type="primary",
    use_container_width=True,
):
    if not era_text:
        st.error("Upload a readable PDF first.")
        st.stop()

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_input = f"""
UPLOADED ERA OR CLAIM-DETAIL DOCUMENT:

{era_text}
""".strip()

    with st.spinner("Analyzing payment and denial information..."):
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

    st.success("Analysis complete")
    st.markdown(result)

    st.download_button(
        "Download ERA analysis",
        data=result,
        file_name="trimera_era_analysis.md",
        mime="text/markdown",
        use_container_width=True,
    )
