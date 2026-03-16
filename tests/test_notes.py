"""Tests for notes commands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from slides_agent.main import app
from tests.conftest import SAMPLE_PRESENTATION

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_all(mock_auth, mock_build_clients):
    yield


def test_notes_get_ok(mock_build_clients):
    result = runner.invoke(
        app,
        ["notes", "get", "--presentation-id", "test_presentation_id", "--slide-id", "slide_1"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["notes_text"] == "Talk track here."
    assert data["slide_id"] == "slide_1"


def test_notes_get_empty_slide(mock_build_clients):
    """Slide 2 has an empty notes page."""
    result = runner.invoke(
        app,
        ["notes", "get", "--presentation-id", "test_presentation_id", "--slide-id", "slide_2"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["notes_text"] is None


def test_notes_get_invalid_slide(mock_build_clients):
    result = runner.invoke(
        app,
        ["notes", "get", "--presentation-id", "test_presentation_id", "--slide-id", "nonexistent"],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error_code"] == "not_found"


def test_notes_set_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "notes", "set",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_1",
            "--text", "New speaker notes",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert len(data["would_apply"]) == 2
    assert "deleteText" in data["would_apply"][0]
    assert "insertText" in data["would_apply"][1]
    assert data["would_apply"][1]["insertText"]["text"] == "New speaker notes"


def test_notes_set_ok(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "notes", "set",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_1",
            "--text", "Updated notes",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    op = data["applied_operations"][0]
    assert op["type"] == "set_notes"
    assert op["slide_id"] == "slide_1"


def test_notes_clear_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "notes", "clear",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert "deleteText" in data["would_apply"][0]
