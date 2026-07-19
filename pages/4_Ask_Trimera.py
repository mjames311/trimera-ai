import os
from typing import Any

import streamlit as st
from openai import OpenAI
from auth import logout_user, require_auth
from research import WEB_SEARCH_TOOLS, with_web_research
from theme import apply_trimera_theme, page_header, render_topbar, sidebar_label, sidebar_model, sidebar_reminder


st.set_page_config(
    page_title="Ask Trimera",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
API_KEY = os.getenv("OPENAI_API_KEY", "")

SYSTEM_INSTRUCTIONS = (
    "You are Ask Trimera, an internal healthcare operations assistant for an "
    "outpatient psychiatry practice. Be concise, accurate, and practical. "
    "Use the complete conversation history, including prior questions, answers, "
    "corrections, and attached files, to understand follow-up requests. "
    "When analyzing files, clearly distinguish what the documents show from any "
    "inference. Do not claim a file contains information that is not present."
)

ALLOWED_FILE_TYPES = [
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "csv",
    "tsv",
    "txt",
    "rtf",
    "odt",
    "ppt",
    "pptx",
]

MAX_FILES_PER_MESSAGE = 20
MAX_TOTAL_UPLOAD_MB = 100


def get_client() -> OpenAI:
    """Create an authenticated OpenAI client."""
    if not API_KEY:
        st.error("OPENAI_API_KEY not configured.")
        st.stop()

    return OpenAI(api_key=API_KEY)


def initialize_state() -> None:
    """Initialize all chat-related Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    if "uploaded_openai_file_ids" not in st.session_state:
        st.session_state["uploaded_openai_file_ids"] = []

    if "uploader_version" not in st.session_state:
        st.session_state["uploader_version"] = 0


def delete_uploaded_openai_files() -> None:
    """
    Best-effort cleanup of files uploaded to OpenAI during this chat session.

    Cleanup errors are intentionally ignored so they never prevent the user from
    clearing the conversation or signing out.
    """
    file_ids = st.session_state.get("uploaded_openai_file_ids", [])

    if not API_KEY or not file_ids:
        return

    try:
        client = OpenAI(api_key=API_KEY)

        for file_id in file_ids:
            try:
                client.files.delete(file_id)
            except Exception:
                pass
    except Exception:
        pass


def clear_conversation() -> None:
    """Delete uploaded API files and reset the current conversation."""
    delete_uploaded_openai_files()
    st.session_state["messages"] = []
    st.session_state["uploaded_openai_file_ids"] = []
    st.session_state["uploader_version"] = (
        st.session_state.get("uploader_version", 0) + 1
    )


def sign_out() -> None:
    """Delete uploaded API files and log out the current user."""
    delete_uploaded_openai_files()
    logout_user()


def validate_uploads(uploaded_files: list[Any]) -> None:
    """Stop with a clear message when upload limits are exceeded."""
    if len(uploaded_files) > MAX_FILES_PER_MESSAGE:
        st.error(
            f"Please attach no more than {MAX_FILES_PER_MESSAGE} files in one message."
        )
        st.stop()

    total_bytes = sum(file.size for file in uploaded_files)
    max_bytes = MAX_TOTAL_UPLOAD_MB * 1024 * 1024

    if total_bytes > max_bytes:
        st.error(
            f"The combined upload is too large. Keep the total under "
            f"{MAX_TOTAL_UPLOAD_MB} MB."
        )
        st.stop()


def upload_files_to_openai(
    client: OpenAI,
    uploaded_files: list[Any],
) -> list[dict[str, str]]:
    """
    Upload Streamlit files to the OpenAI Files API.

    Returns metadata used both for the API request and the visible chat history.
    """
    uploaded_metadata: list[dict[str, str]] = []

    for uploaded_file in uploaded_files:
        uploaded_file.seek(0)

        created_file = client.files.create(
            file=(
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            ),
            purpose="user_data",
        )

        uploaded_metadata.append(
            {
                "file_id": created_file.id,
                "name": uploaded_file.name,
            }
        )

        st.session_state["uploaded_openai_file_ids"].append(created_file.id)

    return uploaded_metadata


def build_responses_input() -> list[dict[str, Any]]:
    """
    Convert the complete saved chat into Responses API input.

    Each user message may contain both its original text and any files attached
    to that turn. This lets later follow-up questions continue to reference files
    uploaded earlier in the same conversation.
    """
    api_input: list[dict[str, Any]] = []

    for message in st.session_state["messages"]:
        role = message.get("role")
        text = message.get("content", "")

        if role == "assistant":
            if text:
                api_input.append(
                    {
                        "role": "assistant",
                        "content": text,
                    }
                )
            continue

        if role != "user":
            continue

        content_parts: list[dict[str, str]] = []

        for attachment in message.get("attachments", []):
            file_id = attachment.get("file_id")
            if file_id:
                content_parts.append(
                    {
                        "type": "input_file",
                        "file_id": file_id,
                    }
                )

        if text:
            content_parts.append(
                {
                    "type": "input_text",
                    "text": text,
                }
            )

        if content_parts:
            api_input.append(
                {
                    "role": "user",
                    "content": content_parts,
                }
            )

    return api_input


def render_message(message: dict[str, Any]) -> None:
    """Render one saved chat message and its attachment names."""
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        attachments = message.get("attachments", [])
        if attachments:
            names = ", ".join(item["name"] for item in attachments)
            st.caption(f"Attached: {names}")


apply_trimera_theme()
require_auth("Ask Trimera", "Internal Trimera Health tool")
initialize_state()
render_topbar()

with st.sidebar:
    sidebar_label("Quick actions")
    if st.button("Clear conversation", use_container_width=True):
        clear_conversation()
        st.rerun()

    if st.button("Sign out", use_container_width=True):
        sign_out()
    sidebar_model(MODEL)
    sidebar_reminder("Private workspace", "Files and questions are handled through the configured server-side account.")

page_header(
    "▤",
    "Ask Trimera",
    "Ask questions or attach PDF, Word, Excel, CSV, text, or PowerPoint files.",
)

uploaded_files = st.file_uploader(
    "Attach files",
    type=ALLOWED_FILE_TYPES,
    accept_multiple_files=True,
    key=f"ask_trimera_uploader_{st.session_state['uploader_version']}",
    help=(
        f"Attach up to {MAX_FILES_PER_MESSAGE} files per message, with a combined "
        f"size under {MAX_TOTAL_UPLOAD_MB} MB."
    ),
)

st.caption("Current reputable web research is automatic when it can improve the answer. Web-derived information is identified and cited.")

for saved_message in st.session_state["messages"]:
    render_message(saved_message)

question = st.chat_input("Ask Trimera...")

if question:
    client = get_client()
    current_files = uploaded_files or []
    validate_uploads(current_files)

    uploaded_metadata: list[dict[str, str]] = []

    if current_files:
        with st.spinner(f"Uploading {len(current_files)} file(s)..."):
            try:
                uploaded_metadata = upload_files_to_openai(
                    client=client,
                    uploaded_files=current_files,
                )
            except Exception as exc:
                st.error(f"File upload failed:\n\n{exc}")
                st.stop()

    user_message = {
        "role": "user",
        "content": question,
        "attachments": uploaded_metadata,
    }
    st.session_state["messages"].append(user_message)
    render_message(user_message)

    request_kwargs: dict[str, Any] = {
        "model": MODEL,
        "input": build_responses_input(),
        "instructions": with_web_research(SYSTEM_INSTRUCTIONS),
        "tools": WEB_SEARCH_TOOLS,
    }

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.responses.create(**request_kwargs)
                answer = response.output_text or "No response was returned."
            except Exception as exc:
                answer = f"OpenAI error:\n\n{exc}"

        st.markdown(answer)

    st.session_state["messages"].append(
        {
            "role": "assistant",
            "content": answer,
        }
    )

    # Reset the uploader after sending so the same files are not accidentally
    # attached to the next message.
    st.session_state["uploader_version"] += 1
    st.rerun()
