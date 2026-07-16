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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


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


password_gate()

with st.sidebar:
    if st.button("Clear conversation"):
        st.session_state["ask_trimera_messages"] = []
        st.rerun()

    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()

    st.write(f"Model: `{MODEL}`")


st.title("💬 Ask Trimera")
st.caption("Ask questions about billing, coding, documentation, payers, and practice operations.")

if "ask_trimera_messages" not in st.session_state:
    st.session_state["ask_trimera_messages"] = []

for message in st.session_state["ask_trimera_messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

question = st.chat_input("Ask Trimera...")

if question:
    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()

    st.session_state["ask_trimera_messages"].append(
        {"role": "user", "content": question}
    )

    with st.chat_message("user"):
        st.write(question)

    instructions = """
You are Ask Trimera, the internal AI assistant for Trimera Health.

You help staff with:
- Medical billing and claim questions
- Coding and documentation questions
- ERA, denial, CARC, RARC, and payer terminology
- Prior authorization and appeal drafting
- DrChrono and claim-transmission questions
- Practice operations and professional writing

Rules:
- Be concise and practical.
- Use correct medical billing terminology.
- Do not invent facts, payer policies, CMS rules, or claim details.
- Clearly say when more information is needed.
- Do not guarantee payment, approval, or legal compliance.
- Distinguish general guidance from a conclusion based on specific documents.
""".strip()

    conversation = "\n\n".join(
        f"{message['role'].upper()}:\n{message['content']}"
        for message in st.session_state["ask_trimera_messages"]
    )

    client = OpenAI(api_key=OPENAI_API_KEY)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.responses.create(
                    model=MODEL,
                    instructions=instructions,
                    input=conversation,
                )
                answer = response.output_text
                st.write(answer)

                st.session_state["ask_trimera_messages"].append(
                    {"role": "assistant", "content": answer}
                )

            except Exception as exc:
                st.error(f"OpenAI request failed: {exc}")
