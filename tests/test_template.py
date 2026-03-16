"""Tests for template commands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from slides_agent.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_all(mock_auth, mock_build_clients):
    yield


def test_template_inspect_finds_tokens(mock_build_clients):
    """Slide 2 has {{customer}} in its text."""
    result = runner.invoke(
        app,
        ["template", "inspect", "--presentation-id", "test_presentation_id"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert "customer" in data["tokens"]
    assert data["token_count"] >= 1


def test_template_inspect_no_tokens(mock_build_clients):
    """If no tokens, should return empty and a warning."""
    slides_client, _ = mock_build_clients
    slides_client.get_presentation.return_value = {
        "presentationId": "no_tokens",
        "title": "No Tokens",
        "slides": [],
        "masters": [],
        "layouts": [],
        "pageSize": {"width": {"magnitude": 9144000, "unit": "EMU"}, "height": {"magnitude": 5143500, "unit": "EMU"}},
    }
    result = runner.invoke(
        app,
        ["template", "inspect", "--presentation-id", "no_tokens"],
    )
    data = json.loads(result.stdout)
    assert data["token_count"] == 0
    assert len(data["warnings"]) > 0


def test_template_fill_dry_run(mock_build_clients, tmp_values_file):
    result = runner.invoke(
        app,
        [
            "template", "fill",
            "--presentation-id", "test_presentation_id",
            "--values-file", str(tmp_values_file),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert len(data["would_apply"]) == 3  # 3 tokens in values file


def test_template_fill_ok(mock_build_clients, tmp_values_file):
    slides_client, _ = mock_build_clients
    slides_client.batch_update.return_value = {
        "replies": [
            {"replaceAllText": {"occurrencesChanged": 1}},
            {"replaceAllText": {"occurrencesChanged": 0}},
            {"replaceAllText": {"occurrencesChanged": 0}},
        ]
    }
    result = runner.invoke(
        app,
        [
            "template", "fill",
            "--presentation-id", "test_presentation_id",
            "--values-file", str(tmp_values_file),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert len(data["applied_replacements"]) == 3


def test_template_fill_missing_file(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "template", "fill",
            "--presentation-id", "test_presentation_id",
            "--values-file", "/nonexistent/values.json",
        ],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error_code"] == "io_error"


def test_template_create_dry_run(mock_build_clients, tmp_values_file):
    result = runner.invoke(
        app,
        [
            "template", "create",
            "--template-id", "template_presentation_id",
            "--title", "Acme QBR",
            "--values-file", str(tmp_values_file),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True


def test_template_create_ok(mock_build_clients, tmp_values_file):
    slides_client, drive_client = mock_build_clients
    slides_client.batch_update.return_value = {
        "replies": [
            {"replaceAllText": {"occurrencesChanged": 1}},
            {"replaceAllText": {"occurrencesChanged": 0}},
            {"replaceAllText": {"occurrencesChanged": 0}},
        ]
    }
    result = runner.invoke(
        app,
        [
            "template", "create",
            "--template-id", "template_id",
            "--title", "Acme QBR",
            "--values-file", str(tmp_values_file),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["new_presentation_id"] == "new_presentation_id"
    assert "docs.google.com" in data["drive_url"]
