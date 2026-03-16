"""Tests for text commands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from slides_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_all(mock_auth, mock_build_clients):
    yield


def test_text_replace_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "text", "replace",
            "--presentation-id", "test_presentation_id",
            "--find", "{{customer}}",
            "--replace", "Acme Corp",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    req = data["would_apply"][0]
    assert "replaceAllText" in req
    assert req["replaceAllText"]["containsText"]["text"] == "{{customer}}"
    assert req["replaceAllText"]["replaceText"] == "Acme Corp"


def test_text_replace_ok(mock_build_clients):
    slides_client, _ = mock_build_clients
    slides_client.batch_update.return_value = {
        "replies": [{"replaceAllText": {"occurrencesChanged": 3}}]
    }
    result = runner.invoke(
        app,
        [
            "text", "replace",
            "--presentation-id", "test_presentation_id",
            "--find", "{{customer}}",
            "--replace", "Acme Corp",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["applied_operations"][0]["occurrences_changed"] == 3


def test_text_replace_no_occurrences_warning(mock_build_clients):
    slides_client, _ = mock_build_clients
    slides_client.batch_update.return_value = {
        "replies": [{"replaceAllText": {"occurrencesChanged": 0}}]
    }
    result = runner.invoke(
        app,
        [
            "text", "replace",
            "--presentation-id", "test_presentation_id",
            "--find", "NONEXISTENT",
            "--replace", "value",
        ],
    )
    data = json.loads(result.stdout)
    assert len(data["warnings"]) > 0


def test_text_set_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "text", "set",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_1",
            "--element-id", "title_element_1",
            "--text", "New Title",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert len(data["would_apply"]) == 2  # deleteText + insertText
    assert "deleteText" in data["would_apply"][0]
    assert "insertText" in data["would_apply"][1]
    assert data["would_apply"][1]["insertText"]["text"] == "New Title"


def test_text_set_ok(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "text", "set",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_1",
            "--element-id", "title_element_1",
            "--text", "Updated Title",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    op = data["applied_operations"][0]
    assert op["type"] == "update_text"
    assert op["element_id"] == "title_element_1"


def test_text_clear_dry_run(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "text", "clear",
            "--presentation-id", "test_presentation_id",
            "--slide-id", "slide_1",
            "--element-id", "title_element_1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert "deleteText" in data["would_apply"][0]


def test_text_examples_flag():
    result = runner.invoke(app, ["text", "replace", "--examples"])
    assert result.exit_code == 0
    assert "slides-agent" in result.stdout
