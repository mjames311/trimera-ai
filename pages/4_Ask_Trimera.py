import base64
import mimetypes
import os
from typing import Any

import streamlit as st
from openai import OpenAI


st.set_page_config(
    page_title="Ask Trimera",
    page_icon="💬",
    layout="wide",
)

CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
WEB_MODEL = os.getenv("OPENAI_WEB_MODEL", "gpt-5.5")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

MAX_FILE_SIZE_MB = 15
MAX_FILES = 5


INSTRUCTIONS = """
You are Ask Trimera, the internal AI assistant for Trimera Health.

You assist staff with:
- Medical billing and claim questions
- Coding and documentation questions
- ERAs, denials, CARCs, RARCs, and payer terminology
- 837P claim transmission questions
- Prior authorizations and appeal drafting
- DrChrono support communications
- CMS and payer guidance
- Practice operations and professional writing
- Analysis of uploaded documents, spreadsheets, and screenshots

Rules:
- Be practical, accurate, and concise.
- Use correct medical billing and healthcare terminology.
- Clearly distinguish facts found in an uploaded document from general guidance.
- When web search is enabled, use current, reliable sources and cite them.
- Prefer primary and authoritative sources such as CMS, payer policies,
  government agencies, and official product documentation.
- Never invent claim details, payer rules, CMS guidance, or document contents.
- State clearly when more information is required.
- Do not guarantee reimbursement, authorization, appeal success, legal
  compliance, or clinical outcomes.
- Do not expose unnecessary patient identifiers in the response.
- When analyzing a document, answer the user's question first, then explain
  the supporting findings.
""".strip()


def password_gate() -> None:
    if not TEST_PASSWORD:
        st.warning("TRIMERA_QA_PASSWORD is not configured.")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("Ask Trimera")
    st.caption("Internal Trimera Health AI assistant")

    entered = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        if entered == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


def get_mime_type(uploaded_file: Any) -> str:
    if uploaded_file.type:
        return uploaded_file.type

    guessed_type, _ = mimetypes.guess_type(uploaded_file.name)
    return guessed_type or "application/octet-stream"


def make_data_url(file_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def build_attachment_part(uploaded_file: Any) -> dict[str, Any]:
    file_bytes = uploaded_file.getvalue()
    mime_type = get_mime_type(uploaded_file)
    data_url = make_data_url(file_bytes, mime_type)

    if mime_type.startswith("image/"):
        return {
            "type": "input_image",
            "image_url": data_url,
        }

    return {
        "type": "input_file",
        "filename": uploaded_file.name,
        "file_data": data_url,
    }


def validate_files(uploaded_files: list[Any]) -> list[str]:
    errors: list[str] = []

    if len(uploaded_files) > MAX_FILES:
        errors.append(
            f"Upload no more than {MAX_FILES} files at a time."
        )

    for uploaded_file in uploaded_files:
        size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            errors.append(
                f"{uploaded_file.name} is {size_mb:.1f} MB. "
                f"The current limit is {MAX_FILE_SIZE_MB} MB per file."
            )

    return errors


def build_api_input(
    messages: list[dict[str, str]],
    question: str,
    uploaded_files: list[Any],
) -> list[dict[str, Any]]:
    api_input: list[dict[str, Any]] = []

    for message in messages:
        api_input.append(
            {
                "role": message["role"],
                "content": [
                    {
                        "type": "input_text",
                        "text": message["content"],
                    }
                ],
            }
        )

    current_content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": question,
        }
    ]

    for uploaded_file in uploaded_files:
        current_content.append(
            build_attachment_part(uploaded_file)
        )

    api_input.append(
        {
            "role": "user",
            "content": current_content,
        }
    )

    return api_input


password_gate()

if "ask_trimera_messages" not in st.session_state:
    st.session_state["ask_trimera_messages"] = []


with st.sidebar:
    st.subheader("Ask Trimera")

    use_web = st.toggle(
        "Search the web",
        value=False,
        help=(
            "Enable this for current laws, payer guidance, CMS updates, "
            "prices, news, product information, or other live information."
        ),
    )

    if use_web:
        st.success("Live web search enabled")
        st.write(f"Web model: `{WEB_MODEL}`")
    else:
        st.write(f"Chat model: `{CHAT_MODEL}`")

    if st.button(
        "Clear conversation",
        use_container_width=True,
    ):
        st.session_state["ask_trimera_messages"] = []
        st.rerun()

    if st.button(
        "Sign out",
        use_container_width=True,
    ):
        st.session_state.clear()
        st.rerun()


st.title("💬 Ask Trimera")
st.caption(
    "Ask questions about billing, coding, documentation, payers, "
    "practice operations, or uploaded files."
)

st.warning(
    "Do not upload PHI until the OpenAI BAA and all required production "
    "safeguards are active."
)

uploaded_files = st.file_uploader(
    "Attach documents or screenshots",
    type=[
        "pdf",
        "txt",
        "md",
        "csv",
        "json",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "png",
        "jpg",
        "jpeg",
        "webp",
    ],
    accept_multiple_files=True,
    help=(
        "Attach up to five PDFs, screenshots, spreadsheets, "
        "text files, Word documents, or PowerPoint files."
    ),
)

if uploaded_files:
    st.info(
        "Attached: "
        + ", ".join(uploaded_file.name for uploaded_file in uploaded_files)
    )

    file_errors = validate_files(uploaded_files)

    for error in file_errors:
        st.error(error)

else:
    file_errors = []


for message in st.session_state["ask_trimera_messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


question = st.chat_input(
    "Ask Trimera about a document or anything else..."
)


if question:
    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()

    if file_errors:
        st.error("Fix the attached-file issue before sending your question.")
        st.stop()

    previous_messages = list(
        st.session_state["ask_trimera_messages"]
    )

    st.session_state["ask_trimera_messages"].append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

        if uploaded_files:
            st.caption(
                "Attachments: "
                + ", ".join(
                    uploaded_file.name
                    for uploaded_file in uploaded_files
                )
            )

    client = OpenAI(api_key=OPENAI_API_KEY)

    api_input = build_api_input(
        messages=previous_messages,
        question=question,
        uploaded_files=uploaded_files or [],
    )

    request_arguments: dict[str, Any] = {
        "model": WEB_MODEL if use_web else CHAT_MODEL,
        "instructions": INSTRUCTIONS,
        "input": api_input,
    }

    if use_web:
        request_arguments["tools"] = [
            {
                "type": "web_search",
            }
        ]

    with st.chat_message("assistant"):
        with st.spinner(
            "Searching and thinking..."
            if use_web
            else "Reviewing and thinking..."
        ):
            try:
                response = client.responses.create(
                    **request_arguments
                )

                answer = response.output_text

                st.markdown(answer)

                st.session_state["ask_trimera_messages"].append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

            except Exception as exc:
                st.error(f"OpenAI request failed: {exc}")
                st.caption(
                    "If web search caused the error, turn off "
                    "'Search the web' and retry."
                )
