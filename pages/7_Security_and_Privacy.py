"""Plain-language security and privacy information for Trimera staff."""

import streamlit as st

from auth import logout_user, require_auth
from theme import (
    apply_trimera_theme,
    page_header,
    render_topbar,
    sidebar_label,
    sidebar_reminder,
)


st.set_page_config(
    page_title="Security and Privacy | Trimera AI",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_trimera_theme()
require_auth(
    "Trimera AI Security and Privacy",
    "Security information for authorized Trimera Health staff.",
)
render_topbar()
page_header(
    "security",
    "Security & Privacy",
    "How Trimera AI protects access, separates patient facts from research, and supports responsible use.",
)

with st.sidebar:
    sidebar_label("Quick actions")
    st.caption(str(st.user.get("email", "")))
    if st.button("Sign out", use_container_width=True):
        logout_user()
    sidebar_reminder(
        "Use the minimum necessary",
        "Only submit information needed for the authorized work task and always review AI output before acting on it.",
    )

st.markdown(
    """
Trimera AI is designed to support secure clinical and administrative work—not to replace
Trimera Health’s privacy program, professional judgment, or legal responsibilities. Its
safeguards combine restricted workforce access, session limits, server-side credentials,
grounding rules, and separation between patient records and external web research.

**Important:** No application can make an organization compliant by itself. Before live
PHI use, Trimera administrators must confirm that applicable BAAs, eligible services,
retention settings, risk analysis, workforce policies, and incident procedures are active
and documented.
"""
)

st.markdown('<div class="trimera-section-title">Protections implemented in this application</div>', unsafe_allow_html=True)
st.markdown(
    """
<div class="trimera-source-grid">
  <div class="trimera-source-card"><strong>Verified work-account access</strong><span>Protected tools require a Google identity with a verified <code>@trimerahealth.net</code> email and matching Google Workspace domain claim. A personal Google account is not accepted.</span></div>
  <div class="trimera-source-card"><strong>Automatic session limits</strong><span>Protected sessions expire after 30 minutes of inactivity, after eight total hours, or when the identity token expires—whichever occurs first.</span></div>
  <div class="trimera-source-card"><strong>Server-side credentials</strong><span>OpenAI and authentication secrets are configured on the server and are not displayed in the browser or entered by staff.</span></div>
  <div class="trimera-source-card"><strong>PHI-separated web research</strong><span>The original patient record is not supplied to the web-enabled research request. Trimera first creates a general topic brief, removes common identifiers, researches that brief, and then returns the research to the protected note-analysis step.</span></div>
  <div class="trimera-source-card"><strong>Grounded patient findings</strong><span>Patient-specific facts must come from the submitted record. Outside literature may add general clinical, payer, regulatory, or coding context but may not invent missing patient history.</span></div>
  <div class="trimera-source-card"><strong>Human review remains required</strong><span>Outputs assist staff and clinicians. They do not independently authorize treatment, submit claims, change billing rules, guarantee payment, or replace professional review.</span></div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="trimera-section-title">Common questions</div>', unsafe_allow_html=True)

with st.expander("Can I use my personal Google account?"):
    st.markdown(
        "No. Protected tools require a verified Trimera Health Google Workspace identity. "
        "Access can be removed through the organization’s account administration when a staff member leaves or changes roles."
    )

with st.expander("Does Trimera send the patient note to ordinary websites?"):
    st.markdown(
        "No. For tools that use current research, the application separates the workflow. "
        "The protected AI step derives a general, non-patient-specific research brief; only "
        "that brief is available to the web-search step. The original note is used again only "
        "during the protected final analysis. Staff should still submit only the minimum information necessary."
    )

with st.expander("Can current medical literature and payer guidance still be used?"):
    st.markdown(
        "Yes. Trimera can research current government guidance, official payer policies, FDA "
        "materials, recognized professional guidance, and peer-reviewed literature. Web-derived "
        "information should be identified and cited, while patient facts remain grounded in the submitted record."
    )

with st.expander("Is OpenAI API data used to train public models?"):
    st.markdown(
        "OpenAI states that API data is not used to train or improve its models unless the customer "
        "affirmatively opts in. PHI use additionally requires an executed OpenAI BAA covering the API "
        "and an eligible retention configuration for the organization. "
        "[OpenAI data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint) · "
        "[OpenAI HIPAA-eligible products and functionality](https://help.openai.com/en/articles/20001069)"
    )

with st.expander("Does using Cloud Run automatically make the application HIPAA compliant?"):
    st.markdown(
        "No. Google lists Cloud Run among services covered by its HIPAA program, but Google also "
        "states that the customer remains responsible for configuring the solution and implementing "
        "the required controls. Trimera must maintain the applicable Google Cloud BAA and use only "
        "covered, appropriately configured services. "
        "[Google Cloud HIPAA information](https://cloud.google.com/security/compliance/hipaa)"
    )

with st.expander("What happens if I walk away without signing out?"):
    st.markdown(
        "The application checks protected sessions every minute and signs the user out after 30 "
        "minutes of inactivity. It also enforces an eight-hour maximum session and respects the "
        "Google identity-token expiration. Staff should still sign out or lock the workstation when leaving it unattended."
    )

with st.expander("Does the AI make clinical, billing, or authorization decisions?"):
    st.markdown(
        "No. Trimera provides structured review and decision support. Documentation QA keeps its "
        "fixed coding findings separate from explanatory research, and no AI response guarantees "
        "coverage, payment, authorization, audit success, or clinical safety. A qualified person must review the result."
    )

with st.expander("What must staff do to help protect PHI?"):
    st.markdown(
        "- Use only your own Trimera Health account.\n"
        "- Submit only information necessary for the assigned task.\n"
        "- Verify the patient and source documents before relying on an answer.\n"
        "- Do not copy PHI into personal email, consumer AI tools, or unapproved storage.\n"
        "- Store downloads only in approved locations and delete unnecessary local copies.\n"
        "- Sign out or lock the workstation when stepping away.\n"
        "- Report unexpected access, disclosure, or behavior through Trimera’s privacy/security process."
    )

st.info(
    "This page describes the current application design in plain language. It is not a legal "
    "opinion, compliance certification, or substitute for Trimera Health’s documented HIPAA risk analysis and policies."
)

st.caption(
    "Authoritative background: "
    "[HHS HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html) · "
    "[OpenAI HIPAA eligibility](https://help.openai.com/en/articles/20001069) · "
    "[Google Cloud HIPAA program](https://cloud.google.com/security/compliance/hipaa)"
)
