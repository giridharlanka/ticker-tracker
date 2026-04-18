"""Tests for Drive upload and Gmail send (mocked API)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


@patch("ticker_tracker.google.drive.build")
def test_upload_file_returns_link(mock_build: MagicMock, tmp_path: Path) -> None:
    f = tmp_path / "report.xlsx"
    f.write_bytes(b"fake-xlsx")

    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.files.return_value.create.return_value.execute.return_value = {
        "id": "fileid123",
        "webViewLink": "https://docs.google.com/file/d/fileid123/view",
    }
    fake_creds = MagicMock()

    from ticker_tracker.google.drive import upload_file

    url = upload_file(f, "Quarterly.xlsx", folder_id="folder99", credentials=fake_creds)

    assert url == "https://docs.google.com/file/d/fileid123/view"
    mock_build.assert_called_once_with("drive", "v3", credentials=fake_creds, cache_discovery=False)
    create = mock_service.files.return_value.create
    create.assert_called_once()
    kwargs = create.call_args.kwargs
    assert kwargs["body"]["name"] == "Quarterly.xlsx"
    assert kwargs["body"]["parents"] == ["folder99"]


@patch("ticker_tracker.google.drive.build")
def test_upload_file_fallback_url(mock_build: MagicMock, tmp_path: Path) -> None:
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.files.return_value.create.return_value.execute.return_value = {"id": "abc"}
    fake_creds = MagicMock()

    from ticker_tracker.google.drive import upload_file

    url = upload_file(f, "a.bin", credentials=fake_creds)
    assert url == "https://drive.google.com/file/d/abc/view"


@patch("ticker_tracker.google.gmail.build")
def test_send_email_builds_raw_and_calls_api(mock_build: MagicMock, tmp_path: Path) -> None:
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "msg-1",
        "threadId": "t-1",
    }
    fake_creds = MagicMock()
    att = tmp_path / "data.xlsx"
    att.write_bytes(b"excel-bytes")

    from ticker_tracker.google.gmail import send_email

    out = send_email(
        "you@example.com",
        "Subject line",
        "<p>Hello</p>",
        attachment_path=att,
        credentials=fake_creds,
    )

    assert out["id"] == "msg-1"
    mock_build.assert_called_once_with("gmail", "v1", credentials=fake_creds, cache_discovery=False)
    send = mock_service.users.return_value.messages.return_value.send
    send.assert_called_once()
    call_kw = send.call_args.kwargs
    assert call_kw["userId"] == "me"
    raw = call_kw["body"]["raw"]
    assert isinstance(raw, str) and len(raw) > 20
