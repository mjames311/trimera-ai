"""Voice-assisted Spravato medication log with a safe practice mode.

The page intentionally does not write to Microsoft 365 until a separately
configured Teams/SharePoint connector is enabled and tested.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st
from openai import OpenAI

from auth import current_user_email, logout_user, require_auth
from theme import (
    apply_trimera_theme,
    page_header,
    render_topbar,
    sidebar_label,
    sidebar_model,
    sidebar_reminder,
)


st.set_page_config(
    page_title="Spravato Medication Log | Trimera AI",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "Spravato Medication Log"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
API_KEY = os.getenv("OPENAI_API_KEY", "")
TEAMS_WRITE_ENABLED = os.getenv("TRIMERA_MED_LOG_TEAMS_WRITE_ENABLED", "").lower() == "true"

PATIENTS = {
    "Bart Simpson": {"dob": "04/01/1985", "opening_balance": 9},
    "Lisa Simpson": {"dob": "05/09/1987", "opening_balance": 5},
    "Homer Simpson": {"dob": "05/12/1956", "opening_balance": 7},
    "Marge Simpson": {"dob": "10/01/1956", "opening_balance": 4},
}

LOG_COLUMNS = [
    "DATE",
    "# OF KITS RECEIVED",
    "# OF KITS RETURNED",
    "# OF KITS USED",
    "# OF KITS ON HAND",
    "TRACKING OR LOT #",
    "E-SIGNATURE",
    "SIG 2",
    "Notes",
]

EXTRACTION_INSTRUCTIONS = """
You convert one staff dictation into a proposed Spravato medication-log entry.
The speaker may use natural, incomplete language and may state fields in any
order. Extract only what was actually said. Do not invent a patient, date, lot
number, signature, quantity, or dose.

Known fictional practice patients:
- Bart Simpson
- Lisa Simpson
- Homer Simpson
- Marge Simpson

Interpret common equivalents such as "used/administered/gave," "received/a
shipment arrived," "returned/sent back," and "on hand/remaining/current
count." Preserve lot and tracking identifiers exactly as spoken except for
removing spaces between individually dictated letters or digits. A phrase such
as "go to Bart Simpson" selects that patient. "New line," "add row," or
"submit row" means the speaker is ready for staff review; it never bypasses
confirmation.

Return only valid JSON with these keys:
patient_name, date, kits_received, kits_returned, kits_used, kits_on_hand,
lot_number, e_signature, second_signature, dose_mg, notes, ready_for_review.
Use null for missing values. Use integers for kit counts. Format an unambiguous
date as MM/DD/YYYY. ready_for_review is true only when the dictation includes a
new-line/add-row/submit-row instruction.
""".strip()


def initialize_state() -> None:
    st.session_state.setdefault("medlog_patient", "Bart Simpson")
    st.session_state.setdefault("medlog_pending", {})
    st.session_state.setdefault(
        "medlog_rows",
        {
            name: [
                {
                    "DATE": "07/20/2026",
                    "# OF KITS RECEIVED": 0,
                    "# OF KITS RETURNED": 0,
                    "# OF KITS USED": 0,
                    "# OF KITS ON HAND": details["opening_balance"],
                    "TRACKING OR LOT #": "PRACTICE-START",
                    "E-SIGNATURE": "DEMO",
                    "SIG 2": "",
                    "Notes": "Fictional opening balance",
                }
            ]
            for name, details in PATIENTS.items()
        },
    )
    st.session_state.setdefault("medlog_last_transcript", "")


def get_client() -> OpenAI:
    if not API_KEY:
        st.error("OPENAI_API_KEY is not configured.")
        st.stop()
    return OpenAI(api_key=API_KEY)


def transcribe_audio(client: OpenAI, audio: Any) -> str:
    audio.seek(0)
    result = client.audio.transcriptions.create(
        model=TRANSCRIBE_MODEL,
        file=(getattr(audio, "name", "med-log-entry.wav"), audio.getvalue(), "audio/wav"),
        prompt=(
            "Spravato medication log dictation. Expect patient names, dates, "
            "84 mg or 56 mg doses, kit quantities, tracking or lot numbers, "
            "staff initials, and short notes."
        ),
    )
    return str(result.text).strip()


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("No structured medication-log entry was returned.")
    return json.loads(cleaned[start : end + 1])


def interpret_transcript(client: OpenAI, transcript: str) -> dict[str, Any]:
    response = client.responses.create(
        model=MODEL,
        instructions=EXTRACTION_INSTRUCTIONS,
        input=transcript,
    )
    parsed = _json_object(response.output_text or "")
    if parsed.get("patient_name") not in PATIENTS:
        parsed["patient_name"] = None
    return parsed


def current_balance(patient: str) -> int:
    rows = st.session_state["medlog_rows"].get(patient, [])
    if not rows:
        return int(PATIENTS[patient]["opening_balance"])
    return int(rows[-1]["# OF KITS ON HAND"])


def expected_balance(patient: str, received: int, returned: int, used: int) -> int:
    return current_balance(patient) + received - returned - used


def normalize_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if value:
        try:
            return datetime.strptime(str(value), "%m/%d/%Y").date()
        except ValueError:
            pass
    return date.today()


def clear_pending() -> None:
    st.session_state["medlog_pending"] = {}
    st.session_state["medlog_last_transcript"] = ""


apply_trimera_theme()
require_auth(APP_TITLE, "Internal Trimera Health medication-tracking tool")
initialize_state()
render_topbar()

with st.sidebar:
    sidebar_label("Quick actions")
    if st.button("Start a new entry", use_container_width=True):
        clear_pending()
        st.rerun()
    if st.button("Sign out", use_container_width=True):
        logout_user()
    sidebar_model(MODEL)
    sidebar_reminder(
        "Review before writing",
        "Confirm the patient, lot number, quantities, signatures, and physical count before submission.",
    )

page_header(
    "medlog",
    APP_TITLE,
    "Dictate a natural medication-log entry, review the structured row, and approve it before submission.",
)

st.info(
    "Practice mode is active with fictional patients. Nothing on this page currently writes to Teams or the live medication log."
)

patient = st.selectbox(
    "Current fictional patient sheet",
    list(PATIENTS),
    index=list(PATIENTS).index(st.session_state["medlog_patient"]),
    help='You can also say “go to Bart Simpson” in the recording.',
)
st.session_state["medlog_patient"] = patient

st.markdown("### Speak or type the entry")
st.caption(
    'Example: “Go to Lisa Simpson. July 21, 84 milligrams, one kit used, lot LS 900, four kits on hand, signature MJ, new line.”'
)
audio = st.audio_input("Record medication-log entry")
typed = st.text_area(
    "Typed practice entry",
    value=st.session_state["medlog_last_transcript"],
    placeholder="Type the same natural-language entry here if you are testing without a microphone.",
    height=88,
)

col_transcribe, col_interpret = st.columns(2)
with col_transcribe:
    transcribe_clicked = st.button(
        "Transcribe recording",
        type="primary",
        use_container_width=True,
        disabled=audio is None,
    )
with col_interpret:
    interpret_clicked = st.button(
        "Interpret typed entry",
        use_container_width=True,
        disabled=not typed.strip(),
    )

transcript_to_interpret = ""
if transcribe_clicked and audio is not None:
    try:
        with st.spinner("Transcribing medication-log dictation..."):
            transcript_to_interpret = transcribe_audio(get_client(), audio)
        st.session_state["medlog_last_transcript"] = transcript_to_interpret
    except Exception as exc:
        st.error(f"The recording could not be transcribed: {exc}")
elif interpret_clicked:
    transcript_to_interpret = typed.strip()
    st.session_state["medlog_last_transcript"] = transcript_to_interpret

if transcript_to_interpret:
    try:
        with st.spinner("Matching the patient and organizing the proposed row..."):
            parsed = interpret_transcript(get_client(), transcript_to_interpret)
        if parsed.get("patient_name"):
            st.session_state["medlog_patient"] = parsed["patient_name"]
        st.session_state["medlog_pending"] = parsed
        st.rerun()
    except Exception as exc:
        st.error(f"The entry could not be interpreted: {exc}")

pending = st.session_state["medlog_pending"]
if st.session_state["medlog_last_transcript"]:
    st.markdown("**Transcript**")
    st.write(st.session_state["medlog_last_transcript"])

st.markdown("### Review proposed row")
review_patient = st.selectbox(
    "Patient",
    list(PATIENTS),
    index=list(PATIENTS).index(pending.get("patient_name") or st.session_state["medlog_patient"]),
    key="medlog_review_patient",
)

date_col, received_col, returned_col, used_col, onhand_col = st.columns(5)
with date_col:
    entry_date = st.date_input("Date", value=normalize_date(pending.get("date")))
with received_col:
    kits_received = st.number_input("Kits received", min_value=0, step=1, value=int(pending.get("kits_received") or 0))
with returned_col:
    kits_returned = st.number_input("Kits returned", min_value=0, step=1, value=int(pending.get("kits_returned") or 0))
with used_col:
    kits_used = st.number_input("Kits used", min_value=0, step=1, value=int(pending.get("kits_used") or 0))

calculated_on_hand = expected_balance(review_patient, kits_received, kits_returned, kits_used)
spoken_on_hand = pending.get("kits_on_hand")
with onhand_col:
    kits_on_hand = st.number_input(
        "Kits on hand",
        min_value=0,
        step=1,
        value=int(spoken_on_hand if spoken_on_hand is not None else max(calculated_on_hand, 0)),
    )

lot_col, sig_col, sig2_col = st.columns(3)
with lot_col:
    lot_number = st.text_input("Tracking or lot #", value=str(pending.get("lot_number") or ""))
with sig_col:
    e_signature = st.text_input("E-signature", value=str(pending.get("e_signature") or ""))
with sig2_col:
    second_signature = st.text_input("Signature 2", value=str(pending.get("second_signature") or ""))

dose = pending.get("dose_mg")
notes_default = str(pending.get("notes") or "")
if dose and f"{dose} mg" not in notes_default.lower():
    notes_default = f"Dose: {dose} mg" + (f"; {notes_default}" if notes_default else "")
notes = st.text_input(
    "Notes",
    value=notes_default,
    help="The current workbook has no separate dose column, so a dictated dose is retained here.",
)

if calculated_on_hand < 0:
    st.error("The calculated balance is negative. Correct the quantities before adding this row.")
elif kits_on_hand != calculated_on_hand:
    st.warning(
        f"Inventory mismatch: the prior balance and quantities calculate to {calculated_on_hand}, "
        f"but the proposed physical count is {kits_on_hand}. Verify before proceeding."
    )
else:
    st.success(f"Inventory reconciles at {calculated_on_hand} kits on hand.")

required_ready = bool(lot_number.strip() and e_signature.strip()) and calculated_on_hand >= 0
approve_col, push_col = st.columns(2)
with approve_col:
    if st.button(
        "Approve and add practice row",
        type="primary",
        use_container_width=True,
        disabled=not required_ready,
    ):
        row = {
            "DATE": entry_date.strftime("%m/%d/%Y"),
            "# OF KITS RECEIVED": kits_received,
            "# OF KITS RETURNED": kits_returned,
            "# OF KITS USED": kits_used,
            "# OF KITS ON HAND": kits_on_hand,
            "TRACKING OR LOT #": lot_number.strip(),
            "E-SIGNATURE": e_signature.strip(),
            "SIG 2": second_signature.strip(),
            "Notes": notes.strip(),
        }
        st.session_state["medlog_rows"][review_patient].append(row)
        st.session_state["medlog_patient"] = review_patient
        clear_pending()
        st.success(f"Practice row added to {review_patient}. No live record was changed.")
        st.rerun()
with push_col:
    st.button(
        "Push approved row to Teams",
        use_container_width=True,
        disabled=not TEAMS_WRITE_ENABLED,
        help="This remains disabled until the Microsoft connector is configured and validated against a test workbook.",
    )

if not TEAMS_WRITE_ENABLED:
    st.caption(
        "Teams submission is intentionally locked. Microsoft application approval and a test-workbook connection are required before live writes can be enabled."
    )

st.markdown(f"### {review_patient} — fictional practice sheet")
rows = st.session_state["medlog_rows"][review_patient]
st.dataframe(pd.DataFrame(rows, columns=LOG_COLUMNS), use_container_width=True, hide_index=True)

csv_data = pd.DataFrame(rows, columns=LOG_COLUMNS).to_csv(index=False).encode("utf-8")
st.download_button(
    "Download this fictional sheet as CSV",
    data=csv_data,
    file_name=f"{review_patient.replace(' ', '_')}_practice_med_log.csv",
    mime="text/csv",
)

st.caption(
    f"Practice entry prepared by {current_user_email() or 'authenticated staff member'}. "
    "Production submissions will also record the authenticated user and server timestamp."
)
