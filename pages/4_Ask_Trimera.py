import os

import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="Ask Trimera",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Ask Trimera")
st.caption("Trimera AI Assistant")

question = st.chat_input("Ask anything...")

if question:

    st.chat_message("user").write(question)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.responses.create(
        model="gpt-5.4-mini",
        input=question
    )

    st.chat_message("assistant").write(response.output_text)
