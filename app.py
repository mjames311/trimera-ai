import os
import re
from pathlib import Path
from typing import List, Tuple

import streamlit as st
from theme import apply_trimera_theme, page_header, render_topbar, sidebar_label, sidebar_model, sidebar_reminder
st.set_page_config(

    page_title="Trimera AI Suite",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_trimera_theme()
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


render_topbar()
page_header(
    "⌂",
    "Home",
    "Clinical intelligence and practice operations tools for Trimera Health.",
)

with st.sidebar:
    sidebar_label("Quick actions")
    if st.button("Sign out"):
        st.session_state.clear(); st.rerun()
    sidebar_model(MODEL)
    sidebar_reminder("Secure environment", "The API key remains server-side.")

st.markdown(
    """
    <p class="trimera-home-intro">
      Trimera AI brings clinical documentation, payer review, billing analysis,
      medication safety, and general practice intelligence into one secure internal workspace.
      Choose a tool below based on the task you need to complete.
    </p>
    <div class="trimera-section-title">Available tools</div>
    <div class="trimera-tool-grid">
      <a class="trimera-tool-card" href="/Documentation_QA">
        <div class="trimera-tool-icon">▣</div><div class="trimera-tool-name">Documentation QA</div>
        <div class="trimera-tool-description">Checks whether a completed note supports the intended billing using extracted facts, fixed coding rules, and governing references.</div>
      </a>
      <a class="trimera-tool-card" href="/PA_Extractor">
        <div class="trimera-tool-icon">♙</div><div class="trimera-tool-name">Prior Authorization Assistant</div>
        <div class="trimera-tool-description">Reviews TMS and Spravato authorization documents for requirements, missing information, and next steps.</div>
      </a>
      <a class="trimera-tool-card" href="/ERA_Analyzer">
        <div class="trimera-tool-icon">⌁</div><div class="trimera-tool-name">ERA Analyzer</div>
        <div class="trimera-tool-description">Analyzes ERA, remittance, and claim-detail files to clarify payments, denials, adjustments, and follow-up actions.</div>
      </a>
      <a class="trimera-tool-card" href="/Ask_Trimera">
        <div class="trimera-tool-icon">▤</div><div class="trimera-tool-name">Ask Trimera</div>
        <div class="trimera-tool-description">Answers general operational questions, analyzes attached files, and automatically researches reputable current sources when useful.</div>
      </a>
      <a class="trimera-tool-card" href="/BCBS_Appeal_Builder">
        <div class="trimera-tool-icon">♢</div><div class="trimera-tool-name">BCBS Appeal Builder</div>
        <div class="trimera-tool-description">Matches downcoded claims to encounter notes, builds appeal packets, and prepares tracker updates.</div>
      </a>
      <a class="trimera-tool-card" href="/Medication_Interaction_Review">
        <div class="trimera-tool-icon">♧</div><div class="trimera-tool-name">Medication Interaction Review</div>
        <div class="trimera-tool-description">Extracts the current medication list and reviews interactions, safety concerns, monitoring needs, and follow-up questions.</div>
      </a>
    </div>
    <div class="trimera-section-title">How answers are grounded</div>
    <div class="trimera-source-grid">
      <div class="trimera-source-card"><strong>Authoritative reference library</strong><span>Where applicable, tools use embedded CMS and Medicare guidance, AMA coding guidance, payer medical policies, TMS and Spravato criteria, and Trimera documentation standards.</span></div>
      <div class="trimera-source-card"><strong>Your uploaded records</strong><span>Clinical notes, authorization documents, ERA files, remittance reports, trackers, and other attachments provide the case-specific facts used in each review.</span></div>
      <div class="trimera-source-card"><strong>Fixed rules and safeguards</strong><span>Documentation QA uses deterministic code-level rules after fact extraction. The AI does not independently change billing outcomes or invent undocumented facts.</span></div>
      <div class="trimera-source-card"><strong>Automatic current web research</strong><span>Analytical and conversational tools can automatically research current reputable sources when embedded or uploaded guidance does not fully resolve a question. Web-derived claims are identified and cited.</span></div>
    </div>
    <div class="trimera-home-note"><strong>Access and safeguards:</strong> Home is available without a password. One sign-in unlocks all protected tools for the current app session and expires after 30 minutes of inactivity. Uploaded records remain the sole source of patient-specific facts; external research adds current context but does not invent missing documentation, override fixed QA findings, or replace professional review.</div>
    """,
    unsafe_allow_html=True,
)
