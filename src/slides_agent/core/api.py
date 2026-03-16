"""Google API client wrapper for slides-agent.

Provides thin, typed accessors for Google Slides and Drive APIs.
All methods raise AgentException on failure so callers get structured errors.

Usage
-----
    from slides_agent.core.api import SlidesClient

    client = SlidesClient.from_credentials(creds)
    presentation = client.get_presentation("abc123")
    client.batch_update("abc123", [{"createSlide": {...}}])
"""

from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build  # type: ignore[import]
from googleapiclient.errors import HttpError  # type: ignore[import]

from .errors import AgentException, api_error_from_http


class SlidesClient:
    """Wrapper around the Google Slides API."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_credentials(cls, creds: Any) -> "SlidesClient":
        service = build("slides", "v1", credentials=creds)
        return cls(service)

    def get_presentation(self, presentation_id: str) -> dict[str, Any]:
        """Fetch a full presentation object from the API."""
        try:
            return (
                self._service.presentations()
                .get(presentationId=presentation_id)
                .execute()
            )
        except HttpError as exc:
            raise AgentException(api_error_from_http(exc)) from exc

    def batch_update(
        self, presentation_id: str, requests: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Apply a list of batchUpdate requests to a presentation.

        Parameters
        ----------
        presentation_id:
            The ID of the presentation to modify.
        requests:
            A list of request dicts in Google Slides API batchUpdate format.

        Returns
        -------
        The raw API batchUpdate response.
        """
        try:
            body = {"requests": requests}
            return (
                self._service.presentations()
                .batchUpdate(presentationId=presentation_id, body=body)
                .execute()
            )
        except HttpError as exc:
            raise AgentException(api_error_from_http(exc)) from exc

    def get_page(self, presentation_id: str, page_object_id: str) -> dict[str, Any]:
        """Fetch a single page (slide) from the API."""
        try:
            return (
                self._service.presentations()
                .pages()
                .get(presentationId=presentation_id, pageObjectId=page_object_id)
                .execute()
            )
        except HttpError as exc:
            raise AgentException(api_error_from_http(exc)) from exc


class DriveClient:
    """Wrapper around the Google Drive API."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_credentials(cls, creds: Any) -> "DriveClient":
        service = build("drive", "v3", credentials=creds)
        return cls(service)

    def copy_file(self, file_id: str, title: str) -> dict[str, Any]:
        """Duplicate a Drive file (presentation copy)."""
        try:
            body = {"name": title}
            return self._service.files().copy(fileId=file_id, body=body).execute()
        except HttpError as exc:
            raise AgentException(api_error_from_http(exc)) from exc

    def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        """Get Drive file metadata."""
        try:
            return (
                self._service.files()
                .get(fileId=file_id, fields="id,name,mimeType,createdTime,modifiedTime,webViewLink")
                .execute()
            )
        except HttpError as exc:
            raise AgentException(api_error_from_http(exc)) from exc

    def export_file(self, file_id: str, mime_type: str) -> bytes:
        """Export a Drive file to the given MIME type (e.g., application/pdf)."""
        try:
            return (
                self._service.files()
                .export(fileId=file_id, mimeType=mime_type)
                .execute()
            )
        except HttpError as exc:
            raise AgentException(api_error_from_http(exc)) from exc

    def upload_image(self, file_path: str, mime_type: str = "image/png") -> str:
        """Upload an image to Drive and return its public URL.

        Uses resumable upload and makes the file publicly readable so the
        Slides API can reference it by URL.

        Returns
        -------
        The public download URL for the uploaded image.
        """
        from googleapiclient.http import MediaFileUpload  # type: ignore[import]

        try:
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            file_metadata = {"name": file_path.split("/")[-1]}
            uploaded = (
                self._service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            file_id = uploaded["id"]
            # Make it publicly readable
            self._service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()
            return f"https://drive.google.com/uc?id={file_id}"
        except HttpError as exc:
            raise AgentException(api_error_from_http(exc)) from exc


def build_clients(creds: Any) -> tuple[SlidesClient, DriveClient]:
    """Convenience function: build both clients from credentials."""
    return SlidesClient.from_credentials(creds), DriveClient.from_credentials(creds)
