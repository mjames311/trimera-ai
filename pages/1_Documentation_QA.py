import os
import re
from pathlib import Path
from typing import List, Tuple

import streamlit as st
from docx import Document
from openai import OpenAI
from pypdf import PdfReader


st.set_page_config(
    page_title="Trimera Documentation QA",
    page_icon="📋",
    layout="wide",
)

APP_TITLE = "Trimera Documentation QA"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MANUAL_PATH = Path(
    os.getenv(
        "TRIMERA_MANUAL_PATH",
        "Trimera_Documentation_Coding_Standards_Manual.docx",
    )
)

CORE_PROMPT = """
You are Trimera Documentation QA, an experienced outpatient psychiatry
documentation auditor.

Determine only whether a completed clinical note adequately supports the
CPT/HCPCS codes the provider intends to bill. Use the supplied Trimera
Documentation & Coding Standards excerpts as the governing knowledge base.

Rules:
- Evaluate only the completed note and only the intended codes.
- Do not recommend alternative codes, upcoding, downcoding, diagnoses,
  medications, or treatment.
- Do not rewrite the note.
- Never invent facts or infer undocumented work.
- Distinguish true billing deficiencies from documentation-quality
  improvements.
- A deficiency must materially weaken support for an intended code.
- Apply payer-specific rules only when a payer is supplied and the manual
  contains a payer-specific rule.
- Do not guarantee payment or audit success.
- Keep the report readable in under 30 seconds.
- For supported codes, use no more than two concise sentences.
- Overall risk and confidence must be logically consistent with code-level
  findings.

Return only this format:

TRIMERA DOCUMENTATION QA

Provider Intended Billing:
[list codes and units]

Payer:
[payer or Not specified]

Overall Result:
PASS | REVIEW RECOMMENDED | CORRECTION REQUIRED

Documentation Confidence:
[0-100]%

Overall Audit Risk:
LOW | MEDIUM | HIGH

================================================================

For each intended code:

[CODE / UNITS] — SUPPORTED | BORDERLINE | NOT SUPPORTED

Support:
[One or two concise sentences.]

If BORDERLINE or NOT SUPPORTED, add:
Documentation Deficiencies:
- [Only material deficiencies.]

Audit Risk:
LOW | MEDIUM | HIGH

================================================================

Documentation Quality Improvements

- [Maximum three meaningful non-billing issues.]
or
None identified.

================================================================

Final Assessment

[Maximum two concise sentences.]
""".strip()

FOLLOWUP_PROMPT = """
You are Ask Trimera inside the Documentation QA module.

You are given:
1. The completed clinical note.
2. The provider's intended billing.
3. The payer.
4. The original Documentation QA report.
5. The user's follow-up question.

Answer questions about that specific QA review.

Rules:
- Base the answer on the supplied note, intended billing, payer, QA report,
  and the governing documentation excerpts already used in the review.
- Never invent facts or claim that undocumented work occurred.
- Clearly distinguish what is documented from what is missing.
- Do not guarantee payment, audit success, or payer acceptance.
- Do not recommend upcoding.
- You may explain why a code was supported, borderline, or unsupported.
- You may identify the exact documentation gap.
- You may draft concise provider education or an internal billing note when
  asked.
- Keep answers practical and concise.
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


@st.cache_data(show_spinner=False)
def read_manual(path_str: str) -> str:
    path = Path(path_str)

    if not path.exists():
        raise FileNotFoundError(f"Manual not found: {path.resolve()}")

    doc = Document(path)

    return "\n".join(
        paragraph.text.strip()
        for paragraph in doc.paragraphs
        if paragraph.text.strip()
    )


@st.cache_data(show_spinner=False)
def split_manual(text: str) -> List[Tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[tuple[str, str]] = []
    title = "Manual introduction"
    buffer: list[str] = []

    heading_re = re.compile(
        r"^(Chapter\s+\d+|Appendix\s+[A-Z]|(?:\d+\.)+\d*\s+|"
        r"[A-Z]{2,5}-\d+(?:\.\d+)?)",
        re.I,
    )

    for line in lines:
        if heading_re.match(line) and buffer:
            chunks.append((title, "\n".join(buffer)))
            title = line
            buffer = [line]
        else:
            if not buffer:
                title = line[:120]
            buffer.append(line)

    if buffer:
        chunks.append((title, "\n".join(buffer)))

    return chunks


def relevant_excerpts(
    chunks: List[Tuple[str, str]],
    codes: list[str],
    payer: str,
    limit: int = 12,
) -> str:
    terms = {code.upper().strip() for code in codes}

    for code in list(terms):
        if code in {
            "99212",
            "99213",
            "99214",
            "99215",
            "99202",
            "99203",
            "99204",
            "99205",
        }:
            terms.update(
                {
                    "medical decision making",
                    "mdm",
                    "problems addressed",
                    "data reviewed",
                    "risk",
                    "time-based",
                }
            )

        if code in {"90833", "90836", "90838"}:
            terms.update({"psychotherapy", "separate", "time"})

        if code == "G2211":
            terms.update({"g2211", "longitudinal"})

        if code == "99417":
            terms.update({"99417", "prolonged", "total time"})

        if code == "90867":
            terms.update({"90867", "tms", "motor threshold", "mapping"})

        if code == "96127":
            terms.update({"96127", "rating scale"})

    if payer and payer != "Not specified":
        terms.add(payer.lower())

    scored: list[tuple[int, str, str]] = []

    for title, body in chunks:
        haystack = f"{title}\n{body}".lower()
        score = sum(haystack.count(term.lower()) for term in terms)

        if "authority hierarchy" in haystack:
            score += 3

        if "master decision logic" in haystack:
            score += 3

        if score > 0:
            scored.append((score, title, body))

    scored.sort(reverse=True, key=lambda item: item[0])

    selected = scored[:limit] or [
        (0, title, body)
        for title, body in chunks[:6]
    ]

    return "\n\n---\n\n".join(
        f"[{title}]\n{body}"
        for _, title, body in selected
    )


def extract_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)

    return "\n\n".join(
        f"[Page {page_number}]\n{page.extract_text() or ''}"
        for page_number, page in enumerate(reader.pages, start=1)
    )


def parse_codes(raw: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[\n,;]+", raw)
        if item.strip()
    ]


def reset_qa_session() -> None:
    keys_to_clear = [
        "qa_result",
        "qa_note_text",
        "qa_codes",
        "qa_payer",
        "qa_excerpts",
        "qa_followup_messages",
    ]

    for key in keys_to_clear:
        st.session_state.pop(key, None)


password_gate()

with st.sidebar:
    if st.button("Start new QA review", use_container_width=True):
        reset_qa_session()
        st.rerun()

    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.write(f"Model: `{MODEL}`")
    st.info("The API key remains server-side.")


st.title("📋 Trimera Documentation QA")
st.caption(
    "Review whether a completed note supports the provider's intended billing."
)

try:
    manual_chunks = split_manual(read_manual(str(MANUAL_PATH)))
except Exception as exc:
    st.error(str(exc))
    st.stop()


payer = st.selectbox(
    "Payer",
    [
        "Not specified",
        "Medicare",
        "UnitedHealthcare / Optum",
        "BCBS",
        "Aetna",
        "Cigna",
        "Humana",
        "Other",
    ],
)

codes_raw = st.text_input(
    "Intended billing",
    placeholder="99214, 90833, G2211  OR  99215, 99417 x5",
)

method = st.radio(
    "Clinical note",
    ["Paste text", "Upload PDF"],
    horizontal=True,
)

note_text = ""

if method == "Paste text":
    note_text = st.text_area(
        "Paste completed note",
        height=360,
    )
else:
    uploaded = st.file_uploader(
        "Upload completed note PDF",
        type=["pdf"],
    )

    if uploaded:
        try:
            note_text = extract_pdf(uploaded)
            st.success("PDF text extracted.")
        except Exception as exc:
            st.error(f"Could not read PDF: {exc}")


if st.button(
    "Run documentation QA",
    type="primary",
    use_container_width=True,
):
    codes = parse_codes(codes_raw)

    if not codes:
        st.error("Enter at least one intended code.")
        st.stop()

    if not note_text.strip():
        st.error("Paste or upload a note.")
        st.stop()

    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()

    excerpts = relevant_excerpts(
        manual_chunks,
        codes,
        payer,
    )

    user_content = f"""
INTENDED BILLING:
{chr(10).join(codes)}

PAYER:
{payer}

RELEVANT MANUAL EXCERPTS:
{excerpts}

COMPLETED CLINICAL NOTE:
{note_text}
""".strip()

    client = OpenAI(api_key=OPENAI_API_KEY)

    with st.spinner("Reviewing documentation..."):
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=CORE_PROMPT,
                input=user_content,
            )
            result = response.output_text
        except Exception as exc:
            st.error(f"OpenAI request failed: {exc}")
            st.stop()

    st.session_state["qa_result"] = result
    st.session_state["qa_note_text"] = note_text
    st.session_state["qa_codes"] = codes
    st.session_state["qa_payer"] = payer
    st.session_state["qa_excerpts"] = excerpts
    st.session_state["qa_followup_messages"] = []


if st.session_state.get("qa_result"):
    result = st.session_state["qa_result"]

    st.divider()
    st.subheader("QA result")
    st.text_area(
        "Report",
        value=result,
        height=620,
    )

    st.download_button(
        "Download report",
        data=result,
        file_name="trimera_documentation_qa.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.divider()
    st.subheader("💬 Ask Trimera about this QA review")
    st.caption(
        "Ask why a code was supported, what documentation is missing, "
        "or request a concise provider education note."
    )

    if "qa_followup_messages" not in st.session_state:
        st.session_state["qa_followup_messages"] = []

    for message in st.session_state["qa_followup_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    followup_question = st.chat_input(
        "Ask a follow-up about this documentation review..."
    )

    if followup_question:
        st.session_state["qa_followup_messages"].append(
            {
                "role": "user",
                "content": followup_question,
            }
        )

        with st.chat_message("user"):
            st.markdown(followup_question)

        conversation = "\n\n".join(
            f"{message['role'].upper()}:\n{message['content']}"
            for message in st.session_state["qa_followup_messages"]
        )

        followup_context = f"""
PROVIDER INTENDED BILLING:
{chr(10).join(st.session_state["qa_codes"])}

PAYER:
{st.session_state["qa_payer"]}

ORIGINAL QA REPORT:
{st.session_state["qa_result"]}

RELEVANT MANUAL EXCERPTS:
{st.session_state["qa_excerpts"]}

COMPLETED CLINICAL NOTE:
{st.session_state["qa_note_text"]}

FOLLOW-UP CONVERSATION:
{conversation}
""".strip()

        client = OpenAI(api_key=OPENAI_API_KEY)

        with st.chat_message("assistant"):
            with st.spinner("Reviewing the QA context..."):
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

        st.session_state["qa_followup_messages"].append(
            {
                "role": "assistant",
                "content": answer,
            }
        )
