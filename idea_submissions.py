"""Secure storage and notification delivery for staff improvement ideas."""

import json
import os
from datetime import datetime, timezone
from pathlib import PurePath
from urllib import request
from urllib.parse import quote
from uuid import uuid4


def _setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not configured.")
    return value


def _safe_filename(filename: str) -> str:
    name = PurePath(filename or "attachment").name
    cleaned = "".join(character for character in name if character.isalnum() or character in "._- ").strip()
    return cleaned[:160] or "attachment"


def _send_notification(submitter: str, submitted_at: str, console_url: str) -> None:
    api_key = _setting("SENDGRID_API_KEY")
    recipient = os.getenv("TRIMERA_IDEA_RECIPIENT", "mikej@trimerahealth.net").strip()
    sender = _setting("TRIMERA_IDEA_FROM_EMAIL")
    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": sender, "name": "Trimera AI"},
        "subject": "New Trimera improvement idea submitted",
        "content": [{
            "type": "text/plain",
            "value": (
                "A new improvement idea was submitted in Trimera AI.\n\n"
                f"Submitted by: {submitter}\n"
                f"Submitted at: {submitted_at}\n\n"
                "Review the full request and attachments securely in Google Cloud:\n"
                f"{console_url}\n"
            ),
        }],
    }
    notification = request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(notification, timeout=20) as response:
        if response.status not in (200, 202):
            raise RuntimeError("The email notification could not be sent.")


def submit_idea(submitter: str, description: str, attachments: list) -> str:
    """Store a submission privately, notify the owner, and return its reference."""
    from google.cloud import storage

    bucket_name = _setting("TRIMERA_IDEA_BUCKET")
    submitted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    reference = f"idea-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:8]}"
    prefix = f"improvement-ideas/{reference}"
    bucket = storage.Client().bucket(bucket_name)

    manifest = {
        "reference": reference,
        "submitted_at": submitted_at,
        "submitted_by": submitter,
        "description": description,
        "attachments": [_safe_filename(item.name) for item in attachments],
    }
    bucket.blob(f"{prefix}/request.json").upload_from_string(
        json.dumps(manifest, indent=2), content_type="application/json"
    )
    for attachment in attachments:
        attachment.seek(0)
        bucket.blob(f"{prefix}/attachments/{_safe_filename(attachment.name)}").upload_from_file(
            attachment,
            content_type=getattr(attachment, "type", None) or "application/octet-stream",
            rewind=True,
        )

    console_url = (
        "https://console.cloud.google.com/storage/browser/"
        f"{quote(bucket_name, safe='')}/{quote(prefix, safe='/')}"
    )
    _send_notification(submitter, submitted_at, console_url)
    return reference
