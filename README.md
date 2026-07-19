# Trimera Documentation QA — Local MVP

This is a local/internal prototype for fictional or fully de-identified notes.

## Windows setup

1. Install Python 3.11 or newer.
2. Unzip this folder.
3. Open Command Prompt in the folder.
4. Run: `python -m venv .venv`
5. Run: `.venv\Scripts\activate`
6. Run: `pip install -r requirements.txt`
7. Rename `.env.example` to `.env` and add the required API configuration.
8. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add the Google OAuth client credentials. Never commit this file.
9. Add `http://localhost:8501/oauth2callback` as an authorized redirect URI in the Google OAuth client.
10. Run: `streamlit run app.py`
11. Open `http://localhost:8501` if it does not open automatically.

The Home page is public. Every clinical tool requires a verified Google Workspace account in the domain configured by `TRIMERA_ALLOWED_EMAIL_DOMAIN` (default: `trimerahealth.net`). Protected sessions expire after 30 minutes of inactivity, after eight hours total, or when the Google identity token expires.

## Before PHI

Do not use PHI until the OpenAI BAA is executed and the API organization is correctly provisioned, the hosting environment is under an appropriate BAA, and production authentication/audit logging are configured.
