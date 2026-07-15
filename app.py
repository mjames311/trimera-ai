import os
import re
from pathlib import Path
from typing import List, Tuple

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from docx import Document

load_dotenv()
APP_TITLE = "Trimera Documentation QA"
MANUAL_PATH = Path(os.getenv("TRIMERA_MANUAL_PATH", "Trimera_Documentation_Coding_Standards_Manual.docx"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")

CORE_PROMPT = '''
You are Trimera Documentation QA, an experienced outpatient psychiatry documentation auditor.

Determine only whether a completed clinical note adequately supports the CPT/HCPCS codes the provider intends to bill. Use the supplied Trimera Documentation & Coding Standards excerpts as the governing knowledge base.

Rules:
- Evaluate only the completed note and only the intended codes.
- Do not recommend alternative codes, upcoding, downcoding, diagnoses, medications, or treatment.
- Do not rewrite the note.
- Never invent facts or infer undocumented work.
- Distinguish true billing deficiencies from documentation-quality improvements.
- A deficiency must materially weaken support for an intended code.
- Apply payer-specific rules only when a payer is supplied and the manual contains a payer-specific rule.
- Do not guarantee payment or audit success.
- Keep the report readable in under 30 seconds.
- For supported codes, use no more than two concise sentences.
- Overall risk and confidence must be logically consistent with code-level findings.

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
'''.strip()


def password_gate() -> None:
    if not TEST_PASSWORD:
        st.warning("Set TRIMERA_QA_PASSWORD in your .env file.")
        st.stop()
    if st.session_state.get("authenticated"):
        return
    st.title(APP_TITLE)
    st.caption("Internal test environment — fictional or fully de-identified notes only.")
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
    return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())


@st.cache_data(show_spinner=False)
def split_manual(text: str) -> List[Tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks = []
    title = "Manual introduction"
    buffer = []
    heading_re = re.compile(r"^(Chapter\s+\d+|Appendix\s+[A-Z]|(?:\d+\.)+\d*\s+|[A-Z]{2,5}-\d+(?:\.\d+)?)", re.I)
    for line in lines:
        if heading_re.match(line) and buffer:
            chunks.append((title, "\n".join(buffer)))
            title, buffer = line, [line]
        else:
            if not buffer:
                title = line[:120]
            buffer.append(line)
    if buffer:
        chunks.append((title, "\n".join(buffer)))
    return chunks


def relevant_excerpts(chunks, codes, payer, limit=12):
    terms = set(c.upper().strip() for c in codes)
    for c in list(terms):
        if c in {"99212","99213","99214","99215","99202","99203","99204","99205"}:
            terms.update({"medical decision making","mdm","problems addressed","data reviewed","risk","time-based"})
        if c in {"90833","90836","90838"}:
            terms.update({"psychotherapy","separate","time"})
        if c == "G2211": terms.update({"g2211","longitudinal"})
        if c == "99417": terms.update({"99417","prolonged","total time"})
        if c == "90867": terms.update({"90867","tms","motor threshold","mapping"})
        if c == "96127": terms.update({"96127","rating scale"})
    if payer and payer != "Not specified": terms.add(payer.lower())
    scored = []
    for title, body in chunks:
        hay = (title + "\n" + body).lower()
        score = sum(hay.count(t.lower()) for t in terms)
        if "authority hierarchy" in hay or "master decision logic" in hay: score += 3
        if score > 0: scored.append((score, title, body))
    scored.sort(reverse=True, key=lambda x: x[0])
    selected = scored[:limit] or [(0, t, b) for t, b in chunks[:6]]
    return "\n\n---\n\n".join(f"[{t}]\n{b}" for _, t, b in selected)


def extract_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    return "\n\n".join(f"[Page {i}]\n{page.extract_text() or ''}" for i, page in enumerate(reader.pages, 1))


def parse_codes(raw):
    return [p.strip() for p in re.split(r"[\n,;]+", raw) if p.strip()]


password_gate()
st.title(APP_TITLE)
st.caption("Prototype: fictional or fully de-identified notes only until all BAAs and production safeguards are active.")

with st.sidebar:
    if st.button("Sign out"):
        st.session_state.clear(); st.rerun()
    st.write(f"Model: `{MODEL}`")
    st.info("The API key stays in the server-side .env file.")

try:
    manual_chunks = split_manual(read_manual(str(MANUAL_PATH)))
except Exception as exc:
    st.error(str(exc)); st.stop()

payer = st.selectbox("Payer", ["Not specified","Medicare","UnitedHealthcare / Optum","BCBS","Aetna","Cigna","Humana","Other"])
codes_raw = st.text_input("Intended billing", placeholder="99214, 90833, G2211  OR  99215, 99417 x5")
method = st.radio("Clinical note", ["Paste text","Upload PDF"], horizontal=True)
note_text = ""
if method == "Paste text":
    note_text = st.text_area("Paste completed note", height=360)
else:
    uploaded = st.file_uploader("Upload completed note PDF", type=["pdf"])
    if uploaded:
        try: note_text = extract_pdf(uploaded); st.success("PDF text extracted.")
        except Exception as exc: st.error(f"Could not read PDF: {exc}")

if st.button("Run documentation QA", type="primary", use_container_width=True):
    codes = parse_codes(codes_raw)
    if not codes: st.error("Enter at least one intended code."); st.stop()
    if not note_text.strip(): st.error("Paste or upload a note."); st.stop()
    excerpts = relevant_excerpts(manual_chunks, codes, payer)
    user_content = f"INTENDED BILLING:\n{chr(10).join(codes)}\n\nPAYER:\n{payer}\n\nRELEVANT MANUAL EXCERPTS:\n{excerpts}\n\nCOMPLETED CLINICAL NOTE:\n{note_text}"
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    with st.spinner("Reviewing documentation..."):
        try:
            response = client.responses.create(model=MODEL, instructions=CORE_PROMPT, input=user_content)
            result = response.output_text
        except Exception as exc:
            st.error(f"OpenAI request failed: {exc}"); st.stop()
    st.subheader("QA result")
    st.text_area("Report", value=result, height=620)
    st.download_button("Download report", data=result, file_name="trimera_documentation_qa.txt", mime="text/plain", use_container_width=True)
