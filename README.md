# Trimera Documentation QA — Local MVP

This is a local/internal prototype for fictional or fully de-identified notes.

## Windows setup

1. Install Python 3.11 or newer.
2. Unzip this folder.
3. Open Command Prompt in the folder.
4. Run: `python -m venv .venv`
5. Run: `.venv\Scripts\activate`
6. Run: `pip install -r requirements.txt`
7. Rename `.env.example` to `.env` and add your API key and test password.
8. Run: `streamlit run app.py`
9. Open `http://localhost:8501` if it does not open automatically.

## Before PHI

Do not use PHI until the OpenAI BAA is executed and the API organization is correctly provisioned, the hosting environment is under an appropriate BAA, and production authentication/audit logging are configured.
