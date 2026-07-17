import os

import streamlit as st
from openai import OpenAI


st.set_page_config(
    page_title="Ask Trimera",
    page_icon="💬",
    layout="wide",
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")
API_KEY = os.getenv("OPENAI_API_KEY", "")

SYSTEM_INSTRUCTIONS = (
    "You are Ask Trimera, an internal healthcare operations assistant. "
    "Be concise and accurate. Use the complete conversation history to understand "
    "follow-up questions, references, corrections, and requested details. "
    "Do not claim to have analyzed an uploaded file unless its actual contents "
    "were provided to you."
)


def password_gate() -> None:
    """Require the shared Trimera password before displaying the application."""
    if st.session_state.get("authenticated"):
        return

    if not TEST_PASSWORD:
        st.error("TRIMERA_QA_PASSWORD not configured.")
        st.stop()

    st.title("Ask Trimera")
    password = st.text_input("Password", type="password")

    if st.button("Sign in"):
        if password == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()

        st.error("Incorrect password.")

    st.stop()


def build_api_history() -> list[dict[str, str]]:
    """
    Convert all saved chat messages into Responses API input.

    This is the key change: every user and assistant message from the current
    conversation is sent on every request, so follow-up messages retain context.
    """
    return [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in st.session_state["messages"]
        if message.get("role") in {"user", "assistant"}
        and message.get("content")
    ]


password_gate()

if "messages" not in st.session_state:
    st.session_state["messages"] = []

with st.sidebar:
    st.title("Ask Trimera")

    use_web = st.toggle(
        "Search the web",
        value=False,
        key="ask_trimera_use_web",
    )

    if st.button("Clear conversation", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.title("💬 Ask Trimera")
st.caption("Upload files and ask questions.")

uploaded = st.file_uploader(
    "Attach a document",
    type=["pdf", "txt", "csv", "png", "jpg", "jpeg", "docx", "xlsx"],
    accept_multiple_files=False,
)

# Re-display the complete current conversation after every Streamlit rerun.
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask Trimera...")

if question:
    if not API_KEY:
        st.error("OPENAI_API_KEY not configured.")
        st.stop()

    # Save the user's visible message first.
    st.session_state["messages"].append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)
        if uploaded:
            st.caption(f"Attached: {uploaded.name}")

    # Include attachment context in the current API turn without changing the
    # visible chat text. This preserves the existing app behavior.
    api_history = build_api_history()

    if uploaded:
        api_history[-1] = {
            "role": "user",
            "content": (
                f"{question}\n\n"
                f"The user attached a file named '{uploaded.name}'. "
                "The file name is available, but its contents have not been sent "
                "to the model by this implementation. Explain that limitation if "
                "the user asks you to analyze the attachment."
            ),
        }

    request_kwargs = {
        "model": MODEL,
        "input": api_history,
        "instructions": SYSTEM_INSTRUCTIONS,
    }

    # Web search availability depends on the selected model and OpenAI account.
    if use_web:
        request_kwargs["tools"] = [{"type": "web_search"}]

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                client = OpenAI(api_key=API_KEY)
                response = client.responses.create(**request_kwargs)
                answer = response.output_text or "No response was returned."
            except Exception as exc:
                answer = f"OpenAI error:\n\n{exc}"

        st.markdown(answer)

    # Save the assistant reply so it is included in the next API request.
    st.session_state["messages"].append(
        {
            "role": "assistant",
            "content": answer,
        }
    )
