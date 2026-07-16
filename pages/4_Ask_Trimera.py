import os
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Ask Trimera", page_icon="💬", layout="wide")

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")
API_KEY = os.getenv("OPENAI_API_KEY", "")

def password_gate():
    if st.session_state.get("authenticated"):
        return
    if not TEST_PASSWORD:
        st.error("TRIMERA_QA_PASSWORD not configured.")
        st.stop()
    st.title("Ask Trimera")
    pwd = st.text_input("Password", type="password")
    if st.button("Sign in"):
        if pwd == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()

password_gate()

if "messages" not in st.session_state:
    st.session_state["messages"] = []

with st.sidebar:
    st.title("Ask Trimera")
    use_web = st.toggle("Search the web", value=False)
    if st.button("Clear conversation"):
        st.session_state["messages"] = []
        st.rerun()
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()

st.title("💬 Ask Trimera")
st.caption("Upload files and ask questions.")

uploaded = st.file_uploader(
    "Attach a document",
    type=["pdf","txt","csv","png","jpg","jpeg","docx","xlsx"],
    accept_multiple_files=False
)

for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

question = st.chat_input("Ask Trimera...")

if question:
    if not API_KEY:
        st.error("OPENAI_API_KEY not configured.")
        st.stop()

    st.session_state["messages"].append({"role":"user","content":question})
    with st.chat_message("user"):
        st.markdown(question)
        if uploaded:
            st.caption(f"Attached: {uploaded.name}")

    client = OpenAI(api_key=API_KEY)

    prompt = question
    if uploaded:
        prompt += f"\n\nThe user attached a file named '{uploaded.name}'. Analyze it if your model supports file inputs. If not, explain what additional implementation is needed."

    kwargs = {
        "model": MODEL,
        "input": prompt,
        "instructions": "You are Ask Trimera, an internal healthcare operations assistant. Be concise and accurate."
    }

    # NOTE: Web search support depends on the model/account.
    if use_web:
        kwargs["tools"] = [{"type":"web_search"}]

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = client.responses.create(**kwargs)
                answer = resp.output_text
            except Exception as e:
                answer = f"OpenAI error:\\n\\n{e}"
            st.markdown(answer)
            st.session_state["messages"].append({"role":"assistant","content":answer})
