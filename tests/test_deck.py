"""Tests for deck commands."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from slides_agent.main import app
from tests.conftest import SAMPLE_PRESENTATION


runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_all(mock_auth, mock_build_clients):
    """Auto-use fixtures for all deck tests."""
    yield


def test_deck_inspect_ok(mock_build_clients):
    slides_client, _ = mock_build_clients
    slides_client.get_presentation.return_value = SAMPLE_PRESENTATION

    result = runner.invoke(app, ["deck", "inspect", "--presentation-id", "test_presentation_id"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["presentation"]["presentation_id"] == "test_presentation_id"
    assert data["presentation"]["slide_count"] == 2


def test_deck_inspect_slide_ids(mock_build_clients):
    result = runner.invoke(app, ["deck", "inspect", "--presentation-id", "test_presentation_id"])
    data = json.loads(result.stdout)
    slide_ids = [s["slide_id"] for s in data["presentation"]["slides"]]
    assert "slide_1" in slide_ids
    assert "slide_2" in slide_ids


def test_deck_inspect_elements(mock_build_clients):
    result = runner.invoke(app, ["deck", "inspect", "--presentation-id", "test_presentation_id"])
    data = json.loads(result.stdout)
    first_slide = data["presentation"]["slides"][0]
    assert len(first_slide["elements"]) == 2
    title = first_slide["elements"][0]
    assert title["element_id"] == "title_element_1"
    assert title["placeholder_type"] == "TITLE"
    assert title["text"]["raw_text"] == "Hello World"


def test_deck_inspect_pretty(mock_build_clients):
    result = runner.invoke(app, ["deck", "inspect", "--presentation-id", "test_presentation_id", "--pretty"])
    assert result.exit_code == 0
    assert "\n" in result.stdout


def test_deck_inspect_schema():
    result = runner.invoke(app, ["deck", "inspect", "--presentation-id", "abc", "--schema"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "properties" in data or "$defs" in data


def test_deck_inspect_examples():
    result = runner.invoke(app, ["deck", "inspect", "--presentation-id", "abc", "--examples"])
    assert result.exit_code == 0
    assert "slides-agent" in result.stdout


def test_deck_duplicate_ok(mock_build_clients):
    result = runner.invoke(
        app,
        ["deck", "duplicate", "--presentation-id", "test_presentation_id", "--title", "My Copy"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["new_presentation_id"] == "new_presentation_id"
    assert data["new_title"] == "My Copy"
    assert "docs.google.com" in data["drive_url"]
