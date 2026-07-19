"""Google Workspace authentication shared by protected Trimera tools."""

import os
import time

import streamlit as st


INACTIVITY_TIMEOUT_SECONDS = 30 * 60
MAX_SESSION_SECONDS = 8 * 60 * 60
LAST_ACTIVITY_KEY = "trimera_last_activity"
SESSION_STARTED_KEY = "trimera_session_started"
DEFAULT_ALLOWED_DOMAIN = "trimerahealth.net"
REQUIRED_AUTH_SETTINGS = (
    "redirect_uri",
    "cookie_secret",
    "client_id",
    "client_secret",
    "server_metadata_url",
)


def _user_claims() -> dict:
    """Return OIDC identity claims without exposing provider tokens."""
    if not getattr(st.user, "is_logged_in", False):
        return {}
    return st.user.to_dict()


def _auth_is_configured() -> bool:
    """Return whether Streamlit has a complete OIDC provider configuration."""
    try:
        auth_settings = st.secrets.get("auth", {})
        return all(str(auth_settings.get(key, "")).strip() for key in REQUIRED_AUTH_SETTINGS)
    except Exception:
        return False


def _logout() -> None:
    """Clear application state and remove the Streamlit identity cookie."""
    st.session_state.clear()
    st.logout()


def logout_user() -> None:
    """Log out the current user from Trimera."""
    _logout()


def current_user_email() -> str:
    """Return the authenticated user's normalized email address."""
    return str(_user_claims().get("email", "")).strip().lower()


def _is_authorized_workspace_user(claims: dict) -> bool:
    """Require a verified identity from the configured Google Workspace."""
    allowed_domain = os.getenv(
        "TRIMERA_ALLOWED_EMAIL_DOMAIN", DEFAULT_ALLOWED_DOMAIN
    ).strip().lower()
    email = str(claims.get("email", "")).strip().lower()
    hosted_domain = str(claims.get("hd", "")).strip().lower()
    email_verified = claims.get("email_verified") in (True, "true", "True", 1)
    return (
        email_verified
        and email.endswith(f"@{allowed_domain}")
        and hosted_domain == allowed_domain
    )


def _session_expired(claims: dict, now: float) -> bool:
    """Enforce inactivity, absolute-session, and identity-token expiration."""
    last_activity = st.session_state.get(LAST_ACTIVITY_KEY, now)
    session_started = st.session_state.get(SESSION_STARTED_KEY, now)

    try:
        token_expired = now >= float(claims.get("exp", now + 1))
    except (TypeError, ValueError):
        token_expired = True

    return (
        now - last_activity >= INACTIVITY_TIMEOUT_SECONDS
        or now - session_started >= MAX_SESSION_SECONDS
        or token_expired
    )


@st.fragment(run_every="60s")
def _session_watchdog() -> None:
    """Log out idle sessions without waiting for the next user interaction."""
    if not getattr(st.user, "is_logged_in", False):
        return
    if _session_expired(_user_claims(), time.time()):
        _logout()


def require_auth(title: str, caption: str) -> None:
    """Require an authorized work account for a protected Trimera page."""
    if not getattr(st.user, "is_logged_in", False):
        st.title(title)
        st.caption(caption)
        if _auth_is_configured():
            st.info("Sign in with your Trimera Health work email to continue.")
            st.button("Sign in with Google", type="primary", on_click=st.login)
        else:
            st.error(
                "Google sign-in is awaiting administrator configuration. "
                "No staff credentials were accepted or transmitted."
            )
        st.stop()

    claims = _user_claims()
    if not _is_authorized_workspace_user(claims):
        st.error("Access is limited to verified Trimera Health work accounts.")
        st.button("Sign out", type="primary", on_click=logout_user)
        st.stop()

    now = time.time()
    if _session_expired(claims, now):
        st.session_state.clear()
        st.warning("Your Trimera session expired. Please sign in again.")
        st.logout()

    st.session_state.setdefault(SESSION_STARTED_KEY, now)
    st.session_state[LAST_ACTIVITY_KEY] = now
    _session_watchdog()
