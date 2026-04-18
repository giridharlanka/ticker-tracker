"""Google Drive API — upload files."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from google.oauth2.credentials import Credentials
from ticker_tracker.google.auth import get_credentials


def _guess_mime(path: Path) -> str:
    mime, _encoding = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def upload_file(
    local_path: str | Path,
    filename: str,
    folder_id: str | None = None,
    *,
    credentials: Credentials | None = None,
) -> str:
    """
    Upload *local_path* to Drive as *filename*.

    If *folder_id* is set, the file is created inside that folder; otherwise it
    is placed in the authenticated user's Drive root.

    Returns a browser URL for the file (``webViewLink`` when available).
    """
    path = Path(local_path)
    if not path.is_file():
        raise FileNotFoundError(str(path))

    creds = credentials or get_credentials()
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    body: dict[str, Any] = {"name": filename}
    if folder_id:
        body["parents"] = [folder_id]

    media = MediaFileUpload(
        str(path),
        mimetype=_guess_mime(path),
        resumable=True,
    )

    created = (
        service.files()
        .create(
            body=body,
            media_body=media,
            fields="id, webViewLink, mimeType",
            supportsAllDrives=True,
        )
        .execute()
    )

    link = created.get("webViewLink")
    if link:
        return str(link)
    fid = created.get("id")
    if not fid:
        raise RuntimeError("Drive API did not return a file id.")
    return f"https://drive.google.com/file/d/{fid}/view"
