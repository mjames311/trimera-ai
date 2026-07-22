"""Voice-assisted Spravato medication log with a safe practice mode.

The page intentionally does not write to Microsoft 365 until a separately
configured Teams/SharePoint connector is enabled and tested.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
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
    "Alba": {"opening_balance": 9},
    "Ayers": {"opening_balance": 5},
    "Armstrong": {"opening_balance": 7},
}

LOG_COLUMNS = [
    "DATE",
    "# OF KITS RECEIVED",
    "# OF KITS RETURNED",
    "# OF KITS USED",
    "# OF KITS ON HAND",
    "TRACKING OR LOT #",
    "E-SIGNATURE",
    "Notes",
]

EXTRACTION_INSTRUCTIONS = """
You convert one continuous staff dictation into a BATCH of proposed Spravato
medication-log entries. The recording may contain several patients. Start a new
entry whenever the speaker names another patient or says "go to [patient]'s
sheet/chart." Do not merge facts from different patients.

Known fictional practice patients:
- Alba
- Ayers
- Armstrong

Interpret ordinary English rather than requiring column names. "Used,"
"administered," and "gave" are equivalent. "Received" and "a shipment
arrived" are equivalent. "Returned" and "sent back" are equivalent. If the
speaker does not mention kits received, returned, or used for an entry, use 0
for that quantity. "Today" means the current date supplied below. If the
speaker corrects an earlier statement (for example, "one kit—no, make that two"),
the latest explicit correction controls and the superseded value must not be
retained.

If the speaker says a kit was "on hand," "already on hand," or from existing
stock, set use_existing_on_hand_lot=true. Do not invent the lot identifier; the
application will obtain the patient's currently recorded on-hand lot. If the
speaker says "same lot" or "same tracking number," set
same_lot_as_previous=true so the application can reuse the prior resolved entry
in this batch. Preserve explicitly spoken identifiers, removing spaces between
individually dictated letters or digits.

Return only valid JSON in this exact outer shape:
{"entries": [ ... ]}

Every entry must contain these keys:
patient_name, date, kits_received, kits_returned, kits_used, kits_on_hand,
lot_number, use_existing_on_hand_lot, same_lot_as_previous, dose_mg, notes.
Use null only for information that cannot be safely derived. Use integers for
kit counts and format dates as MM/DD/YYYY. Do not include signatures; the
application identifies the authenticated staff member. Do not turn an earlier
patient's facts into a later patient's notes.
""".strip()


def initialize_state() -> None:
    st.session_state.setdefault("medlog_patient", "Alba")
    st.session_state.setdefault("medlog_queue", [])
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
                    "TRACKING OR LOT #": f"{name.split()[0].upper()}-ON-HAND-001",
                    "E-SIGNATURE": "DEMO",
                    "Notes": "Fictional opening balance",
                }
            ]
            for name, details in PATIENTS.items()
        },
    )
    st.session_state.setdefault(
        "medlog_on_hand_lot",
        {name: f"{name.split()[0].upper()}-ON-HAND-001" for name in PATIENTS},
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


def interpret_transcript(client: OpenAI, transcript: str) -> list[dict[str, Any]]:
    response = client.responses.create(
        model=MODEL,
        instructions=EXTRACTION_INSTRUCTIONS + f"\n\nCURRENT DATE: {date.today().strftime('%m/%d/%Y')}",
        input=transcript,
    )
    parsed = _json_object(response.output_text or "")
    entries = parsed.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("No patient entries were identified in the recording.")
    cleaned = []
    previous_lot = ""
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("patient_name") not in PATIENTS:
            continue
        patient = entry["patient_name"]
        entry["kits_received"] = int(entry.get("kits_received") or 0)
        entry["kits_returned"] = int(entry.get("kits_returned") or 0)
        entry["kits_used"] = int(entry.get("kits_used") or 0)
        entry["date"] = entry.get("date") or date.today().strftime("%m/%d/%Y")
        explicit_lot = str(entry.get("lot_number") or "").strip()
        if entry.get("same_lot_as_previous") and previous_lot:
            explicit_lot = previous_lot
        elif not explicit_lot and (
            entry.get("use_existing_on_hand_lot") or entry["kits_used"] > 0
        ):
            explicit_lot = st.session_state["medlog_on_hand_lot"].get(patient, "")
        entry["lot_number"] = explicit_lot
        entry["notes"] = str(entry.get("notes") or "No additional notes").strip()
        if explicit_lot:
            previous_lot = explicit_lot
        cleaned.append(entry)
    if not cleaned:
        raise ValueError("No known fictional patients were identified in the recording.")
    balances = {patient: current_balance(patient) for patient in PATIENTS}
    signature = current_user_email()
    for entry in cleaned:
        patient = entry["patient_name"]
        calculated = (
            balances[patient]
            + entry["kits_received"]
            - entry["kits_returned"]
            - entry["kits_used"]
        )
        spoken_on_hand = entry.get("kits_on_hand")
        entry["inventory_mismatch"] = (
            spoken_on_hand is not None and int(spoken_on_hand) != calculated
        )
        entry["kits_on_hand"] = calculated
        entry["e_signature"] = signature
        balances[patient] = calculated
    return cleaned


def current_balance(patient: str) -> int:
    rows = st.session_state["medlog_rows"].get(patient, [])
    if not rows:
        return int(PATIENTS[patient]["opening_balance"])
    return int(rows[-1]["# OF KITS ON HAND"])


def clear_pending() -> None:
    st.session_state["medlog_queue"] = []
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
        "Confirm the patient, lot number, quantities, signature, and physical count before submission.",
    )

page_header(
    "medlog",
    APP_TITLE,
    "Dictate a natural medication-log entry, review the structured row, and approve it before submission.",
)

st.info(
    "Practice mode is active with fictional patients. Nothing on this page currently writes to Teams or the live medication log."
)

st.markdown("### Speak or type the entry")
st.caption(
    'One recording may contain several patients. Example: “Go to Alba. Today one kit was received and one kit already on hand was used. Go to Ayers. Today two kits were used from that same lot.”'
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
        with st.spinner("Separating patients and organizing the proposed rows..."):
            entries = interpret_transcript(get_client(), transcript_to_interpret)
        st.session_state["medlog_patient"] = entries[0]["patient_name"]
        st.session_state["medlog_queue"] = entries
        st.rerun()
    except Exception as exc:
        st.error(f"The entry could not be interpreted: {exc}")

queue = st.session_state["medlog_queue"]
if st.session_state["medlog_last_transcript"]:
    st.markdown("**Transcript**")
    st.write(st.session_state["medlog_last_transcript"])
if queue:
    st.markdown("**Batch detected from this recording**")
    batch_rows = [
        {
            "Patient": entry["patient_name"],
            "DATE": entry["date"],
            "# OF KITS RECEIVED": entry["kits_received"],
            "# OF KITS RETURNED": entry["kits_returned"],
            "# OF KITS USED": entry["kits_used"],
            "# OF KITS ON HAND": entry["kits_on_hand"],
            "TRACKING OR LOT #": entry.get("lot_number") or "NEEDS LOT",
            "E-SIGNATURE": entry["e_signature"],
            "Notes": (
                f"Dose: {entry['dose_mg']} mg; {entry['notes']}"
                if entry.get("dose_mg")
                else entry["notes"]
            ),
        }
        for entry in queue
    ]
    st.dataframe(
        pd.DataFrame(batch_rows),
        use_container_width=True,
        hide_index=True,
    )
    missing_lots = [entry["patient_name"] for entry in queue if not entry.get("lot_number")]
    mismatches = [entry["patient_name"] for entry in queue if entry.get("inventory_mismatch")]
    negative_balances = [entry["patient_name"] for entry in queue if entry["kits_on_hand"] < 0]
    if missing_lots:
        st.error("A lot number could not be resolved for: " + ", ".join(missing_lots) + ". Correct the dictation and interpret it again.")
    if mismatches:
        st.warning("The spoken physical count did not match calculated inventory for: " + ", ".join(mismatches) + ".")
    if negative_balances:
        st.error("The proposed transaction would create negative inventory for: " + ", ".join(negative_balances) + ".")

    batch_ready = not missing_lots and not mismatches and not negative_balances
    practice_col, push_col = st.columns(2)
    with practice_col:
        if st.button(
            "Add entire batch to practice log",
            type="primary",
            use_container_width=True,
            disabled=not batch_ready,
        ):
            for entry, row in zip(queue, batch_rows):
                patient_name = row.pop("Patient")
                st.session_state["medlog_rows"][patient_name].append(row)
                if entry["kits_used"] > 0 and entry.get("lot_number"):
                    st.session_state["medlog_on_hand_lot"][patient_name] = entry["lot_number"]
            clear_pending()
            st.success("The entire fictional batch was added. No live record was changed.")
            st.rerun()
    with push_col:
        st.button(
            "Push batch to Teams test log",
            use_container_width=True,
            disabled=not (TEAMS_WRITE_ENABLED and batch_ready),
            help="This remains disabled until the Microsoft connector is configured and validated against a test workbook.",
        )

if not TEAMS_WRITE_ENABLED:
    st.caption(
        "Teams submission is intentionally locked. Microsoft application approval and a test-workbook connection are required before live writes can be enabled."
    )

st.markdown("### Fictional practice log")
all_rows = [
    {"Patient": patient_name, **row}
    for patient_name, patient_rows in st.session_state["medlog_rows"].items()
    for row in patient_rows
]
st.dataframe(pd.DataFrame(all_rows), use_container_width=True, hide_index=True)

csv_data = pd.DataFrame(all_rows).to_csv(index=False).encode("utf-8")
st.download_button(
    "Download the complete fictional log as CSV",
    data=csv_data,
    file_name="Trimera_Spravato_Med_Log_Practice.csv",
    mime="text/csv",
)

st.caption(
    f"Practice entry prepared by {current_user_email() or 'authenticated staff member'}. "
    "Production submissions will also record the authenticated user and server timestamp."
)
