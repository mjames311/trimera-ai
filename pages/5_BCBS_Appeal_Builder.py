import io
import json
import os
import re
import zipfile
from copy import deepcopy
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd
import streamlit as st
from openai import OpenAI
from pypdf import PdfReader, PdfWriter
from rapidfuzz import fuzz
from auth import logout_user, require_auth
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from theme import apply_trimera_theme, page_header, render_topbar, sidebar_label, sidebar_model, sidebar_reminder


st.set_page_config(
    page_title="BCBS Appeal Packet Builder",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "BCBS Appeal Packet Builder"
API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
DEFAULT_APPEAL_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1] / "Assets" / "APPEAL.template.docx"
)
AMA_GUIDELINES_PATH = (
    Path(__file__).resolve().parents[1]
    / "Assets"
    / "2023-e-m-descriptors-guidelines.pdf"
)
CMS_GUIDELINES_PATH = (
    Path(__file__).resolve().parents[1]
    / "reference"
    / "mln006764_evaluation_management_services.pdf"
)
SECOND_LEVEL_DEFAULT_ADDRESS = (
    "Blue Cross and Blue Shield of Texas\n"
    "Appeal Coordinator\n"
    "PO Box 660044\n"
    "Dallas, TX 75266-0044"
)

AMOUNT_TO_CODE = {
    25.00: "G2211",
    100.00: "90833",
    150.00: "90836",
    200.00: "99214",
    250.00: "99215",
    500.00: "99417 x5",
}

E_M_CODES = {"99214", "99215"}

EXPECTED_ALLOWED_BY_CODE = {
    "99214": 116.47,
    "99215": 155.96,
    "90833": 67.21,
    "90836": 88.54,
    "G2211": 13.51,
    "99417 x5": 193.57,
}

APPEAL_BODY_1 = (
    "On the date of service listed above, the CPT E/M code for the service "
    "identified above was reported with the original CPT code shown above. "
    "Blue Cross Blue Shield of Texas has inappropriately down coded the CPT "
    "E/M code submitted and changed it to the code shown above, resulting in "
    "an inappropriate reduction of payment for delivered medical care."
)

APPEAL_BODY_2 = (
    "Under Blue Cross Blue Shield of Texas medical review guidelines, the "
    "payer follows the 2021 CMS E/M coding guidelines. The undersigned provider "
    "has billed according to the 2021 CMS E/M guidelines accurately. Down "
    "coding of CPT E/M codes is not appropriate without review of medical "
    "record documentation. The American Medical Association (AMA) strongly "
    "opposes automatic downcoding and states:"
)

TMA_TITLE = "65.015, Automatic Downcoding of Claims:"

TMA_1 = (
    "The Texas Medical Association vigorously opposes health plans exclusively "
    "relying on software, algorithms, or other methodologies excluding review "
    "of the patient's medical record to deny or downcode evaluation and "
    "management (E/M) services, other than correct coding protocol denials, "
    "based solely on the CPT/Healthcare Common Procedure Coding System (HCPCS) "
    "codes, ICD-10 codes, and/or modifiers submitted on the claim;"
)

TMA_2 = (
    "TMA supports that, after review of the patient's medical record and "
    "determination that a lower level of E/M code is warranted, the explanation "
    "of benefits, remittance advice documents, or other claim adjudication "
    "notices provide notice that clearly indicates a service was downcoded "
    "using the proper claim adjustment reason codes and/or remittance advice "
    "remark codes;"
)

TMA_3 = (
    "TMA advocates for legislation to provide transparency and prohibit "
    "automated denials, other than National Correct Coding Initiative denials, "
    "or downcoding of E/M services based solely on the CPT/HCPCS codes, ICD-10 "
    "codes, or modifiers submitted on the claim. (Res. 403 2024)"
)

APPEAL_CLOSE = (
    "The appropriateness of the reported level of the original CPT E/M code "
    "identified above is clearly documented within the patient's chart "
    "(attached) and should be recognized by Blue Cross Blue Shield of Texas. "
    "Based on the circumstances of this case, we are requesting that the "
    "original CPT E/M code be paid in full and not be inappropriately downcoded."
)

APPEAL_THANKS = (
    "Thank you for your reconsideration. Please contact my office should you "
    "have any questions regarding this claim."
)



XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

ET.register_namespace("", XLSX_NS)
ET.register_namespace("r", REL_NS)


def excel_serial(value: Any) -> float:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Could not convert date: {value}")
    origin = pd.Timestamp("1899-12-30")
    return float((parsed.normalize() - origin).days)


def column_letters(cell_ref: str) -> str:
    match = re.match(r"([A-Z]+)", cell_ref or "")
    return match.group(1) if match else ""


def cell_text(
    cell: ET.Element,
    shared_strings: list[str],
) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find(f"{{{XLSX_NS}}}v")

    if cell_type == "inlineStr":
        texts = cell.findall(f".//{{{XLSX_NS}}}t")
        return "".join(node.text or "" for node in texts)

    if value_node is None:
        return ""

    raw = value_node.text or ""

    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw

    return raw


def read_shared_strings(
    archive: zipfile.ZipFile,
) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = []

    for item in root.findall(f"{{{XLSX_NS}}}si"):
        texts = item.findall(f".//{{{XLSX_NS}}}t")
        strings.append("".join(node.text or "" for node in texts))

    return strings


def find_sheet_path(
    archive: zipfile.ZipFile,
    sheet_name: str,
) -> str:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))

    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
    }

    for sheet in workbook_root.findall(
        f".//{{{XLSX_NS}}}sheet"
    ):
        if sheet.attrib.get("name") != sheet_name:
            continue

        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        target = rel_targets.get(rel_id, "")
        target = target.lstrip("/")

        if target.startswith("xl/"):
            return target

        return f"xl/{target}"

    raise ValueError(f"Worksheet not found: {sheet_name}")


def make_inline_cell(
    ref: str,
    value: str,
    style_id: str | None = None,
) -> ET.Element:
    attributes = {"r": ref, "t": "inlineStr"}
    if style_id is not None:
        attributes["s"] = style_id

    cell = ET.Element(f"{{{XLSX_NS}}}c", attributes)
    inline = ET.SubElement(cell, f"{{{XLSX_NS}}}is")
    text = ET.SubElement(inline, f"{{{XLSX_NS}}}t")

    if value.startswith(" ") or value.endswith(" "):
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    text.text = value
    return cell


def make_number_cell(
    ref: str,
    value: float | int,
    style_id: str | None = None,
) -> ET.Element:
    attributes = {"r": ref}
    if style_id is not None:
        attributes["s"] = style_id

    cell = ET.Element(f"{{{XLSX_NS}}}c", attributes)
    value_node = ET.SubElement(cell, f"{{{XLSX_NS}}}v")
    value_node.text = str(value)
    return cell


def make_formula_cell(
    ref: str,
    formula: str,
    style_id: str | None = None,
) -> ET.Element:
    attributes = {"r": ref}
    if style_id is not None:
        attributes["s"] = style_id

    cell = ET.Element(f"{{{XLSX_NS}}}c", attributes)
    formula_node = ET.SubElement(cell, f"{{{XLSX_NS}}}f")
    formula_node.text = formula
    return cell


def append_claims_to_tracker(
    tracker_bytes: bytes,
    claims_df: pd.DataFrame,
    appeal_date_value: date,
) -> tuple[bytes, pd.DataFrame, list[str]]:
    input_buffer = io.BytesIO(tracker_bytes)
    output_buffer = io.BytesIO()

    added_rows = []
    skipped_existing = []

    with zipfile.ZipFile(input_buffer, "r") as source_archive:
        shared_strings = read_shared_strings(source_archive)
        sheet_path = find_sheet_path(
            source_archive,
            "BCBS Downcoding Tracker",
        )

        sheet_root = ET.fromstring(source_archive.read(sheet_path))
        sheet_data = sheet_root.find(f"{{{XLSX_NS}}}sheetData")

        if sheet_data is None:
            raise ValueError("Tracker worksheet has no sheetData section.")

        rows = sheet_data.findall(f"{{{XLSX_NS}}}row")

        existing_keys = set()
        last_data_row_number = 1
        template_row = None

        for row in rows:
            row_number = int(row.attrib.get("r", "0"))
            values_by_column = {}

            for cell in row.findall(f"{{{XLSX_NS}}}c"):
                col = column_letters(cell.attrib.get("r", ""))
                values_by_column[col] = cell_text(cell, shared_strings)

            patient = normalize_name(values_by_column.get("A", ""))
            dos_raw = values_by_column.get("B", "")
            original_codes = values_by_column.get("C", "").strip()

            if patient:
                last_data_row_number = max(last_data_row_number, row_number)
                template_row = row

                try:
                    dos_key = format_date(float(dos_raw))
                except Exception:
                    dos_key = dos_raw

                existing_keys.add(
                    (
                        patient,
                        dos_key,
                        original_codes.lower().replace(",", " +"),
                    )
                )

        if template_row is None:
            raise ValueError("Could not identify a populated tracker row.")

        template_styles = {}
        for cell in template_row.findall(f"{{{XLSX_NS}}}c"):
            col = column_letters(cell.attrib.get("r", ""))
            template_styles[col] = cell.attrib.get("s")

        next_row = last_data_row_number + 1

        for _, claim in claims_df.iterrows():
            patient = str(claim["Patient"]).strip()
            dos = str(claim["DOS"]).strip()
            original = str(claim["Original CPT(s) Billed"]).replace(", ", " + ")
            paid = str(claim["Downcoded To"]).replace(", ", " + ")

            key = (
                normalize_name(patient),
                dos,
                original.lower().replace(",", " +"),
            )

            if key in existing_keys:
                skipped_existing.append(
                    f"{patient} - {dos} - already in tracker"
                )
                continue

            row_attributes = {
                key: value
                for key, value in template_row.attrib.items()
                if key != "r"
            }
            row_attributes["r"] = str(next_row)
            new_row = ET.Element(
                f"{{{XLSX_NS}}}row",
                row_attributes,
            )

            values = {
                "A": ("text", patient),
                "B": ("number", excel_serial(dos)),
                "C": ("text", original),
                "D": ("text", paid),
                "E": ("number", float(claim["Expected Payment"])),
                "F": ("number", float(claim["Actual Payment"])),
                "G": (
                    "formula",
                    f'IF(OR(E{next_row}="",F{next_row}=""),"",E{next_row}-F{next_row})',
                ),
                "H": ("text", "Yes"),
                "I": ("number", excel_serial(appeal_date_value)),
                "J": ("text", "Pending"),
                "K": ("number", 0),
                "L": (
                    "formula",
                    f'IF(G{next_row}="","",MAX(G{next_row}-K{next_row},0))',
                ),
                "M": ("text", ""),
            }

            for col in "ABCDEFGHIJKLM":
                ref = f"{col}{next_row}"
                kind, value = values[col]
                style_id = template_styles.get(col)

                if kind == "text":
                    cell = make_inline_cell(ref, str(value), style_id)
                elif kind == "number":
                    cell = make_number_cell(ref, value, style_id)
                else:
                    cell = make_formula_cell(ref, str(value), style_id)

                new_row.append(cell)

            sheet_data.append(new_row)
            existing_keys.add(key)

            added_rows.append(
                {
                    "Patient Name": patient,
                    "DOS": dos,
                    "Original CPT(s)": original,
                    "Paid CPT(s)": paid,
                    "Expected Payment": float(claim["Expected Payment"]),
                    "Actual Payment": float(claim["Actual Payment"]),
                    "Appeal Submitted?": "Yes",
                    "Appeal Date": (
                        f"{appeal_date_value.month}/"
                        f"{appeal_date_value.day}/"
                        f"{appeal_date_value.year}"
                    ),
                    "Outcome": "Pending",
                    "Claim Number": claim["Claim Number"],
                    "Source Report(s)": claim.get("Source Report(s)", ""),
                }
            )

            next_row += 1

        dimension = sheet_root.find(f"{{{XLSX_NS}}}dimension")
        if dimension is not None and added_rows:
            dimension.set("ref", f"A1:M{next_row - 1}")

        updated_sheet_xml = ET.tostring(
            sheet_root,
            encoding="utf-8",
            xml_declaration=True,
        )

        workbook_xml = ET.fromstring(source_archive.read("xl/workbook.xml"))
        calc_pr = workbook_xml.find(f"{{{XLSX_NS}}}calcPr")
        if calc_pr is None:
            calc_pr = ET.SubElement(workbook_xml, f"{{{XLSX_NS}}}calcPr")

        calc_pr.set("fullCalcOnLoad", "1")
        calc_pr.set("forceFullCalc", "1")
        calc_pr.set("calcMode", "auto")

        updated_workbook_xml = ET.tostring(
            workbook_xml,
            encoding="utf-8",
            xml_declaration=True,
        )

        with zipfile.ZipFile(
            output_buffer,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as output_archive:
            for item in source_archive.infolist():
                if item.filename == sheet_path:
                    output_archive.writestr(item, updated_sheet_xml)
                elif item.filename == "xl/workbook.xml":
                    output_archive.writestr(item, updated_workbook_xml)
                else:
                    output_archive.writestr(
                        item,
                        source_archive.read(item.filename),
                    )

    return (
        output_buffer.getvalue(),
        pd.DataFrame(added_rows),
        skipped_existing,
    )


def tracker_copy_table(
    claims_df: pd.DataFrame,
    appeal_date_value: date,
    include_header: bool = False,
) -> str:
    columns = [
        "Patient Name",
        "DOS",
        "Original CPT(s)",
        "Paid CPT(s)",
        "Expected Payment",
        "Actual Payment",
        "Loss $",
        "Appeal Submitted?",
        "Appeal Date",
        "Outcome",
        "Recovered $",
        "Net Outstanding Loss",
        "Insurance Type",
    ]

    rows = [columns] if include_header else []

    for _, claim in claims_df.iterrows():
        expected = round(float(claim.get("Expected Payment", 0) or 0), 2)
        actual = round(float(claim.get("Actual Payment", 0) or 0), 2)
        loss = round(expected - actual, 2)

        rows.append(
            [
                str(claim.get("Patient", "")).strip(),
                str(claim.get("DOS", "")).strip(),
                str(claim.get("Original CPT(s) Billed", "")).replace(", ", " + "),
                str(claim.get("Downcoded To", "")).replace(", ", " + "),
                f"{expected:.2f}",
                f"{actual:.2f}",
                f"{loss:.2f}",
                "Yes",
                f"{appeal_date_value.month}/{appeal_date_value.day}/{appeal_date_value.year}",
                "Pending",
                "0.00",
                f"{loss:.2f}",
                "",
            ]
        )

    return "\n".join(
        "\t".join(str(value) for value in row)
        for row in rows
    )

def money_to_float(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).replace("$", "").replace(",", "").strip()
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def normalize_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9 ]+", " ", str(value)).lower()
    return " ".join(value.split())


def filename_safe(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return re.sub(r"_+", "_", value).strip("_")


def availity_appeal_filename(patient: Any, dos: Any, claim_number: Any) -> str:
    """Build an Availity-safe PDF name with no spaces or unsupported punctuation."""
    parsed_dos = pd.to_datetime(dos, errors="coerce")
    date_token = (
        parsed_dos.strftime("%Y%m%d")
        if not pd.isna(parsed_dos)
        else filename_safe(str(dos)) or "UNKNOWN_DATE"
    )
    patient_token = filename_safe(str(patient)) or "UNKNOWN_PATIENT"
    claim_token = filename_safe(str(claim_number)) or "UNKNOWN_CLAIM"
    stem = filename_safe(
        f"BCBS_APPEAL_{patient_token}_{date_token}_{claim_token}"
    )
    return f"{stem}.pdf"


def format_date(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def claim_number_for_appeal(value: Any) -> str:
    claim = str(value).strip()
    if claim.endswith("00"):
        return claim[:-2]
    return claim


def code_sort_key(code: str) -> tuple[int, str]:
    base = code.split()[0]
    if base in {"99214", "99215"}:
        return (0, code)
    if base in {"90833", "90836"}:
        return (1, code)
    if base == "99417":
        return (2, code)
    if base == "G2211":
        return (3, code)
    return (4, code)


def codes_from_group(group: pd.DataFrame) -> list[str]:
    amounts = sorted(
        {
            money_to_float(value)
            for value in group["Billed"].tolist()
            if money_to_float(value) > 0
        }
    )

    codes = []
    for amount in amounts:
        code = AMOUNT_TO_CODE.get(amount)
        if code and code not in codes:
            codes.append(code)

    return sorted(codes, key=code_sort_key)


def downcoded_codes(original_codes: list[str]) -> list[str]:
    result = []
    for code in original_codes:
        base = code.split()[0]
        result.append("99213" if base in E_M_CODES else code)
    return result


def build_claim_summary(report_df: pd.DataFrame) -> pd.DataFrame:
    required = {
        "Patient",
        "Date of Service",
        "Insurance Claim Number",
        "Billed",
        "Note",
    }
    missing = required - set(report_df.columns)
    if missing:
        raise ValueError(
            "The report is missing required columns: "
            + ", ".join(sorted(missing))
        )

    keys = [
        "Patient",
        "Date of Service",
        "Insurance Claim Number",
    ]

    rows = []
    for group_key, group in report_df.groupby(keys, dropna=False):
        patient, dos, claim = group_key
        note_text = " ".join(group["Note"].fillna("").astype(str).tolist())

        if "186:" not in note_text and "Level of care change" not in note_text:
            continue

        original = codes_from_group(group)
        if not any(code.split()[0] in E_M_CODES for code in original):
            continue

        paid_codes = downcoded_codes(original)

        expected_payment = round(
            sum(EXPECTED_ALLOWED_BY_CODE.get(code, 0.0) for code in original),
            2,
        )

        actual_payment = round(
            sum(money_to_float(value) for value in group["Paid"].tolist())
            + sum(
                money_to_float(value)
                for value in group["Patient Responsible"].tolist()
            ),
            2,
        )

        rows.append(
            {
                "Patient": str(patient).strip(),
                "DOS": format_date(dos),
                "Claim Number": claim_number_for_appeal(claim),
                "Original CPT(s) Billed": ", ".join(original),
                "Downcoded To": ", ".join(paid_codes),
                "Original Codes List": original,
                "Expected Payment": expected_payment,
                "Actual Payment": actual_payment,
                "Source Report(s)": ", ".join(
                    sorted(
                        {
                            str(value).strip()
                            for value in group.get(
                                "Source Report",
                                pd.Series(dtype=str),
                            ).dropna().tolist()
                            if str(value).strip()
                        }
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def clean_json_text(value: str) -> str:
    """Remove common Markdown fences before parsing model JSON output."""
    value = (value or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def normalize_report_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize common remittance-report column-name variations."""
    if frame is None or frame.empty:
        return pd.DataFrame()

    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]

    aliases = {
        "patient": "Patient",
        "patient name": "Patient",
        "member": "Patient",
        "member name": "Patient",
        "date of service": "Date of Service",
        "dos": "Date of Service",
        "service date": "Date of Service",
        "insurance claim number": "Insurance Claim Number",
        "claim number": "Insurance Claim Number",
        "claim #": "Insurance Claim Number",
        "claim id": "Insurance Claim Number",
        "billed": "Billed",
        "billed amount": "Billed",
        "charge": "Billed",
        "charge amount": "Billed",
        "paid": "Paid",
        "paid amount": "Paid",
        "payment": "Paid",
        "patient responsible": "Patient Responsible",
        "patient responsibility": "Patient Responsible",
        "patient resp": "Patient Responsible",
        "note": "Note",
        "notes": "Note",
        "remark": "Note",
        "remarks": "Note",
        "status note": "Note",
    }

    rename_map = {}
    for column in frame.columns:
        normalized = re.sub(r"\s+", " ", column.lower()).strip()
        if normalized in aliases:
            rename_map[column] = aliases[normalized]

    frame = frame.rename(columns=rename_map)

    # Combine duplicated normalized columns rather than leaving ambiguous names.
    if frame.columns.duplicated().any():
        combined = {}
        for column in dict.fromkeys(frame.columns):
            matching = frame.loc[:, frame.columns == column]
            combined[column] = matching.bfill(axis=1).iloc[:, 0]
        frame = pd.DataFrame(combined)

    for required_column in ["Paid", "Patient Responsible", "Note"]:
        if required_column not in frame.columns:
            frame[required_column] = 0.0 if required_column != "Note" else ""

    return frame


def read_excel_report(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read every populated worksheet from an uploaded Excel workbook."""
    try:
        workbook = pd.ExcelFile(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(
            f"Could not open Excel report '{filename}'. Save legacy .xls files "
            "as .xlsx and try again. Details: {exc}"
        ) from exc

    frames = []
    for sheet_name in workbook.sheet_names:
        sheet = pd.read_excel(workbook, sheet_name=sheet_name)
        sheet = normalize_report_dataframe(sheet)
        if not sheet.empty:
            sheet["Source Sheet"] = sheet_name
            frames.append(sheet)

    if not frames:
        raise ValueError(f"Excel report '{filename}' did not contain readable rows.")

    return pd.concat(frames, ignore_index=True, sort=False)


def extract_report_with_openai(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
) -> pd.DataFrame:
    """Use OpenAI file analysis to convert PDF or Word reports into rows."""
    if not API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is required to read PDF or Word remittance reports."
        )

    client = OpenAI(api_key=API_KEY)
    uploaded_file = None

    prompt = """
Extract every claim/service line from this BCBS remittance report.
Return ONLY valid JSON with this exact shape:
{
  "rows": [
    {
      "Patient": "patient name",
      "Date of Service": "date",
      "Insurance Claim Number": "claim number",
      "Billed": 0.00,
      "Paid": 0.00,
      "Patient Responsible": 0.00,
      "Note": "all denial, adjustment, remark, and level-of-care text for the line"
    }
  ]
}

Rules:
- Include one object per service line, not merely one object per patient.
- Preserve repeated claim numbers across different service lines.
- Use numeric values for Billed, Paid, and Patient Responsible.
- Put all downcoding language, including code 186 or 'Level of care change', in Note.
- Do not invent missing values. Use an empty string for missing text and 0 for missing money.
- Do not include commentary outside the JSON.
""".strip()

    try:
        uploaded_file = client.files.create(
            file=(filename, file_bytes, mime_type or "application/octet-stream"),
            purpose="user_data",
        )

        response = client.responses.create(
            model=MODEL,
            instructions=(
                "You extract structured healthcare remittance data accurately. "
                "Never omit service lines and never fabricate values."
            ),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": uploaded_file.id},
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
        )

        payload = json.loads(clean_json_text(response.output_text))
        rows = payload.get("rows", [])
        if not isinstance(rows, list) or not rows:
            raise ValueError("No claim rows were extracted from the document.")

        return normalize_report_dataframe(pd.DataFrame(rows))

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"The AI could not return readable structured data for '{filename}'."
        ) from exc
    finally:
        if uploaded_file is not None:
            try:
                client.files.delete(uploaded_file.id)
            except Exception:
                pass


def read_remittance_report(report_file: Any) -> pd.DataFrame:
    """Read CSV, Excel, PDF, or Word remittance reports into one schema."""
    filename = report_file.name
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_bytes = report_file.getvalue()

    if extension == "csv":
        try:
            frame = pd.read_csv(io.BytesIO(file_bytes))
        except UnicodeDecodeError:
            frame = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")
        return normalize_report_dataframe(frame)

    if extension in {"xlsx", "xls"}:
        return read_excel_report(file_bytes, filename)

    if extension == "pdf":
        return extract_report_with_openai(
            file_bytes,
            filename,
            report_file.type or "application/pdf",
        )

    if extension in {"docx", "doc"}:
        return extract_report_with_openai(
            file_bytes,
            filename,
            report_file.type
            or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    raise ValueError(
        f"Unsupported remittance report type: {filename}. "
        "Use CSV, XLSX, XLS, PDF, DOCX, or DOC."
    )


def date_variants(dos: str) -> list[str]:
    parsed = pd.to_datetime(dos, errors="coerce")
    if pd.isna(parsed):
        return [str(dos)]

    return [
        f"{parsed.month}/{parsed.day}/{parsed.year}",
        f"{parsed.month:02d}/{parsed.day:02d}/{parsed.year}",
        f"{parsed.year}-{parsed.month:02d}-{parsed.day:02d}",
        f"{parsed.month}-{parsed.day}-{parsed.year}",
        f"{parsed.month:02d}-{parsed.day:02d}-{parsed.year}",
    ]


def match_score(patient: str, dos: str, filename: str, text: str) -> float:
    haystack = normalize_name(filename + " " + text[:15000])
    patient_norm = normalize_name(patient)
    tokens = [token for token in patient_norm.split() if len(token) > 1]

    token_score = 0
    if tokens:
        token_score = 100 * sum(token in haystack for token in tokens) / len(tokens)

    fuzzy = fuzz.partial_ratio(patient_norm, haystack)
    date_found = any(variant.lower() in (filename + " " + text).lower()
                     for variant in date_variants(dos))

    return 0.55 * token_score + 0.30 * fuzzy + (15 if date_found else 0)


def extract_docx_images(template_bytes: bytes) -> tuple[bytes | None, bytes | None]:
    logo = None
    signature = None

    try:
        with zipfile.ZipFile(io.BytesIO(template_bytes)) as archive:
            media = sorted(
                name for name in archive.namelist()
                if name.startswith("word/media/")
            )
            if media:
                logo = archive.read(media[0])
            if len(media) > 1:
                signature = archive.read(media[1])
    except Exception:
        pass

    return logo, signature


def create_appeal_pdf(
    row: pd.Series,
    appeal_date: str,
    logo_bytes: bytes | None,
    signature_bytes: bytes | None,
) -> bytes:
    output = io.BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.28 * inch,
        bottomMargin=0.35 * inch,
    )

    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "AppealNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=10.6,
        spaceAfter=4,
    )
    small = ParagraphStyle(
        "AppealSmall",
        parent=normal,
        fontSize=8,
        leading=9.5,
    )
    centered_italic = ParagraphStyle(
        "CenteredItalic",
        parent=small,
        alignment=TA_CENTER,
        fontName="Helvetica-Oblique",
    )
    title_style = ParagraphStyle(
        "AppealTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=8,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=small,
        fontName="Helvetica-Bold",
    )

    story = []

    if logo_bytes:
        logo = Image(io.BytesIO(logo_bytes), width=0.70 * inch, height=0.55 * inch)
        logo.hAlign = "CENTER"
        story.append(logo)

    story.append(Paragraph("APPEAL OF INAPPROPRIATE E/M DOWNCODING", title_style))
    story.append(
        Table(
            [[""]],
            colWidths=[7.55 * inch],
            rowHeights=[0.025 * inch],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#17365D"))]),
        )
    )
    story.append(Spacer(1, 6))

    header_data = [
        [
            Paragraph("Date:", label_style),
            Paragraph(appeal_date, small),
            Paragraph("Submitted via:", label_style),
            Paragraph("Availity", small),
        ],
        [
            Paragraph("Attn:", label_style),
            Paragraph("Provider Appeals Department", small),
            "",
            "",
        ],
        [
            Paragraph("Payer:", label_style),
            Paragraph("Blue Cross Blue Shield of Texas", small),
            "",
            "",
        ],
    ]

    header_table = Table(
        header_data,
        colWidths=[0.62 * inch, 2.35 * inch, 1.05 * inch, 2.45 * inch],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#E7EBF3")),
                ("BACKGROUND", (3, 0), (3, -1), colors.HexColor("#E7EBF3")),
                ("SPAN", (1, 1), (3, 1)),
                ("SPAN", (1, 2), (3, 2)),
                ("BOX", (1, 0), (3, 2), 0.5, colors.HexColor("#B4B4B4")),
                ("INNERGRID", (1, 0), (3, 2), 0.25, colors.HexColor("#C7C7C7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 9))

    story.append(
        Paragraph(
            "<b>Re: Inappropriate downcoding of CPT evaluation and management (E/M) code</b>",
            normal,
        )
    )
    story.append(Spacer(1, 5))

    claim_data = [
        [
            "",
            "",
            Paragraph("Patient Name:", label_style),
            Paragraph(str(row["Patient"]), small),
        ],
        [
            Paragraph("Claim Number:", label_style),
            Paragraph(str(row["Claim Number"]), small),
            Paragraph("Claim / Service Date:", label_style),
            Paragraph(str(row["DOS"]), small),
        ],
        [
            Paragraph("Original CPT(s) Billed:", label_style),
            Paragraph(str(row["Original CPT(s) Billed"]), small),
            Paragraph("Downcoded To:", label_style),
            Paragraph(str(row["Downcoded To"]), small),
        ],
    ]

    claim_table = Table(
        claim_data,
        colWidths=[1.25 * inch, 1.78 * inch, 1.35 * inch, 2.0 * inch],
    )
    claim_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#E7EBF3")),
                ("BACKGROUND", (3, 0), (3, -1), colors.HexColor("#E7EBF3")),
                ("BOX", (1, 0), (1, -1), 0.5, colors.HexColor("#B4B4B4")),
                ("BOX", (3, 0), (3, -1), 0.5, colors.HexColor("#B4B4B4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(claim_table)
    story.append(Spacer(1, 7))

    for paragraph in [APPEAL_BODY_1, APPEAL_BODY_2]:
        story.append(Paragraph(paragraph, normal))

    story.append(Paragraph(TMA_TITLE, centered_italic))
    for paragraph in [TMA_1, TMA_2, TMA_3]:
        story.append(Paragraph(paragraph, centered_italic))

    story.append(Paragraph(APPEAL_CLOSE, normal))
    story.append(Paragraph(APPEAL_THANKS, normal))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Sincerely,", normal))

    if signature_bytes:
        signature = Image(
            io.BytesIO(signature_bytes),
            width=0.75 * inch,
            height=0.35 * inch,
        )
        signature.hAlign = "LEFT"
        story.append(signature)

    story.append(Paragraph("Michael James", normal))
    story.append(Paragraph("Practice Administrator", normal))

    doc.build(story)
    return output.getvalue()


def ama_guideline_pages(
    guideline_pdf: bytes,
    billed_codes: list[str],
) -> tuple[bytes, dict[str, list[int]]]:
    """Copy code-relevant AMA pages without relying on incidental code mentions."""
    reader = PdfReader(io.BytesIO(guideline_pdf))
    code_pages: dict[str, list[int]] = {}
    selected_indexes = set()
    office_em_pages = [6, 8, 9, 10, 20]

    for raw_code in billed_codes:
        code = str(raw_code).split()[0].strip().upper()
        if not code or not code.isdigit():
            continue

        if code in E_M_CODES:
            matches = [page for page in office_em_pages if page <= len(reader.pages)]
        else:
            matches = [
                page_index + 1
                for page_index, page in enumerate(reader.pages)
                if re.search(rf"(?<!\d){re.escape(code)}(?!\d)", page.extract_text() or "")
            ]
        if matches:
            code_pages[code] = matches
            selected_indexes.update(page - 1 for page in matches)

    writer = PdfWriter()
    for page_index in sorted(selected_indexes):
        writer.add_page(reader.pages[page_index])

    if not selected_indexes:
        return b"", code_pages

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), code_pages


def cms_guideline_pages(
    guideline_pdf: bytes,
    billed_codes: list[str],
) -> tuple[bytes, dict[str, list[int]]]:
    """Select CMS E/M overview pages when the manual does not list each CPT code."""
    reader = PdfReader(io.BytesIO(guideline_pdf))
    code_pages: dict[str, list[int]] = {}
    selected_indexes: set[int] = set()
    em_overview_pages = [23, 24, 25]

    for raw_code in billed_codes:
        code = str(raw_code).split()[0].strip().upper()
        matches = [
            page_index + 1
            for page_index, page in enumerate(reader.pages)
            if code and code in (page.extract_text() or "")
        ]
        if code in E_M_CODES or re.fullmatch(r"99\d{3}", code):
            matches = sorted(set(matches + em_overview_pages))
        valid_matches = [page for page in matches if 1 <= page <= len(reader.pages)]
        if valid_matches:
            code_pages[code] = valid_matches
            selected_indexes.update(page - 1 for page in valid_matches)

    writer = PdfWriter()
    for page_index in sorted(selected_indexes):
        writer.add_page(reader.pages[page_index])
    if not selected_indexes:
        return b"", code_pages
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), code_pages

def merge_pdfs(*pdf_sources: bytes) -> bytes:
    writer = PdfWriter()

    for source in pdf_sources:
        if not source:
            continue
        reader = PdfReader(io.BytesIO(source))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()

def _second_level_value(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.I | re.M)
    return match.group(1).strip() if match else ""


def extract_second_level_case(denial_text: str) -> dict[str, Any]:
    """Extract editable identifiers from a BCBSTX upheld-denial letter."""
    codes = sorted(set(re.findall(r"\b(?:9\d{4}|G\d{4})\b", denial_text, flags=re.I)))
    rationale_match = re.search(
        r"(We acknowledge.*?(?:denial|downcoding).*?upheld\.)",
        denial_text,
        flags=re.I | re.S,
    )
    rationale = (
        re.sub(r"\s+", " ", rationale_match.group(1)).strip()
        if rationale_match
        else ""
    )
    return {
        "patient": _second_level_value(r"^Patient Name:\s*(.+)$", denial_text),
        "member_id": _second_level_value(r"^Subscriber ID:\s*(.+)$", denial_text),
        "group_number": _second_level_value(r"^Group Number:\s*(.+)$", denial_text),
        "claim_number": _second_level_value(r"^Claim Number:\s*(.+)$", denial_text),
        "service_date": _second_level_value(r"^Service Date:\s*(.+)$", denial_text),
        "codes": codes,
        "rationale": rationale,
    }


def _pdf_paragraph(value: Any) -> str:
    return escape(str(value or "")).replace("\n", "<br/>")


def create_second_level_cover_pdf(
    case: dict[str, str],
    mailing_address: str,
    appeal_date_value: date,
    provider_name: str,
    codes: list[str],
    supporting_count: int,
) -> bytes:
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "SecondLevelTitle",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=12,
    )
    normal = ParagraphStyle(
        "SecondLevelNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=7,
    )
    label = ParagraphStyle(
        "SecondLevelLabel",
        parent=normal,
        fontName="Helvetica-Bold",
    )
    story = [
        Paragraph("SECOND-LEVEL / SPECIALTY APPEAL", title),
        Paragraph(_pdf_paragraph(mailing_address), normal),
        Spacer(1, 8),
    ]
    rows = [
        [Paragraph("Appeal date", label), Paragraph(appeal_date_value.strftime("%m/%d/%Y"), normal)],
        [Paragraph("Provider", label), Paragraph(_pdf_paragraph(provider_name), normal)],
        [Paragraph("Patient", label), Paragraph(_pdf_paragraph(case["patient"]), normal)],
        [Paragraph("Member ID", label), Paragraph(_pdf_paragraph(case["member_id"]), normal)],
        [Paragraph("Group number", label), Paragraph(_pdf_paragraph(case["group_number"]), normal)],
        [Paragraph("Claim number", label), Paragraph(_pdf_paragraph(case["claim_number"]), normal)],
        [Paragraph("Date of service", label), Paragraph(_pdf_paragraph(case["service_date"]), normal)],
        [Paragraph("Billed code(s)", label), Paragraph(_pdf_paragraph(", ".join(codes)), normal)],
    ]
    table = Table(rows, colWidths=[1.45 * inch, 5.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C3CC")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF0F6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([table, Spacer(1, 14), Paragraph("ENCLOSURES", label)])
    enclosures = [
        "AMA guidance pages applicable to the billed code(s)",
        "CMS evaluation and management guidance applicable to the billed code(s)",
        "Fillable provider code-by-code response worksheet",
        "Complete encounter note",
        "BCBSTX upheld-denial correspondence",
    ]
    if supporting_count:
        enclosures.append(f"Additional supporting correspondence ({supporting_count} file(s))")
    story.extend(Paragraph(f"{index}. {_pdf_paragraph(item)}", normal) for index, item in enumerate(enclosures, 1))
    story.extend(
        [
            Spacer(1, 12),
            Paragraph(
                "Please include this submission in the complete claim and appeal record and route it for the applicable second-level or specialty review.",
                normal,
            ),
        ]
    )
    doc.build(story)
    return output.getvalue()


def _draw_wrapped_paragraph(
    pdf_canvas: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    style: ParagraphStyle,
) -> float:
    paragraph = Paragraph(_pdf_paragraph(text), style)
    _, height = paragraph.wrap(width, 10 * inch)
    paragraph.drawOn(pdf_canvas, x, y - height)
    return y - height


def create_provider_feedback_pdf(
    case: dict[str, str],
    provider_name: str,
    codes: list[str],
    guideline_pages: dict[str, dict[str, list[int]]],
    appeal_date_value: date,
) -> bytes:
    """Create provider worksheets with multiline fillable PDF fields."""
    output = io.BytesIO()
    pdf_canvas = canvas.Canvas(output, pagesize=letter)
    width, height = letter
    normal = ParagraphStyle(
        "FillableNormal",
        fontName="Helvetica",
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#1F2937"),
    )
    small = ParagraphStyle(
        "FillableSmall",
        parent=normal,
        fontSize=7.5,
        leading=9.2,
    )

    for code in codes:
        pdf_canvas.setTitle("BCBS Second-Level Provider Feedback")
        pdf_canvas.setFillColor(colors.HexColor("#17365D"))
        pdf_canvas.setFont("Helvetica-Bold", 15)
        pdf_canvas.drawCentredString(width / 2, height - 0.55 * inch, "PROVIDER CLINICAL FEEDBACK")
        pdf_canvas.setStrokeColor(colors.HexColor("#17365D"))
        pdf_canvas.setLineWidth(1)
        pdf_canvas.line(0.65 * inch, height - 0.68 * inch, width - 0.65 * inch, height - 0.68 * inch)

        pdf_canvas.setFillColor(colors.HexColor("#1F2937"))
        pdf_canvas.setFont("Helvetica", 8.5)
        pdf_canvas.drawString(0.65 * inch, height - 0.92 * inch, f"Patient: {case['patient']}")
        pdf_canvas.drawString(3.15 * inch, height - 0.92 * inch, f"Claim: {case['claim_number']}")
        pdf_canvas.drawString(5.75 * inch, height - 0.92 * inch, f"DOS: {case['service_date']}")

        pdf_canvas.setFont("Helvetica-Bold", 12)
        pdf_canvas.setFillColor(colors.HexColor("#17365D"))
        pdf_canvas.drawString(0.65 * inch, height - 1.25 * inch, f"Originally billed CPT/HCPCS code: {code}")

        references = guideline_pages.get(code, {})
        reference_text = "; ".join(
            f"{source} page(s) {', '.join(map(str, pages))}"
            for source, pages in references.items()
            if pages
        ) or "No matching reference page was automatically identified."
        pdf_canvas.setFillColor(colors.HexColor("#1F2937"))
        pdf_canvas.setFont("Helvetica-Bold", 8)
        pdf_canvas.drawString(0.65 * inch, height - 1.48 * inch, "Reference pages included:")
        pdf_canvas.setFont("Helvetica", 8)
        pdf_canvas.drawString(2.20 * inch, height - 1.48 * inch, reference_text[:90])

        y = height - 1.75 * inch
        pdf_canvas.setFont("Helvetica-Bold", 8.5)
        pdf_canvas.drawString(0.65 * inch, y, "BCBSTX upheld-denial rationale")
        y -= 0.08 * inch
        y = _draw_wrapped_paragraph(
            pdf_canvas,
            case.get("rationale") or "No denial rationale was extracted; review the attached correspondence.",
            0.65 * inch,
            y,
            7.2 * inch,
            small,
        ) - 0.14 * inch

        field_top = min(y - 0.22 * inch, 6.55 * inch)
        field_bottom = 1.45 * inch
        field_height = max(2.2 * inch, field_top - field_bottom)
        if field_bottom + field_height > field_top:
            field_height = max(1.8 * inch, field_top - field_bottom)
        pdf_canvas.setFont("Helvetica-Bold", 9)
        pdf_canvas.drawString(
            0.65 * inch,
            field_bottom + field_height + 0.10 * inch,
            f"Provider reasoning for billed code {code}",
        )
        pdf_canvas.acroForm.textfield(
            name=f"provider_response_{code}",
            tooltip=f"Provider explanation for {code}",
            x=0.65 * inch,
            y=field_bottom,
            width=7.2 * inch,
            height=field_height,
            borderStyle="solid",
            borderWidth=1,
            borderColor=colors.HexColor("#7A8A99"),
            fillColor=colors.HexColor("#FFFFFF"),
            textColor=colors.HexColor("#111827"),
            fontName="Helvetica",
            fontSize=9,
            fieldFlags="multiline",
            forceBorder=True,
        )

        pdf_canvas.setFont("Helvetica", 8)
        pdf_canvas.drawString(0.65 * inch, 1.10 * inch, "Provider signature:")
        pdf_canvas.acroForm.textfield(
            name=f"provider_signature_{code}",
            tooltip=f"Provider signature for {code}",
            x=1.55 * inch,
            y=0.92 * inch,
            width=3.45 * inch,
            height=0.32 * inch,
            borderStyle="underlined",
            borderWidth=1,
            forceBorder=True,
        )
        pdf_canvas.drawString(5.25 * inch, 1.10 * inch, "Date:")
        pdf_canvas.acroForm.textfield(
            name=f"provider_date_{code}",
            tooltip=f"Provider date for {code}",
            value=appeal_date_value.strftime("%m/%d/%Y"),
            x=5.58 * inch,
            y=0.92 * inch,
            width=1.55 * inch,
            height=0.32 * inch,
            borderStyle="underlined",
            borderWidth=1,
            forceBorder=True,
        )
        pdf_canvas.setFillColor(colors.HexColor("#5F6B76"))
        pdf_canvas.setFont("Helvetica-Oblique", 7.5)
        pdf_canvas.drawString(
            0.65 * inch,
            0.55 * inch,
            "Provider-authored response required. Trimera does not add or infer clinical facts.",
        )
        pdf_canvas.showPage()

    pdf_canvas.save()
    return output.getvalue()


def merge_fillable_pdfs(*pdf_sources: bytes) -> bytes:
    """Merge packet sections while retaining AcroForm fields."""
    writer = PdfWriter()
    for source in pdf_sources:
        if source:
            writer.append(io.BytesIO(source))
    writer.set_need_appearances_writer(True)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()

def render_second_level_workflow() -> None:
    st.markdown("### Second-level / specialty appeal")
    st.caption(
        "Upload the encounter note and BCBSTX upheld-denial correspondence. "
        "Trimera creates a fillable PDF for Dr. Maxwell; she does not use this app."
    )
    denial_file = st.file_uploader(
        "1. Upload BCBSTX upheld-denial correspondence",
        type=["pdf"],
        key="second_level_denial",
    )
    note_file = st.file_uploader(
        "2. Upload the complete encounter note",
        type=["pdf"],
        key="second_level_note",
    )
    supporting_files = st.file_uploader(
        "3. Upload additional supporting letters (optional)",
        type=["pdf"],
        accept_multiple_files=True,
        key="second_level_supporting",
    )
    if denial_file is None or note_file is None:
        st.info("Upload both required PDFs to begin the second-level packet review.")
        return

    try:
        denial_bytes = denial_file.getvalue()
        denial_text = extract_pdf_text(denial_bytes)
        case = extract_second_level_case(denial_text)
    except Exception as exc:
        st.error(f"The upheld-denial correspondence could not be read: {exc}")
        return

    st.markdown("### Review extracted appeal details")
    left, right = st.columns(2)
    with left:
        patient = st.text_input("Patient name", value=case["patient"], key="second_patient")
        member_id = st.text_input("Member ID", value=case["member_id"], key="second_member")
        group_number = st.text_input("Group number", value=case["group_number"], key="second_group")
        claim_number = st.text_input("Claim number", value=case["claim_number"], key="second_claim")
    with right:
        service_date = st.text_input("Date of service", value=case["service_date"], key="second_dos")
        codes_raw = st.text_input("Originally billed code(s)", value=", ".join(case["codes"]), key="second_codes")
        provider_name = st.text_input("Provider", value="Rebecca H. Maxwell, MD", key="second_provider")
        appeal_date_value = st.date_input("Appeal date", value=date.today(), key="second_date")
    mailing_address = st.text_area(
        "Mailing address",
        value=SECOND_LEVEL_DEFAULT_ADDRESS,
        height=125,
        key="second_address",
    )
    reviewed_case = {
        "patient": patient.strip(),
        "member_id": member_id.strip(),
        "group_number": group_number.strip(),
        "claim_number": claim_number.strip(),
        "service_date": service_date.strip(),
        "rationale": case["rationale"],
    }
    if case["rationale"]:
        with st.expander("BCBSTX upheld-denial rationale"):
            st.write(case["rationale"])

    codes = list(dict.fromkeys(re.findall(r"\b(?:9\d{4}|G\d{4})\b", codes_raw.upper())))
    if not codes:
        st.error("Confirm at least one valid five-character billed code.")
        return

    try:
        ama_pdf, ama_map = ama_guideline_pages(AMA_GUIDELINES_PATH.read_bytes(), codes)
        cms_pdf, cms_map = cms_guideline_pages(CMS_GUIDELINES_PATH.read_bytes(), codes)
    except OSError as exc:
        st.error(f"A required AMA/CMS reference file is unavailable: {exc}")
        return

    guideline_pages = {
        code: {
            "AMA": ama_map.get(code, []),
            "CMS": cms_map.get(code, []),
        }
        for code in codes
    }
    st.markdown("### Packet contents")
    reference_rows = []
    for code in codes:
        reference_rows.append(
            {
                "Billed code": code,
                "AMA pages": ", ".join(map(str, ama_map.get(code, []))) or "Not found",
                "CMS pages": ", ".join(map(str, cms_map.get(code, []))) or "Not found",
                "Provider response field": "Included in fillable PDF",
            }
        )
    st.dataframe(pd.DataFrame(reference_rows), use_container_width=True, hide_index=True)
    st.caption(
        "Packet order: cover sheet, code-specific AMA pages, code-specific CMS pages, "
        "fillable provider worksheet, encounter note, upheld-denial correspondence, and optional letters."
    )

    required_values = [patient, member_id, claim_number, service_date, mailing_address, provider_name]
    ready = all(str(value).strip() for value in required_values)
    if st.button(
        "Create fillable PDF",
        type="primary",
        use_container_width=True,
        disabled=not ready,
    ):
        try:
            cover_pdf = create_second_level_cover_pdf(
                reviewed_case,
                mailing_address,
                appeal_date_value,
                provider_name,
                codes,
                len(supporting_files or []),
            )
            provider_pdf = create_provider_feedback_pdf(
                reviewed_case,
                provider_name,
                codes,
                guideline_pages,
                appeal_date_value,
            )
            packet = merge_fillable_pdfs(
                cover_pdf,
                ama_pdf,
                cms_pdf,
                provider_pdf,
                note_file.getvalue(),
                denial_bytes,
                *[item.getvalue() for item in (supporting_files or [])],
            )
            filename = (
                f"BCBS_SECOND_LEVEL_FILLABLE_{filename_safe(patient)}_"
                f"{filename_safe(claim_number)}.pdf"
            )
            st.success(
                "The fillable packet is ready. Send it to Dr. Maxwell so she can type, save, and return her responses."
            )
            st.download_button(
                "Download fillable packet for Dr. Maxwell",
                data=packet,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True,
                on_click="ignore",
            )
        except Exception as exc:
            st.error(f"The second-level packet could not be generated: {exc}")

apply_trimera_theme()
require_auth(APP_TITLE, "Internal Trimera Health tool")
render_topbar()

with st.sidebar:
    sidebar_label("Quick actions")
    if st.button("Sign out", use_container_width=True):
        logout_user()

    sidebar_model(MODEL)
    sidebar_reminder(
        "Appeal workflow",
        "Builds one packet per unique downcoded claim and flags unsafe matches.",
    )


page_header(
    "appeal",
    "BCBS Appeal Builder",
    "Build downcoding appeal packets from remittance reports, encounter notes, and the current tracker.",
)
appeal_level = st.radio(
    "Appeal level",
    options=["First-level appeal", "Second-level / specialty appeal"],
    horizontal=True,
)

if appeal_level == "Second-level / specialty appeal":
    render_second_level_workflow()
    st.stop()

report_files = st.file_uploader(
    "1. Upload one or more BCBS remittance reports",
    type=["csv", "xlsx", "xls", "pdf", "docx", "doc"],
    accept_multiple_files=True,
    help=(
        "Upload any combination of CSV, Excel, PDF, or Word remittance "
        "reports. PDF and Word extraction uses the configured OpenAI model."
    ),
)

st.caption("The approved Trimera BCBS appeal template is included automatically.")
st.caption(
    "Applicable AMA guideline pages for each billed CPT code are included "
    "automatically between the appeal letter and encounter note."
)

note_files = st.file_uploader(
    "2. Upload encounter-note PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

tracker_file = st.file_uploader(
    "3. Upload current BCBS tracker (optional)",
    type=["xlsx"],
    help=(
        "Upload the current tracker to receive a new copy with all newly "
        "detected downcoded claims appended automatically."
    ),
)

appeal_date = st.date_input(
    "Appeal date",
    value=date.today(),
)

if report_files and note_files:
    try:
        report_frames = []

        for report_file in report_files:
            with st.spinner(f"Reading {report_file.name}..."):
                frame = read_remittance_report(report_file)
            frame["Source Report"] = report_file.name
            report_frames.append(frame)

        report_df = pd.concat(
            report_frames,
            ignore_index=True,
            sort=False,
        )

        # Prevent the same claim from being built twice when it appears in
        # more than one remittance report.
        report_df = report_df.drop_duplicates()

        claims_df = build_claim_summary(report_df)

        if not claims_df.empty:
            claims_df = claims_df.drop_duplicates(
                subset=[
                    "Patient",
                    "DOS",
                    "Claim Number",
                    "Original CPT(s) Billed",
                    "Downcoded To",
                ]
            ).reset_index(drop=True)

    except Exception as exc:
        st.error(f"Could not read the remittance reports: {exc}")
        st.stop()

    if claims_df.empty:
        st.warning(
            "No downcoded 99214 or 99215 claims were found across the uploaded reports."
        )
        st.stop()

    st.success(
        f"Combined {len(report_files)} remittance report(s) and identified "
        f"{len(claims_df)} unique downcoded claim(s)."
    )

    with st.expander("Uploaded remittance reports"):
        for report_file in report_files:
            st.write(f"- {report_file.name}")

    note_data = []
    for note_file in note_files:
        file_bytes = note_file.getvalue()
        try:
            text = extract_pdf_text(file_bytes)
        except Exception:
            text = ""

        note_data.append(
            {
                "filename": note_file.name,
                "bytes": file_bytes,
                "text": text,
            }
        )

    match_rows = []
    default_matches = {}

    for claim_index, claim in claims_df.iterrows():
        scored = sorted(
            [
                (
                    match_score(
                        claim["Patient"],
                        claim["DOS"],
                        note["filename"],
                        note["text"],
                    ),
                    note_index,
                )
                for note_index, note in enumerate(note_data)
            ],
            reverse=True,
        )

        best_score, best_note_index = scored[0]
        default_matches[claim_index] = (
            best_note_index if best_score >= 65 else None
        )

        match_rows.append(
            {
                "Patient": claim["Patient"],
                "DOS": claim["DOS"],
                "Claim Number": claim["Claim Number"],
                "Original CPT(s)": claim["Original CPT(s) Billed"],
                "Downcoded To": claim["Downcoded To"],
                "Best Note Match": (
                    note_data[best_note_index]["filename"]
                    if best_score >= 65
                    else "No confident match"
                ),
                "Match Score": round(best_score, 1),
            }
        )

    st.subheader("Review matches")
    st.dataframe(pd.DataFrame(match_rows), use_container_width=True)

    st.subheader("Copy rows into your real tracker")
    st.caption(
        "Click inside the box, press Ctrl+A and Ctrl+C, then paste into the "
        "first empty row of Column A in Excel. Each value will fall into the "
        "correct tracker column automatically."
    )

    include_tracker_header = st.checkbox(
        "Include tracker column headers",
        value=False,
        help="Leave this off when pasting below the existing tracker rows.",
    )

    tracker_copy_text = tracker_copy_table(
        claims_df,
        appeal_date,
        include_header=include_tracker_header,
    )

    st.text_area(
        "Excel-ready tracker rows",
        value=tracker_copy_text,
        height=min(500, max(180, 34 * (len(claims_df) + 1))),
        help=(
            "Tab-delimited text matching Columns A through M of the BCBS "
            "Downcoding Tracker."
        ),
    )

    tracker_export_df = pd.DataFrame(
        {
            "Patient Name": claims_df["Patient"],
            "DOS": claims_df["DOS"],
            "Original CPT(s)": claims_df[
                "Original CPT(s) Billed"
            ].str.replace(", ", " + ", regex=False),
            "Paid CPT(s)": claims_df[
                "Downcoded To"
            ].str.replace(", ", " + ", regex=False),
            "Expected Payment": claims_df["Expected Payment"].round(2),
            "Actual Payment": claims_df["Actual Payment"].round(2),
            "Loss $": (
                claims_df["Expected Payment"]
                - claims_df["Actual Payment"]
            ).round(2),
            "Appeal Submitted?": "Yes",
            "Appeal Date": appeal_date.strftime("%m/%d/%Y"),
            "Outcome": "Pending",
            "Recovered $": 0.00,
            "Net Outstanding Loss": (
                claims_df["Expected Payment"]
                - claims_df["Actual Payment"]
            ).round(2),
            "Insurance Type": "",
        }
    )

    st.download_button(
        "Download tracker rows as CSV",
        data=tracker_export_df.to_csv(index=False),
        file_name=(
            f"BCBS_TRACKER_ROWS_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        ),
        mime="text/csv",
        use_container_width=True,
    )

    st.caption(
        "Confirm each encounter note below. Claims without a matching note are "
        "left as 'No note selected' and skipped; all confidently matched claims "
        "can be built together."
    )

    selected_matches = {}
    options = ["No note selected"] + [note["filename"] for note in note_data]

    for claim_index, claim in claims_df.iterrows():
        default_note_index = default_matches.get(claim_index)
        default_option_index = (
            default_note_index + 1
            if default_note_index is not None
            else 0
        )

        selected_filename = st.selectbox(
            f"{claim['Patient']} - DOS {claim['DOS']} - "
            f"Claim {claim['Claim Number']}",
            options=options,
            index=default_option_index,
            key=f"note_match_{claim_index}",
        )

        selected_matches[claim_index] = selected_filename

    if st.button(
        "Build appeal packets",
        type="primary",
        use_container_width=True,
    ):
        try:
            template_bytes = DEFAULT_APPEAL_TEMPLATE_PATH.read_bytes()
            guideline_bytes = AMA_GUIDELINES_PATH.read_bytes()
        except OSError:
            st.error(
                "The approved BCBS appeal references are unavailable. "
                "Please contact the Trimera AI administrator."
            )
            st.stop()
        logo_bytes, signature_bytes = extract_docx_images(template_bytes)

        built = []
        skipped = []
        guideline_pages_by_claim = {}

        for claim_index, claim in claims_df.iterrows():
            selected_filename = selected_matches.get(claim_index)

            if not selected_filename or selected_filename == "No note selected":
                skipped.append(
                    f"{claim['Patient']} - {claim['DOS']} - no note selected"
                )
                continue

            note = next(
                item for item in note_data
                if item["filename"] == selected_filename
            )

            appeal_pdf = create_appeal_pdf(
                claim,
                f"{appeal_date.month}/{appeal_date.day}/{appeal_date.year}",
                logo_bytes,
                signature_bytes,
            )
            guideline_pdf, guideline_page_map = ama_guideline_pages(
                guideline_bytes,
                claim["Original Codes List"],
            )
            guideline_pages_by_claim[claim_index] = guideline_page_map

            merged_pdf = merge_pdfs(
                appeal_pdf,
                guideline_pdf,
                note["bytes"],
            )

            output_name = availity_appeal_filename(
                claim["Patient"],
                claim["DOS"],
                claim["Claim Number"],
            )

            built.append((output_name, merged_pdf))

        manifest_csv = pd.DataFrame(
            [
                {
                    "Patient": row["Patient"],
                    "DOS": row["DOS"],
                    "Claim Number": row["Claim Number"],
                    "Original CPT(s) Billed": row["Original CPT(s) Billed"],
                    "Downcoded To": row["Downcoded To"],
                    "Source Report(s)": row.get("Source Report(s)", ""),
                    "Encounter Note": selected_matches.get(index, ""),
                    "AMA Guideline Pages": "; ".join(
                        f"{code}: {', '.join(map(str, pages))}"
                        for code, pages in guideline_pages_by_claim.get(
                            index, {}
                        ).items()
                    ),
                    "Packet Built": (
                        "YES"
                        if selected_matches.get(index)
                        not in {None, "No note selected"}
                        else "NO"
                    ),
                }
                for index, row in claims_df.iterrows()
            ]
        ).to_csv(index=False)

        if built:
            zip_output = io.BytesIO()
            with zipfile.ZipFile(
                zip_output,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                for output_name, output_bytes in built:
                    archive.writestr(output_name, output_bytes)
                archive.writestr(
                    "APPEAL_PACKET_MANIFEST.csv",
                    manifest_csv,
                )

            st.success(f"Built {len(built)} appeal packet(s).")
            st.caption(
                "Download the ZIP file below. It contains every completed "
                "appeal PDF and the appeal manifest."
            )
            st.download_button(
                "Download all appeal packets",
                data=zip_output.getvalue(),
                file_name=(
                    f"BCBS_APPEAL_PACKETS_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                ),
                mime="application/zip",
                use_container_width=True,
                on_click="ignore",
            )

        if tracker_file is not None:
            try:
                updated_tracker, tracker_added, tracker_skipped = (
                    append_claims_to_tracker(
                        tracker_file.getvalue(),
                        claims_df,
                        appeal_date,
                    )
                )

                st.divider()
                st.subheader("Updated BCBS tracker")

                if not tracker_added.empty:
                    st.success(
                        f"Added {len(tracker_added)} new claim(s) to the tracker."
                    )
                    st.dataframe(
                        tracker_added,
                        use_container_width=True,
                    )
                else:
                    st.info(
                        "No new tracker rows were added because all detected "
                        "claims were already present."
                    )

                st.download_button(
                    "Download updated tracker",
                    data=updated_tracker,
                    file_name=(
                        f"BCBSTX_DC_TRACKER_UPDATED_"
                        f"{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    use_container_width=True,
                )

                if tracker_skipped:
                    with st.expander("Tracker rows skipped as duplicates"):
                        for item in tracker_skipped:
                            st.write(f"- {item}")

            except Exception as exc:
                st.error(f"Could not update the tracker: {exc}")

        if skipped:
            st.warning("Appeal packets skipped: " + "; ".join(skipped))
