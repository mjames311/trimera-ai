import json
import os
import re
from pathlib import Path
from typing import Any

import pdfplumber
import streamlit as st
from docx import Document
from openai import OpenAI
from pypdf import PdfReader
from rapidfuzz import fuzz

st.set_page_config(page_title="Trimera Documentation QA", page_icon="📋", layout="wide")

APP_TITLE = "Trimera Documentation QA"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "reference"
MANUAL_PATH = ROOT / "Trimera_Documentation_Coding_Standards_Manual.docx"

REFERENCE_FILES = {
    "AMA": ["2023-e-m-descriptors-guidelines (1).pdf"],
    "CMS": ["mln006764_evaluation_management_services.pdf", "ai.rules.emcodes.docx"],
    "BCBS": ["cpcp051-12-22-2025.pdf"],
    "UNITED_COMMUNITY": ["UHCCP-Evaluation-Management-Policy-(R5007).pdf"],
    "DOWNCODING_RISK": ["OH.PP.066.pdf"],
}

PAYER_AUTHORITY_ORDER = {
    "Medicare": ["CMS", "AMA"],
    "BCBS": ["BCBS", "AMA", "CMS"],
    "UnitedHealthcare Community Plan / Medicaid": ["UNITED_COMMUNITY", "AMA", "CMS"],
    "UnitedHealthcare / Optum Commercial": ["AMA", "CMS"],
    "Aetna": ["AMA", "CMS"],
    "Cigna": ["AMA", "CMS"],
    "Humana": ["AMA", "CMS"],
    "Other": ["AMA", "CMS"],
    "Not specified": ["AMA", "CMS"],
}

MDM_RANK = {"none": 0, "minimal": 0, "straightforward": 0, "low": 1, "moderate": 2, "high": 3, "unclear": -1}
E_M_RULES = {
    "99203": {"mdm": "low", "time": 30, "patient": "new"},
    "99204": {"mdm": "moderate", "time": 45, "patient": "new"},
    "99205": {"mdm": "high", "time": 60, "patient": "new"},
    "99213": {"mdm": "low", "time": 20, "patient": "established"},
    "99214": {"mdm": "moderate", "time": 30, "patient": "established"},
    "99215": {"mdm": "high", "time": 40, "patient": "established"},
}
PSYCHOTHERAPY_RULES = {"90833": 16, "90836": 38, "90838": 53}

FACT_EXTRACTION_PROMPT = """
You are a documentation fact extractor. Do not decide whether any code is supported.
Extract only facts explicitly documented in the completed note.

Return valid JSON only, with no markdown fences, using this exact schema:
{
  "patient_status": "new|established|unclear",
  "total_em_time_minutes": null,
  "time_statement_text": "",
  "em_time_separate_from_other_services": "yes|no|unclear",
  "problems_level": "straightforward|low|moderate|high|unclear",
  "data_level": "minimal|low|moderate|high|unclear",
  "risk_level": "minimal|low|moderate|high|unclear",
  "overall_mdm_level": "straightforward|low|moderate|high|unclear",
  "problems_evidence": [],
  "data_evidence": [],
  "risk_evidence": [],
  "prescription_drug_management": "yes|no|unclear",
  "psychotherapy_separately_identifiable": "yes|no|unclear",
  "psychotherapy_minutes": null,
  "psychotherapy_intervention_documented": "yes|no|unclear",
  "psychotherapy_response_or_progress_documented": "yes|no|unclear",
  "psychotherapy_evidence": [],
  "longitudinal_relationship_documented": "yes|no|unclear",
  "longitudinal_evidence": [],
  "base_em_code_or_level_explicit": "yes|no|unclear",
  "prolonged_time_separately_attributable_to_em": "yes|no|unclear",
  "important_ambiguities": []
}

Rules:
- Use null for an absent number.
- Never infer time from appointment start/end unless the note explicitly attributes that time to the physician/QHP's billable E/M or psychotherapy work.
- Do not count time for another separately reported service as E/M time.
- For MDM, apply the 2-of-3 framework, but extract the level rather than deciding the billed code.
- Prescription drug management may support moderate risk when explicitly documented.
- Keep evidence short and quote or closely paraphrase the note.
""".strip()

EXPLANATION_PROMPT = """
You are Trimera Documentation QA's explanation layer.
The Python rules engine has already determined the code-level outcomes. You may not change those outcomes.

Use the completed note, extracted facts, governing excerpts, and fixed findings to provide concise, useful feedback.
Rules:
- Never override SUPPORTED, BORDERLINE, or NOT SUPPORTED.
- Never invent facts.
- Explain material gaps only.
- Distinguish true billing deficiencies from optional documentation-quality improvements.
- Cite authority using the supplied source label, such as [AMA], [CMS], [BCBS], or [UNITED_COMMUNITY].
- Do not recommend a different code.
- Keep each code explanation to two concise sentences.
- Give no more than three documentation-quality improvements.

Return valid JSON only:
{
  "code_explanations": {"CODE": {"support": "", "deficiencies": []}},
  "quality_improvements": [],
  "final_assessment": ""
}
""".strip()

FOLLOWUP_PROMPT = """
You are Ask Trimera inside the Documentation QA module.
The code-level result was produced by a fixed Python rules engine. Do not change or contradict the fixed result.
Answer using the completed note, intended billing, payer, extracted facts, fixed findings, governing excerpts, and prior follow-up messages.
Never invent facts. Clearly distinguish documented facts from missing items. You may explain a result, identify the exact gap, or draft concise provider education or an internal billing note. Do not guarantee payment or audit success. Keep the answer practical and concise.
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
def read_pdf(path_str: str) -> str:
    path = Path(path_str)
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n\n".join((page.extract_text() or "") for page in pdf.pages)
        if text.strip():
            return text
    except Exception:
        pass
    reader = PdfReader(path)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


@st.cache_data(show_spinner=False)
def read_docx(path_str: str) -> str:
    doc = Document(path_str)
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            values = [cell.text.strip() for cell in row.cells]
            if any(values):
                parts.append(" | ".join(values))
    return "\n".join(parts)


def read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf(str(path))
    if path.suffix.lower() == ".docx":
        return read_docx(str(path))
    return path.read_text(encoding="utf-8", errors="ignore")


def split_text(text: str, source_label: str, chunk_size: int = 5000) -> list[dict]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks, start, index = [], 0, 1
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start, end)
            if boundary > start + 1000:
                end = boundary
        body = text[start:end].strip()
        if body:
            chunks.append({"source": source_label, "chunk": index, "text": body})
            index += 1
        start = max(end, start + 1)
    return chunks


@st.cache_data(show_spinner=False)
def load_reference_library() -> dict[str, list[dict]]:
    library: dict[str, list[dict]] = {}
    for category, filenames in REFERENCE_FILES.items():
        category_chunks = []
        for filename in filenames:
            path = REFERENCE_DIR / filename
            if path.exists():
                category_chunks.extend(split_text(read_document(path), category))
        library[category] = category_chunks
    library["TRIMERA"] = split_text(read_document(MANUAL_PATH), "TRIMERA") if MANUAL_PATH.exists() else []
    return library


def parse_codes(raw: str) -> list[dict]:
    entries = [item.strip() for item in re.split(r"[\n,;]+", raw) if item.strip()]
    parsed = []
    for item in entries:
        match = re.search(r"\b([A-Z]?\d{4,5})\b(?:\s*(?:x|×)\s*(\d+))?", item, re.I)
        if match:
            parsed.append({"raw": item, "code": match.group(1).upper(), "units": int(match.group(2) or 1)})
        else:
            parsed.append({"raw": item, "code": item.upper(), "units": 1})
    return parsed


def query_terms(codes: list[dict], payer: str) -> list[str]:
    terms = set()
    for entry in codes:
        code = entry["code"]
        terms.add(code)
        if code in E_M_RULES:
            terms.update(["medical decision making", "two of three", "problems addressed", "data reviewed", "risk", "total time", "prescription drug management"])
        elif code in PSYCHOTHERAPY_RULES:
            terms.update(["psychotherapy", "separately identifiable", "time", "90833", "90836", "90838"])
        elif code == "G2211":
            terms.update(["G2211", "longitudinal", "continuing focal point"])
        elif code in {"99417", "G2212"}:
            terms.update([code, "prolonged", "total time", "99205", "99215"])
    terms.add(payer)
    return sorted(term for term in terms if term)


def score_chunk(chunk: dict, terms: list[str]) -> float:
    text = chunk["text"].lower()
    score = 0.0
    for term in terms:
        term_lower = term.lower()
        if term_lower in text:
            score += 4 + text.count(term_lower)
        elif fuzz.partial_ratio(term_lower, text[:12000]) >= 90:
            score += 1.5
    return score


def governing_excerpts(library: dict[str, list[dict]], payer: str, codes: list[dict], limit_per_category: int = 5) -> tuple[str, list[str]]:
    order = PAYER_AUTHORITY_ORDER.get(payer, ["AMA", "CMS"]) + ["TRIMERA", "DOWNCODING_RISK"]
    terms = query_terms(codes, payer)
    sections, used_sources = [], []
    for category in order:
        chunks = library.get(category, [])
        ranked = sorted(((score_chunk(chunk, terms), chunk) for chunk in chunks), key=lambda item: item[0], reverse=True)
        selected = [chunk for score, chunk in ranked if score > 0][:limit_per_category]
        if not selected and chunks and category in {"AMA", "CMS"}:
            selected = chunks[:2]
        if selected:
            used_sources.append(category)
            sections.extend(f"[{category} | chunk {chunk['chunk']}]\n{chunk['text']}" for chunk in selected)
    return "\n\n---\n\n".join(sections), used_sources


def extract_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    return "\n\n".join(f"[Page {page_number}]\n{page.extract_text() or ''}" for page_number, page in enumerate(reader.pages, start=1))


def clean_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.I).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def yes(value: Any) -> bool:
    return str(value).strip().lower() == "yes"


def unclear(value: Any) -> bool:
    return str(value).strip().lower() == "unclear"


def calculate_mdm(facts: dict) -> str:
    ranks = sorted([MDM_RANK.get(str(facts.get(key, "unclear")).lower(), -1) for key in ("problems_level", "data_level", "risk_level")], reverse=True)
    if len(ranks) < 2 or ranks[1] < 0:
        return "unclear"
    return {0: "straightforward", 1: "low", 2: "moderate", 3: "high"}[ranks[1]]


def evaluate_em(code: str, facts: dict) -> dict:
    rule = E_M_RULES[code]
    calculated_mdm = calculate_mdm(facts)
    mdm_supported = MDM_RANK.get(calculated_mdm, -1) >= MDM_RANK[rule["mdm"]]
    time_value = facts.get("total_em_time_minutes")
    time_supported = isinstance(time_value, (int, float)) and time_value >= rule["time"] and yes(facts.get("em_time_separate_from_other_services"))
    patient_status = str(facts.get("patient_status", "unclear")).lower()
    patient_match = patient_status == "unclear" or patient_status == rule["patient"]
    if (mdm_supported or time_supported) and patient_match:
        status = "SUPPORTED"
    elif MDM_RANK.get(calculated_mdm, -1) == MDM_RANK[rule["mdm"]] - 1 or (isinstance(time_value, (int, float)) and time_value >= rule["time"] and not yes(facts.get("em_time_separate_from_other_services"))):
        status = "BORDERLINE"
    else:
        status = "NOT SUPPORTED"
    deficiencies = []
    if not mdm_supported and not time_supported:
        deficiencies.append(f"Neither {rule['mdm']} MDM nor clearly attributable {rule['time']}-minute E/M time was established.")
    if not patient_match:
        deficiencies.append(f"The note identifies the patient as {patient_status}, which does not match this {rule['patient']}-patient code.")
    reasons = []
    if mdm_supported:
        reasons.append(f"Calculated MDM is {calculated_mdm}, meeting the {rule['mdm']} requirement.")
    if time_supported:
        reasons.append(f"Documented separate E/M time is {time_value} minutes, meeting the {rule['time']}-minute threshold.")
    return {"status": status, "reasons": reasons, "deficiencies": deficiencies, "calculated_mdm": calculated_mdm}


def evaluate_psychotherapy(code: str, facts: dict) -> dict:
    minimum = PSYCHOTHERAPY_RULES[code]
    minutes = facts.get("psychotherapy_minutes")
    separate = yes(facts.get("psychotherapy_separately_identifiable"))
    intervention = yes(facts.get("psychotherapy_intervention_documented"))
    time_met = isinstance(minutes, (int, float)) and minutes >= minimum
    missing = []
    if not separate:
        missing.append("Psychotherapy was not clearly separately identifiable from E/M.")
    if not intervention:
        missing.append("A specific psychotherapy intervention was not clearly documented.")
    if not time_met:
        missing.append(f"At least {minimum} psychotherapy minutes were not documented.")
    status = "SUPPORTED" if separate and intervention and time_met else "BORDERLINE" if sum([separate, intervention, time_met]) == 2 else "NOT SUPPORTED"
    return {"status": status, "reasons": [f"Separate psychotherapy: {'yes' if separate else 'no/unclear'}; intervention: {'yes' if intervention else 'no/unclear'}; time: {minutes if minutes is not None else 'not documented'}."], "deficiencies": missing}


def evaluate_g2211(facts: dict, payer: str, codes: list[dict]) -> dict:
    base_present = any(entry["code"] in E_M_RULES for entry in codes)
    longitudinal = yes(facts.get("longitudinal_relationship_documented"))
    if payer != "Medicare":
        return {"status": "BORDERLINE", "reasons": ["G2211 is Medicare-specific in the supplied CMS authority."], "deficiencies": ["The selected payer is not Medicare; payer-specific coverage would need confirmation."]}
    if base_present and longitudinal:
        status, deficiencies = "SUPPORTED", []
    elif base_present and unclear(facts.get("longitudinal_relationship_documented")):
        status, deficiencies = "BORDERLINE", ["The ongoing longitudinal relationship was not clearly established."]
    else:
        status, deficiencies = "NOT SUPPORTED", []
        if not base_present:
            deficiencies.append("A qualifying office/outpatient E/M base code is absent.")
        if not longitudinal:
            deficiencies.append("The continuing focal-point or ongoing-care relationship is absent.")
    return {"status": status, "reasons": [f"Qualifying base code present: {'yes' if base_present else 'no'}; longitudinal relationship: {'yes' if longitudinal else 'no/unclear'}."], "deficiencies": deficiencies}


def evaluate_prolonged(code: str, units: int, facts: dict, payer: str, codes: list[dict]) -> dict:
    base_codes = [entry["code"] for entry in codes if entry["code"] in {"99205", "99215"}]
    base = base_codes[0] if base_codes else None
    total_time = facts.get("total_em_time_minutes")
    separate = yes(facts.get("prolonged_time_separately_attributable_to_em"))
    if not base:
        return {"status": "NOT SUPPORTED", "reasons": [], "deficiencies": [f"{code} requires a qualifying 99205 or 99215 base service."]}
    if code == "99417" and payer == "Medicare":
        return {"status": "NOT SUPPORTED", "reasons": [], "deficiencies": ["For Medicare office/outpatient prolonged time, the supplied CMS authority directs use of G2212 rather than 99417."]}
    if code == "G2212" and payer != "Medicare":
        return {"status": "BORDERLINE", "reasons": [], "deficiencies": ["G2212 is Medicare-specific; confirm the selected payer's rule."]}
    first_threshold = (75 if base == "99205" else 55) if code == "99417" else (89 if base == "99205" else 69)
    required_time = first_threshold + max(units - 1, 0) * 15
    time_met = isinstance(total_time, (int, float)) and total_time >= required_time and separate
    if time_met:
        status, deficiencies = "SUPPORTED", []
    elif isinstance(total_time, (int, float)) and total_time >= required_time and not separate:
        status, deficiencies = "BORDERLINE", ["The total time reaches the threshold, but prolonged E/M time is not clearly separated from other reported services."]
    else:
        status, deficiencies = "NOT SUPPORTED", [f"{required_time} minutes of clearly attributable total E/M time were required for {units} unit(s); documented time was {total_time if total_time is not None else 'not stated'}." ]
    return {"status": status, "reasons": [f"Base code: {base}; required total E/M time: {required_time}; documented: {total_time if total_time is not None else 'not stated'}."], "deficiencies": deficiencies}


def evaluate_codes(codes: list[dict], facts: dict, payer: str) -> dict[str, dict]:
    findings = {}
    for entry in codes:
        code, units = entry["code"], entry["units"]
        if code in E_M_RULES:
            finding = evaluate_em(code, facts)
        elif code in PSYCHOTHERAPY_RULES:
            finding = evaluate_psychotherapy(code, facts)
        elif code == "G2211":
            finding = evaluate_g2211(facts, payer, codes)
        elif code in {"99417", "G2212"}:
            finding = evaluate_prolonged(code, units, facts, payer, codes)
        else:
            finding = {"status": "BORDERLINE", "reasons": ["This code is not yet in the deterministic rules engine."], "deficiencies": ["The result requires manual review against the governing excerpts."]}
        finding["units"] = units
        findings[code] = finding
    return findings


def overall_result(findings: dict[str, dict]) -> tuple[str, str, int]:
    statuses = [item["status"] for item in findings.values()]
    if "NOT SUPPORTED" in statuses:
        result = "CORRECTION REQUIRED"
        risk = "HIGH" if statuses.count("NOT SUPPORTED") > 1 else "MEDIUM"
    elif "BORDERLINE" in statuses:
        result, risk = "REVIEW RECOMMENDED", "MEDIUM"
    else:
        result, risk = "PASS", "LOW"
    confidence = max(70, min(98, 96 - statuses.count("BORDERLINE") * 8 - statuses.count("NOT SUPPORTED") * 5))
    return result, risk, confidence


def render_report(codes: list[dict], payer: str, findings: dict[str, dict], explanations: dict, sources: list[str]) -> str:
    result, risk, confidence = overall_result(findings)
    lines = ["# TRIMERA DOCUMENTATION QA", "", "## Provider Intended Billing", ", ".join(entry["raw"] for entry in codes), "", "## Payer", payer, "", "## Overall Result", f"**{result}**", "", "## Documentation Confidence", f"**{confidence}%**", "", "## Overall Audit Risk", f"**{risk}**", "", "## Governing Authority Used", ", ".join(f"[{source}]" for source in sources) or "No authority loaded", "", "---", ""]
    explanation_map = explanations.get("code_explanations", {})
    for entry in codes:
        code, finding = entry["code"], findings[entry["code"]]
        explanation = explanation_map.get(code, {})
        support = explanation.get("support") or " ".join(finding["reasons"])
        deficiencies = explanation.get("deficiencies") or finding["deficiencies"]
        lines.extend([f"## {code}" + (f" × {entry['units']}" if entry["units"] > 1 else ""), f"### {finding['status']}", "", "**Support**", support or "No supporting element was established.", ""])
        if finding["status"] != "SUPPORTED":
            lines.append("**Documentation Deficiencies**")
            lines.extend(f"- {item}" for item in deficiencies)
            lines.append("")
        code_risk = "LOW" if finding["status"] == "SUPPORTED" else "MEDIUM" if finding["status"] == "BORDERLINE" else "HIGH"
        lines.extend(["**Audit Risk**", code_risk, "", "---", ""])
    lines.extend(["## Documentation Quality Improvements", ""])
    improvements = explanations.get("quality_improvements", [])[:3]
    lines.extend([f"- {item}" for item in improvements] or ["None identified."])
    lines.extend(["", "---", "", "## Final Assessment", explanations.get("final_assessment", "The fixed code-level findings above control the result.")])
    return "\n".join(lines)


def reset_qa_session() -> None:
    for key in ["qa_result", "qa_note_text", "qa_codes", "qa_payer", "qa_excerpts", "qa_facts", "qa_findings", "qa_sources", "qa_followup_messages"]:
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
    st.info("Code-level outcomes are determined by the fixed rules engine.")

st.title("📋 Trimera Documentation QA")
st.caption("Grounded review using payer, AMA, CMS, and Trimera authority documents.")

try:
    reference_library = load_reference_library()
except Exception as exc:
    st.error(f"Could not load the reference library: {exc}")
    st.stop()

payer = st.selectbox("Payer", ["Not specified", "Medicare", "UnitedHealthcare Community Plan / Medicaid", "UnitedHealthcare / Optum Commercial", "BCBS", "Aetna", "Cigna", "Humana", "Other"])
codes_raw = st.text_input("Intended billing", placeholder="99214, 90833, G2211  OR  99215, 99417 x5")
method = st.radio("Clinical note", ["Paste text", "Upload PDF"], horizontal=True)
note_text = ""
if method == "Paste text":
    note_text = st.text_area("Paste completed note", height=360)
else:
    uploaded = st.file_uploader("Upload completed note PDF", type=["pdf"])
    if uploaded:
        try:
            note_text = extract_pdf(uploaded)
            st.success("PDF text extracted.")
        except Exception as exc:
            st.error(f"Could not read PDF: {exc}")

if st.button("Run documentation QA", type="primary", use_container_width=True):
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
    excerpts, used_sources = governing_excerpts(reference_library, payer, codes)
    if not excerpts:
        st.error("No governing reference excerpts were found. Confirm the files exist in the reference folder with the expected filenames.")
        st.stop()
    client = OpenAI(api_key=OPENAI_API_KEY)
    extraction_input = f"INTENDED BILLING:\n{chr(10).join(entry['raw'] for entry in codes)}\n\nPAYER:\n{payer}\n\nCOMPLETED CLINICAL NOTE:\n{note_text}"
    with st.spinner("Extracting documented facts..."):
        try:
            extraction_response = client.responses.create(model=MODEL, instructions=FACT_EXTRACTION_PROMPT, input=extraction_input)
            facts = clean_json(extraction_response.output_text)
        except Exception as exc:
            st.error(f"Fact extraction failed: {exc}")
            st.stop()
    findings = evaluate_codes(codes, facts, payer)
    explanation_input = f"PAYER:\n{payer}\n\nINTENDED BILLING:\n{json.dumps(codes, indent=2)}\n\nFIXED CODE FINDINGS:\n{json.dumps(findings, indent=2)}\n\nEXTRACTED FACTS:\n{json.dumps(facts, indent=2)}\n\nGOVERNING EXCERPTS:\n{excerpts}\n\nCOMPLETED NOTE:\n{note_text}"
    with st.spinner("Writing grounded feedback..."):
        try:
            explanation_response = client.responses.create(model=MODEL, instructions=EXPLANATION_PROMPT, input=explanation_input)
            explanations = clean_json(explanation_response.output_text)
        except Exception as exc:
            explanations = {"code_explanations": {}, "quality_improvements": [], "final_assessment": f"The fixed rules engine completed the review, but the explanation layer failed: {exc}"}
    report = render_report(codes, payer, findings, explanations, used_sources)
    st.session_state.update({"qa_result": report, "qa_note_text": note_text, "qa_codes": codes, "qa_payer": payer, "qa_excerpts": excerpts, "qa_facts": facts, "qa_findings": findings, "qa_sources": used_sources, "qa_followup_messages": []})

if st.session_state.get("qa_result"):
    report = st.session_state["qa_result"]
    st.divider()
    st.subheader("QA result")
    st.markdown(report)
    st.download_button("Download report", data=report, file_name="trimera_documentation_qa.md", mime="text/markdown", use_container_width=True)
    with st.expander("Technical fact extraction"):
        st.json(st.session_state["qa_facts"])
    st.divider()
    st.subheader("💬 Ask Trimera about this QA review")
    st.caption("Ask why a fixed result was reached, what documentation is missing, or request concise provider education.")
    for message in st.session_state.get("qa_followup_messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    followup_question = st.chat_input("Ask a follow-up about this documentation review...")
    if followup_question:
        st.session_state["qa_followup_messages"].append({"role": "user", "content": followup_question})
        with st.chat_message("user"):
            st.markdown(followup_question)
        conversation = "\n\n".join(f"{message['role'].upper()}:\n{message['content']}" for message in st.session_state["qa_followup_messages"])
        followup_context = f"PAYER:\n{st.session_state['qa_payer']}\n\nINTENDED BILLING:\n{json.dumps(st.session_state['qa_codes'], indent=2)}\n\nFIXED FINDINGS:\n{json.dumps(st.session_state['qa_findings'], indent=2)}\n\nEXTRACTED FACTS:\n{json.dumps(st.session_state['qa_facts'], indent=2)}\n\nORIGINAL REPORT:\n{st.session_state['qa_result']}\n\nGOVERNING EXCERPTS:\n{st.session_state['qa_excerpts']}\n\nCOMPLETED NOTE:\n{st.session_state['qa_note_text']}\n\nFOLLOW-UP CONVERSATION:\n{conversation}"
        client = OpenAI(api_key=OPENAI_API_KEY)
        with st.chat_message("assistant"):
            with st.spinner("Reviewing the fixed QA result..."):
                try:
                    response = client.responses.create(model=MODEL, instructions=FOLLOWUP_PROMPT, input=followup_context)
                    answer = response.output_text
                    st.markdown(answer)
                except Exception as exc:
                    st.error(f"OpenAI request failed: {exc}")
                    st.stop()
        st.session_state["qa_followup_messages"].append({"role": "assistant", "content": answer})
