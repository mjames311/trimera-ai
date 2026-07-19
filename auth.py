"""Shared session authentication for protected Trimera tools."""

import time

import streamlit as st


INACTIVITY_TIMEOUT_SECONDS = 30 * 60
AUTHENTICATED_KEY = "authenticated"
LAST_ACTIVITY_KEY = "trimera_last_activity"


def is_authenticated() -> bool:
    """Return whether the current Streamlit session has a fresh login."""
    if not st.session_state.get(AUTHENTICATED_KEY):
        return False
    last_activity = st.session_state.get(LAST_ACTIVITY_KEY, 0)
    return time.time() - last_activity < INACTIVITY_TIMEOUT_SECONDS


def require_auth(password: str, title: str, caption: str) -> None:
    """Require one login per session and expire it after 30 idle minutes."""
    if is_authenticated():
        st.session_state[LAST_ACTIVITY_KEY] = time.time()
        return

    if st.session_state.get(AUTHENTICATED_KEY):
        st.session_state.clear()
        st.info("Your session expired after 30 minutes of inactivity. Please sign in again.")

    if not password:
        st.error("TRIMERA_QA_PASSWORD is not configured.")
        st.stop()

    st.title(title)
    st.caption(caption)
    entered = st.text_input("Password", type="password", key="trimera_shared_password")
    if st.button("Sign in", type="primary", key="trimera_shared_sign_in"):
        if entered == password:
            st.session_state[AUTHENTICATED_KEY] = True
            st.session_state[LAST_ACTIVITY_KEY] = time.time()
            st.rerun()
        st.error("Incorrect password.")
    st.stop()
