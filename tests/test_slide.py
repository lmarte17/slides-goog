"""Tests for slide commands."""

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


def test_slide_list_ok(mock_build_clients):
    result = runner.invoke(app, ["slide", "list", "--presentation-id", "test_presentation_id"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["slide_count"] == 2
    assert len(data["slides"]) == 2


def test_slide_list_ids(mock_build_clients):
    result = runner.invoke(app, ["slide", "list", "--presentation-id", "test_presentation_id"])
    data = json.loads(result.stdout)
    ids = [s["slide_id"] for s in data["slides"]]
    assert ids == ["slide_1", "slide_2"]


def test_slide_create_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        ["slide", "create", "--presentation-id", "test_presentation_id", "--layout", "BLANK", "--dry-run"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert len(data["would_apply"]) == 1
    assert "createSlide" in data["would_apply"][0]


def test_slide_create_ok(mock_build_clients):
    slides_client, _ = mock_build_clients
    slides_client.batch_update.return_value = {
        "replies": [{"createSlide": {"objectId": "new_slide_id"}}]
    }
    result = runner.invoke(
        app,
        ["slide", "create", "--presentation-id", "test_presentation_id", "--layout", "TITLE_AND_BODY"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    op = data["applied_operations"][0]
    assert op["type"] == "create_slide"
    assert op["slide_id"] == "new_slide_id"


def test_slide_delete_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        ["slide", "delete", "--presentation-id", "test_presentation_id", "--slide-id", "slide_1", "--dry-run"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert "deleteObject" in data["would_apply"][0]


def test_slide_delete_force(mock_build_clients):
    result = runner.invoke(
        app,
        ["slide", "delete", "--presentation-id", "test_presentation_id", "--slide-id", "slide_1", "--force"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["applied_operations"][0]["type"] == "delete_slide"


def test_slide_duplicate_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        ["slide", "duplicate", "--presentation-id", "test_presentation_id", "--slide-id", "slide_1", "--dry-run"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert "duplicateObject" in data["would_apply"][0]


def test_slide_reorder_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "slide", "reorder",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_2",
            "--insertion-index", "0",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    req = data["would_apply"][0]
    assert "updateSlidesPosition" in req
    assert req["updateSlidesPosition"]["insertionIndex"] == 0


def test_slide_background_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "slide", "background",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_1",
            "--color", "#1A73E8",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert "updatePageProperties" in data["would_apply"][0]


def test_slide_background_invalid_color(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "slide", "background",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_1",
            "--color", "notacolor",
        ],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error_code"] == "validation_error"
