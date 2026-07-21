"""Shared, PHI-separated web-research workflow for Trimera responses."""

from __future__ import annotations

import copy
import re
from typing import Any


WEB_SEARCH_TOOLS = [{"type": "web_search"}]

WEB_RESEARCH_INSTRUCTIONS = """

CURRENT EXTERNAL RESEARCH POLICY
- Current external research has already been performed through a PHI-separated research step when it could improve this answer.
- Prefer primary, authoritative sources: CMS and other government sites, official payer policies, FDA labeling and safety communications, official prescribing information, recognized professional organizations, and peer-reviewed literature. Use high-quality secondary sources only when necessary.
- Clearly distinguish facts taken from uploaded or embedded documents from information found through current web research.
- Cite web-derived material with the source organization/title and a usable URL. Do not present an uncited web claim as though it came from an uploaded guideline.
- Uploaded records remain the only source of patient-specific and claim-specific facts. Never fill missing documentation with facts found online.
- If current web guidance conflicts with supplied governing material, identify the conflict, dates, and jurisdictions instead of silently choosing one.
- Web research may provide context and education, but it may not override fixed Python rule-engine findings or guarantee coverage, payment, authorization, or clinical safety.
""".strip()

TOPIC_EXTRACTION_INSTRUCTIONS = """
Create a short web-research brief from the supplied material. Return only general,
non-patient-specific research questions and keywords that would help answer the
request. Preserve medication names, CPT/HCPCS codes, diagnoses at a general level,
payer names, and the type of policy or literature needed.

Never include or reproduce a person's name, initials, date of birth, exact date of
service, address, email, phone number, medical-record number, member/subscriber ID,
claim/case number, account number, authorization number, or any quoted passage that
could identify a person. Do not summarize the patient's history. Replace any such
detail with a generic concept such as "adult patient," "medication trial history,"
or "payer authorization criteria."
""".strip()

RESEARCH_ONLY_INSTRUCTIONS = """
Research the supplied general healthcare questions using current reputable sources.
Prefer official government, payer, drug-labeling, professional-association, and
peer-reviewed sources. Do not search for or infer the identity of any patient.
Return a concise research digest with source titles, organizations, publication or
effective dates when available, and usable URLs. Clearly flag conflicts or limits.
""".strip()


_IDENTIFIER_PATTERNS = (
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[email removed]"),
    (re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)"), "[phone removed]"),
    (re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4})\b"), "[date removed]"),
    (re.compile(r"(?i)\b(?:DOB|MRN|member\s*ID|subscriber\s*ID|claim(?:/case)?\s*(?:number|#)|case\s*#|account\s*(?:number|#)|authorization\s*(?:number|#))\s*[:#-]?\s*[A-Z0-9-]+"), "[identifier removed]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[identifier removed]"),
)


def sanitize_research_brief(text: str) -> str:
    """Defense-in-depth removal of common identifiers from a research brief."""
    sanitized = text
    for pattern, replacement in _IDENTIFIER_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized[:6000]


def with_web_research(instructions: str) -> str:
    return f"{instructions.strip()}\n\n{WEB_RESEARCH_INSTRUCTIONS}"


def _append_research_context(api_input: Any, research_digest: str) -> Any:
    context = (
        "PHI-SEPARATED CURRENT RESEARCH DIGEST:\n"
        "Use this only as general external context. Patient-specific facts must come "
        "only from the original uploaded or pasted record.\n\n"
        f"{research_digest}"
    )
    if isinstance(api_input, str):
        return f"{api_input}\n\n{context}"
    combined = copy.deepcopy(api_input)
    combined.append({"role": "user", "content": [{"type": "input_text", "text": context}]})
    return combined


def create_researched_response(*, client: Any, model: str, instructions: str, api_input: Any) -> Any:
    """Research without exposing the original record to the web-search tool.

    The first request sees the clinical material but has no tools and produces only
    generalized topics. Only that sanitized brief reaches the web-enabled request.
    The final synthesis sees the original record plus the resulting research digest,
    but has no web tool available.
    """
    topic_response = client.responses.create(
        model=model,
        instructions=TOPIC_EXTRACTION_INSTRUCTIONS,
        input=api_input,
    )
    research_brief = sanitize_research_brief(topic_response.output_text or "")
    if not research_brief.strip():
        research_brief = "Current authoritative guidance relevant to the user's general healthcare question."

    research_response = client.responses.create(
        model=model,
        instructions=RESEARCH_ONLY_INSTRUCTIONS,
        input=research_brief,
        tools=WEB_SEARCH_TOOLS,
    )
    research_digest = research_response.output_text or "No external research results were returned."

    return client.responses.create(
        model=model,
        instructions=with_web_research(instructions),
        input=_append_research_context(api_input, research_digest),
    )
