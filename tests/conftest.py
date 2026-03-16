"""Shared pytest fixtures and mock API responses."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

SAMPLE_SLIDE_ELEMENT = {
    "objectId": "title_element_1",
    "size": {
        "width": {"magnitude": 6858000, "unit": "EMU"},
        "height": {"magnitude": 1143000, "unit": "EMU"},
    },
    "transform": {
        "scaleX": 1,
        "scaleY": 1,
        "translateX": 457200,
        "translateY": 274638,
        "unit": "EMU",
    },
    "shape": {
        "shapeType": "TEXT_BOX",
        "placeholder": {"type": "TITLE", "index": 0},
        "text": {
            "textElements": [
                {"startIndex": 0, "paragraphMarker": {"style": {"alignment": "LEFT"}}},
                {
                    "startIndex": 0,
                    "endIndex": 11,
                    "textRun": {
                        "content": "Hello World",
                        "style": {
                            "bold": False,
                            "italic": False,
                            "fontFamily": "Google Sans",
                            "fontSize": {"magnitude": 36, "unit": "PT"},
                        },
                    },
                },
            ]
        },
    },
}

SAMPLE_IMAGE_ELEMENT = {
    "objectId": "image_element_1",
    "size": {
        "width": {"magnitude": 3000000, "unit": "EMU"},
        "height": {"magnitude": 2000000, "unit": "EMU"},
    },
    "transform": {
        "scaleX": 1,
        "scaleY": 1,
        "translateX": 100000,
        "translateY": 100000,
        "unit": "EMU",
    },
    "image": {
        "contentUrl": "https://example.com/image.png",
        "sourceUrl": "https://example.com/image.png",
    },
}

SAMPLE_NOTES_PAGE = {
    "objectId": "notes_page_1",
    "pageElements": [
        {
            "objectId": "notes_body_1",
            "shape": {
                "placeholder": {"type": "BODY"},
                "text": {
                    "textElements": [
                        {"startIndex": 0, "paragraphMarker": {}},
                        {
                            "startIndex": 0,
                            "endIndex": 16,
                            "textRun": {"content": "Talk track here.", "style": {}},
                        },
                    ]
                },
            },
        }
    ],
}

SAMPLE_SLIDE = {
    "objectId": "slide_1",
    "pageElements": [SAMPLE_SLIDE_ELEMENT, SAMPLE_IMAGE_ELEMENT],
    "slideProperties": {
        "layoutObjectId": "layout_title",
        "masterObjectId": "master_1",
        "notesPage": SAMPLE_NOTES_PAGE,
    },
    "pageProperties": {
        "pageBackgroundFill": {
            "solidFill": {
                "color": {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}
            }
        }
    },
}

SAMPLE_SLIDE_2 = {
    "objectId": "slide_2",
    "pageElements": [
        {
            "objectId": "body_element_2",
            "shape": {
                "shapeType": "TEXT_BOX",
                "placeholder": {"type": "BODY"},
                "text": {
                    "textElements": [
                        {"startIndex": 0, "paragraphMarker": {}},
                        {
                            "startIndex": 0,
                            "endIndex": 22,
                            "textRun": {"content": "{{customer}} overview", "style": {}},
                        },
                    ]
                },
            },
            "size": {"width": {"magnitude": 6858000, "unit": "EMU"}, "height": {"magnitude": 2000000, "unit": "EMU"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0, "translateY": 0, "unit": "EMU"},
        }
    ],
    "slideProperties": {
        "layoutObjectId": "layout_body",
        "masterObjectId": "master_1",
        "notesPage": {"objectId": "notes_2", "pageElements": []},
    },
}

SAMPLE_PRESENTATION = {
    "presentationId": "test_presentation_id",
    "title": "Test Presentation",
    "locale": "en",
    "pageSize": {
        "width": {"magnitude": 9144000, "unit": "EMU"},
        "height": {"magnitude": 5143500, "unit": "EMU"},
    },
    "slides": [SAMPLE_SLIDE, SAMPLE_SLIDE_2],
    "masters": [{"objectId": "master_1", "masterProperties": {"displayName": "Default"}}],
    "layouts": [
        {
            "objectId": "layout_title",
            "layoutProperties": {
                "name": "TITLE",
                "displayName": "Title",
                "masterObjectId": "master_1",
            },
        }
    ],
}


# ---------------------------------------------------------------------------
# Mock credentials
# ---------------------------------------------------------------------------


class MockCredentials:
    valid = True
    expired = False
    scopes = {"https://www.googleapis.com/auth/presentations", "https://www.googleapis.com/auth/drive"}
    client_id = "mock_client_id"

    def to_json(self):
        return json.dumps({"token": "mock_token", "client_id": "mock_client_id"})


@pytest.fixture
def mock_creds():
    return MockCredentials()


@pytest.fixture
def mock_slides_client(mock_creds):
    """A mock SlidesClient that returns SAMPLE_PRESENTATION."""
    from slides_agent.core.api import SlidesClient

    client = MagicMock(spec=SlidesClient)
    client.get_presentation.return_value = SAMPLE_PRESENTATION
    client.batch_update.return_value = {
        "presentationId": "test_presentation_id",
        "replies": [{}],
    }
    return client


@pytest.fixture
def mock_drive_client(mock_creds):
    from slides_agent.core.api import DriveClient

    client = MagicMock(spec=DriveClient)
    client.copy_file.return_value = {
        "id": "new_presentation_id",
        "name": "Copy of Test Presentation",
    }
    client.get_file_metadata.return_value = {
        "id": "test_presentation_id",
        "name": "Test Presentation",
        "mimeType": "application/vnd.google-apps.presentation",
    }
    return client


@pytest.fixture
def mock_auth(mock_creds):
    """Patch auth.require_credentials to return mock credentials."""
    with patch("slides_agent.core.auth.require_credentials", return_value=mock_creds):
        yield mock_creds


@pytest.fixture
def mock_build_clients(mock_slides_client, mock_drive_client):
    """Patch build_clients in all command modules (each imports it directly)."""
    import contextlib

    _COMMAND_MODULES = [
        "deck", "slide", "notes", "text", "patch", "template",
        "image", "element", "theme", "export",
    ]
    patches = [
        patch(
            f"slides_agent.commands.{mod}.build_clients",
            return_value=(mock_slides_client, mock_drive_client),
        )
        for mod in _COMMAND_MODULES
    ]
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield mock_slides_client, mock_drive_client


@pytest.fixture
def cli_runner():
    from typer.testing import CliRunner
    return CliRunner()


@pytest.fixture
def sample_presentation():
    return SAMPLE_PRESENTATION


@pytest.fixture
def tmp_ops_file(tmp_path):
    """Create a temporary operations JSON file."""
    ops = [
        {
            "type": "update_text",
            "presentation_id": "test_presentation_id",
            "slide_id": "slide_1",
            "element_id": "title_element_1",
            "text": "Updated Title",
        },
        {
            "type": "replace_text",
            "presentation_id": "test_presentation_id",
            "find": "{{customer}}",
            "replace": "Acme Corp",
        },
    ]
    f = tmp_path / "ops.json"
    f.write_text(json.dumps(ops))
    return f


@pytest.fixture
def tmp_values_file(tmp_path):
    """Create a temporary template values JSON file."""
    values = {"customer": "Acme Corp", "date": "2025-01-15", "version": "v3"}
    f = tmp_path / "values.json"
    f.write_text(json.dumps(values))
    return f
