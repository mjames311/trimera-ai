"""Shared web-research policy for Trimera analytical and chat responses."""

WEB_SEARCH_TOOLS = [{"type": "web_search"}]

WEB_RESEARCH_INSTRUCTIONS = """

CURRENT EXTERNAL RESEARCH POLICY
- Web search is available automatically. Use it whenever current or external information could materially improve the answer, especially when the embedded or uploaded guidance does not explicitly resolve the question.
- Prefer primary, authoritative sources: CMS and other government sites, official payer policies, FDA labeling and safety communications, official prescribing information, recognized professional organizations, and peer-reviewed literature. Use high-quality secondary sources only when necessary.
- Clearly distinguish facts taken from uploaded or embedded documents from information found through current web research.
- Cite web-derived material with the source organization/title and a usable URL. Do not present an uncited web claim as though it came from an uploaded guideline.
- Uploaded records remain the only source of patient-specific and claim-specific facts. Never fill missing documentation with facts found online.
- If current web guidance conflicts with supplied governing material, identify the conflict, dates, and jurisdictions instead of silently choosing one.
- Web research may provide context and education, but it may not override fixed Python rule-engine findings or guarantee coverage, payment, authorization, or clinical safety.
""".strip()


def with_web_research(instructions: str) -> str:
    return f"{instructions.strip()}\n\n{WEB_RESEARCH_INSTRUCTIONS}"
