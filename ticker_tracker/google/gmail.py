"""Gmail API — send HTML mail with optional attachment."""

from __future__ import annotations

import base64
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from googleapiclient.discovery import build

from google.oauth2.credentials import Credentials
from ticker_tracker.google.auth import get_credentials


def _build_raw_message(
    to: str,
    subject: str,
    body_html: str,
    attachment_path: str | Path | None,
) -> str:
    message = MIMEMultipart()
    message["to"] = to
    message["subject"] = subject
    message.attach(MIMEText(body_html, "html", "utf-8"))

    if attachment_path is not None:
        path = Path(attachment_path)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        mime_main, mime_sub = "application", "octet-stream"
        guessed, _ = mimetypes.guess_type(str(path))
        if guessed and "/" in guessed:
            main, sub = guessed.split("/", 1)
            mime_main, mime_sub = main, sub

        part = MIMEBase(mime_main, mime_sub)
        part.set_payload(path.read_bytes())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=path.name,
        )
        message.attach(part)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return raw


def send_email(
    to: str,
    subject: str,
    body_html: str,
    attachment_path: str | Path | None = None,
    *,
    credentials: Credentials | None = None,
) -> dict:
    """
    Send a message via Gmail API (not SMTP).

    *body_html* is sent as an HTML part. If *attachment_path* is set, that file
    is attached (e.g. ``.xlsx`` with an appropriate MIME type when guessable).
    """
    creds = credentials or get_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw = _build_raw_message(to, subject, body_html, attachment_path)
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent
