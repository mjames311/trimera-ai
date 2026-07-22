"""Voice-assisted Spravato medication log with a controlled Google Sheets push."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession
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
GOOGLE_SHEETS_WRITE_ENABLED = (
    os.getenv("TRIMERA_MED_LOG_GOOGLE_WRITE_ENABLED", "").lower() == "true"
)
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("TRIMERA_MED_LOG_GOOGLE_SHEET_ID", "").strip()
NON_PATIENT_TABS = {
    "E-Med Log",
    "Pharmacies",
    "Inactive Patients",
    "E-Med Log (2)",
    "Cardinal-Besse B&B",
}
PATIENTS: dict[str, dict[str, Any]] = {}

LOG_COLUMNS = [
    "DATE",
    "# OF KITS RECEIVED",
    "# OF KITS RETURNED / DISPOSED",
    "# OF KITS USED",
    "# OF KITS ON HAND",
    "TRACKING OR LOT #",
    "Notes",
]

EXTRACTION_INSTRUCTIONS = """
You convert one continuous staff dictation into a BATCH of proposed Spravato
medication-log entries. The recording may contain several patients. Start a new
entry whenever the speaker names another patient or says "go to [patient]'s
sheet/chart." Do not merge facts from different patients.

The application supplies the exact known patient-tab names below. Match the
spoken patient to one of those names; do not invent a patient.

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

The lot_number value must always be a string. When one delivery contains kits
with different explicitly spoken lot numbers, preserve every lot in spoken
order and join them with exactly " / ". For example, "two kits arrived with
lot numbers LOT-A and LOT-B" must produce lot_number="LOT-A / LOT-B". Do not
discard or deduplicate either identifier.

Set kits_on_hand_is_physical_count=true only when the speaker explicitly states
an ending physical inventory count, such as "the physical count is nine," "nine
kits remain," or "I count nine kits on hand." A phrase such as "one kit already
on hand was used" describes where the used kit came from; it is not an ending
physical count. In that case set kits_on_hand=null and
kits_on_hand_is_physical_count=false.

Return only valid JSON in this exact outer shape:
{"entries": [ ... ]}

Every entry must contain these keys:
patient_name, date, kits_received, kits_returned, kits_used, kits_on_hand,
lot_number, use_existing_on_hand_lot, same_lot_as_previous,
kits_on_hand_is_physical_count, dose_mg, notes.
Use null only for information that cannot be safely derived. Use integers for
kit counts and format dates as MM/DD/YYYY. Do not include signatures; the
application identifies the authenticated staff member. Do not turn an earlier
patient's facts into a later patient's notes.
""".strip()


def initialize_state() -> None:
    state_source = GOOGLE_SHEETS_SPREADSHEET_ID or "unconfigured"
    if st.session_state.get("medlog_state_source") != state_source:
        first_patient = next(iter(PATIENTS))
        st.session_state["medlog_state_source"] = state_source
        st.session_state["medlog_patient"] = first_patient
        st.session_state["medlog_queue"] = []
        st.session_state["medlog_rows"] = {
            name: [
                {
                    "DATE": details["opening_date"],
                    "# OF KITS RECEIVED": 0,
                    "# OF KITS RETURNED / DISPOSED": 0,
                    "# OF KITS USED": 0,
                    "# OF KITS ON HAND": details["opening_balance"],
                    "TRACKING OR LOT #": details["opening_lot"],
                    "Notes": "Opening balance from prior medication log",
                }
            ]
            for name, details in PATIENTS.items()
        }
        st.session_state["medlog_on_hand_lot"] = {
            name: details["opening_lot"] for name, details in PATIENTS.items()
        }
        st.session_state["medlog_last_transcript"] = ""


def _integer_inventory(value: Any) -> int | None:
    match = re.match(r"\s*(-?\d+)", str(value or ""))
    return int(match.group(1)) if match else None


@st.cache_data(ttl=60, show_spinner=False)
def load_patients_from_google_sheet(spreadsheet_id: str) -> dict[str, dict[str, Any]]:
    """Load patient tabs and their latest recorded balances from Google Sheets."""
    if not spreadsheet_id:
        raise RuntimeError("The medication-log spreadsheet is not configured.")
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    session = AuthorizedSession(credentials)
    base_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    metadata = session.get(
        base_url,
        params={"fields": "sheets.properties(sheetId,title,index)"},
        timeout=30,
    )
    metadata.raise_for_status()
    tab_names = [
        sheet["properties"]["title"]
        for sheet in sorted(
            metadata.json().get("sheets", []),
            key=lambda item: item["properties"].get("index", 0),
        )
        if sheet["properties"]["title"] not in NON_PATIENT_TABS
    ]
    params: list[tuple[str, str]] = [("majorDimension", "ROWS")]
    params.extend(
        ("ranges", f"'{name.replace(chr(39), chr(39) * 2)}'!A:G")
        for name in tab_names
    )
    values_response = session.get(
        f"{base_url}/values:batchGet", params=params, timeout=60
    )
    values_response.raise_for_status()
    value_ranges = values_response.json().get("valueRanges", [])
    patients: dict[str, dict[str, Any]] = {}
    for name, value_range in zip(tab_names, value_ranges):
        rows = value_range.get("values", [])
        latest_index = next(
            (
                index
                for index in range(len(rows) - 1, -1, -1)
                if len(rows[index]) > 4
                and _integer_inventory(rows[index][4]) is not None
            ),
            None,
        )
        if latest_index is None:
            continue
        latest_row = rows[latest_index]
        lot = next(
            (
                str(rows[index][5]).strip()
                for index in range(latest_index, -1, -1)
                if len(rows[index]) > 5 and str(rows[index][5]).strip()
            ),
            "",
        )
        patients[name] = {
            "opening_balance": _integer_inventory(latest_row[4]),
            "opening_lot": lot,
            "opening_date": str(latest_row[0] or "Prior log").strip(),
            "sheet_tab": name,
        }
    if not patients:
        raise RuntimeError("No patient tabs with recorded inventory were found.")
    return patients


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


def _normalized_lot_number(raw_lot: Any) -> str:
    """Return one display value while preserving every explicitly supplied lot."""
    if isinstance(raw_lot, list):
        return " / ".join(
            str(part).strip() for part in raw_lot if str(part).strip()
        )
    return str(raw_lot or "").strip()


def interpret_transcript(client: OpenAI, transcript: str) -> list[dict[str, Any]]:
    patient_names = "\n".join(f"- {name}" for name in PATIENTS)
    response = client.responses.create(
        model=MODEL,
        instructions=(
            EXTRACTION_INSTRUCTIONS
            + f"\n\nKNOWN PATIENT TABS:\n{patient_names}"
            + f"\n\nCURRENT DATE: {date.today().strftime('%m/%d/%Y')}"
        ),
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
        explicit_lot = _normalized_lot_number(entry.get("lot_number"))
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
        raise ValueError("No known patient tabs were identified in the recording.")
    balances = {patient: current_balance(patient) for patient in PATIENTS}
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
            bool(entry.get("kits_on_hand_is_physical_count"))
            and spoken_on_hand is not None
            and int(spoken_on_hand) != calculated
        )
        recorded_on_hand = (
            int(spoken_on_hand)
            if entry.get("kits_on_hand_is_physical_count")
            and spoken_on_hand is not None
            else calculated
        )
        entry["kits_on_hand"] = recorded_on_hand
        balances[patient] = recorded_on_hand
    return cleaned


def current_balance(patient: str) -> int:
    rows = st.session_state["medlog_rows"].get(patient, [])
    if not rows:
        return int(PATIENTS[patient]["opening_balance"])
    return int(rows[-1]["# OF KITS ON HAND"])


def clear_pending() -> None:
    st.session_state["medlog_queue"] = []
    st.session_state["medlog_last_transcript"] = ""


def google_sheet_push_configured() -> bool:
    return GOOGLE_SHEETS_WRITE_ENABLED and bool(GOOGLE_SHEETS_SPREADSHEET_ID)


def _google_sheet_values(row: dict[str, Any]) -> list[list[Any]]:
    """Map one reviewed UI row to the normalized seven-column patient log."""
    return [[
        row["DATE"],
        row["# OF KITS RECEIVED"],
        row["# OF KITS RETURNED / DISPOSED"],
        row["# OF KITS USED"],
        row["# OF KITS ON HAND"],
        row["TRACKING OR LOT #"],
        row["Notes"],
    ]]


def push_batch_to_google_sheet(batch_rows: list[dict[str, Any]]) -> int:
    """Append reviewed rows to their patient tabs using the Cloud Run identity."""
    if not google_sheet_push_configured():
        raise RuntimeError("The Google Sheets test-log connection is not enabled.")
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    session = AuthorizedSession(credentials)
    updated_rows = 0
    for row in batch_rows:
        patient = str(row["Patient"])
        sheet_tab = PATIENTS[patient]["sheet_tab"]
        target_range = quote(f"'{sheet_tab}'!A:G", safe="")
        url = (
            "https://sheets.googleapis.com/v4/spreadsheets/"
            f"{GOOGLE_SHEETS_SPREADSHEET_ID}/values/{target_range}:append"
        )
        response = session.post(
            url,
            params={
                "valueInputOption": "USER_ENTERED",
                "insertDataOption": "INSERT_ROWS",
            },
            json={"majorDimension": "ROWS", "values": _google_sheet_values(row)},
            timeout=30,
        )
        response.raise_for_status()
        updated_rows += int(response.json().get("updates", {}).get("updatedRows", 0))
    if updated_rows != len(batch_rows):
        raise RuntimeError(
            f"Google Sheets reported {updated_rows} written rows for a {len(batch_rows)}-row batch."
        )
    return updated_rows


apply_trimera_theme()
require_auth(APP_TITLE, "Internal Trimera Health medication-tracking tool")
try:
    PATIENTS = load_patients_from_google_sheet(GOOGLE_SHEETS_SPREADSHEET_ID)
except Exception as exc:
    st.error(f"The configured medication log could not be loaded: {exc}")
    st.stop()
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
        "Confirm the patient, lot number, quantities, and physical count before submission.",
    )

page_header(
    "medlog",
    APP_TITLE,
    "Dictate a natural medication-log entry, review the structured row, and approve it before submission.",
)

st.info(
    "Test mode uses the patient tabs and latest balances in the configured restricted Google Sheet."
)

st.markdown("### Speak or type the entry")
st.caption(
    "One recording may contain several patients. Name each patient, then describe kits received, returned, used, the lot number, and any physical count."
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
    st.markdown("**Review proposed changes**")
    batch_rows = [
        {
            "Patient": entry["patient_name"],
            "DATE": entry["date"],
            "# OF KITS RECEIVED": entry["kits_received"],
            "# OF KITS RETURNED / DISPOSED": entry["kits_returned"],
            "# OF KITS USED": entry["kits_used"],
            "# OF KITS ON HAND": entry["kits_on_hand"],
            "TRACKING OR LOT #": entry.get("lot_number") or "NEEDS LOT",
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
        st.warning(
            "The spoken physical count did not match calculated inventory for: "
            + ", ".join(mismatches)
            + ". The spoken physical count will be recorded; review it before approval."
        )
    if negative_balances:
        st.error("The proposed transaction would create negative inventory for: " + ", ".join(negative_balances) + ".")

    batch_ready = not missing_lots and not negative_balances
    practice_col, push_col = st.columns(2)
    with practice_col:
        if st.button(
            "Approve batch and add to practice log",
            type="primary",
            use_container_width=True,
            disabled=not batch_ready,
        ):
            for entry, row in zip(queue, batch_rows):
                practice_row = row.copy()
                patient_name = practice_row.pop("Patient")
                st.session_state["medlog_rows"][patient_name].append(practice_row)
                if (
                    (entry["kits_received"] > 0 or entry["kits_used"] > 0)
                    and entry.get("lot_number")
                ):
                    st.session_state["medlog_on_hand_lot"][patient_name] = entry["lot_number"]
            clear_pending()
            st.success("The entire fictional batch was added. No live record was changed.")
            st.rerun()
    with push_col:
        push_clicked = st.button(
            "Push approved batch to Google test log",
            use_container_width=True,
            disabled=not (google_sheet_push_configured() and batch_ready),
            help="Appends the reviewed rows to the configured restricted Google Sheet.",
        )
        if push_clicked:
            try:
                with st.spinner("Writing the approved batch to the Google test log..."):
                    written = push_batch_to_google_sheet(batch_rows)
                clear_pending()
                st.success(f"Pushed {written} approved row(s) to the Google test log.")
            except Exception as exc:
                st.error(f"The batch was not written: {exc}")

if not google_sheet_push_configured():
    st.caption(
        "Google submission is locked until the test spreadsheet ID and explicit write flag are configured in Cloud Run."
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

st.caption("Practice mode only. Review every proposed entry before writing it to the test log.")
