import io
import os
import re
import zipfile
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st
from openai import OpenAI
from pypdf import PdfReader, PdfWriter
from rapidfuzz import fuzz
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


st.set_page_config(
    page_title="BCBS Appeal Packet Builder",
    page_icon="📨",
    layout="wide",
)

APP_TITLE = "BCBS Appeal Packet Builder"
TEST_PASSWORD = os.getenv("TRIMERA_QA_PASSWORD", "")

AMOUNT_TO_CODE = {
    25.00: "G2211",
    100.00: "90833",
    150.00: "90836",
    200.00: "99214",
    250.00: "99215",
    500.00: "99417 x5",
}

E_M_CODES = {"99214", "99215"}

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


def password_gate() -> None:
    if not TEST_PASSWORD:
        st.warning("TRIMERA_QA_PASSWORD is not configured.")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title(APP_TITLE)
    st.caption("Internal Trimera Health tool")

    entered = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        if entered == TEST_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


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

        rows.append(
            {
                "Patient": str(patient).strip(),
                "DOS": format_date(dos),
                "Claim Number": claim_number_for_appeal(claim),
                "Original CPT(s) Billed": ", ".join(original),
                "Downcoded To": ", ".join(paid_codes),
                "Original Codes List": original,
            }
        )

    return pd.DataFrame(rows)


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


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


def merge_pdfs(first_pdf: bytes, second_pdf: bytes) -> bytes:
    writer = PdfWriter()

    for source in [first_pdf, second_pdf]:
        reader = PdfReader(io.BytesIO(source))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


password_gate()

with st.sidebar:
    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.info(
        "This tool builds one appeal packet per downcoded claim and flags "
        "anything it cannot match safely."
    )


st.title("📨 BCBS Downcoding Appeal Packet Builder")
st.caption(
    "Upload the BCBS report, appeal template, and encounter-note PDFs. "
    "The tool fills each appeal and merges it with the matching note."
)

report_file = st.file_uploader(
    "1. Upload BCBS claim report",
    type=["csv"],
)

template_file = st.file_uploader(
    "2. Upload BCBS appeal Word template",
    type=["docx"],
)

note_files = st.file_uploader(
    "3. Upload encounter-note PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

appeal_date = st.date_input(
    "Appeal date",
    value=date.today(),
)

if report_file and template_file and note_files:
    try:
        report_df = pd.read_csv(report_file)
        claims_df = build_claim_summary(report_df)
    except Exception as exc:
        st.error(f"Could not read the claim report: {exc}")
        st.stop()

    if claims_df.empty:
        st.warning("No downcoded 99214 or 99215 claims were found in the report.")
        st.stop()

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

    st.caption(
        "Confirm each encounter note below. The tool will not build a packet "
        "for a claim left as 'No note selected.'"
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
        template_bytes = template_file.getvalue()
        logo_bytes, signature_bytes = extract_docx_images(template_bytes)

        zip_output = io.BytesIO()
        built = []
        skipped = []

        with zipfile.ZipFile(
            zip_output,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
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

                merged_pdf = merge_pdfs(
                    appeal_pdf,
                    note["bytes"],
                )

                output_name = (
                    f"{filename_safe(claim['Patient'])}_"
                    f"{pd.to_datetime(claim['DOS']).strftime('%Y-%m-%d')}_"
                    f"{filename_safe(claim['Claim Number'])}_"
                    f"BCBS_APPEAL.pdf"
                )

                archive.writestr(output_name, merged_pdf)
                built.append(output_name)

            archive.writestr(
                "APPEAL_PACKET_MANIFEST.csv",
                pd.DataFrame(
                    [
                        {
                            "Patient": row["Patient"],
                            "DOS": row["DOS"],
                            "Claim Number": row["Claim Number"],
                            "Original CPT(s) Billed": row["Original CPT(s) Billed"],
                            "Downcoded To": row["Downcoded To"],
                            "Encounter Note": selected_matches.get(index, ""),
                            "Packet Built": (
                                "YES"
                                if selected_matches.get(index)
                                not in {None, "No note selected"}
                                else "NO"
                            ),
                        }
                        for index, row in claims_df.iterrows()
                    ]
                ).to_csv(index=False),
            )

        if built:
            st.success(f"Built {len(built)} appeal packet(s).")

            st.download_button(
                "Download all appeal packets",
                data=zip_output.getvalue(),
                file_name=(
                    f"BCBS_APPEAL_PACKETS_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                ),
                mime="application/zip",
                use_container_width=True,
            )

        if skipped:
            st.warning("Skipped: " + "; ".join(skipped))
