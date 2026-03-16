"""Tests for schema commands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from slides_agent.main import app

runner = CliRunner()


def test_schema_list_ok():
    result = runner.invoke(app, ["schema", "list"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert "presentation" in data["schemas"]
    assert "patch-plan" in data["schemas"]
    assert "error" in data["schemas"]


def test_schema_show_presentation():
    result = runner.invoke(app, ["schema", "show", "presentation"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert "properties" in schema or "$defs" in schema


def test_schema_show_patch_plan():
    result = runner.invoke(app, ["schema", "show", "patch-plan"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert "properties" in schema or "$defs" in schema


def test_schema_show_error():
    result = runner.invoke(app, ["schema", "show", "error"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    # Should have ok, error_code, detail fields
    props = schema.get("properties", {})
    assert "error_code" in props
    assert "detail" in props


def test_schema_show_invalid_name():
    result = runner.invoke(app, ["schema", "show", "nonexistent-schema"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error_code"] == "not_found"


def test_schema_show_update_text_op():
    result = runner.invoke(app, ["schema", "show", "patch-operation-update-text"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    props = schema.get("properties", {})
    assert "element_id" in props
    assert "text" in props


def test_schema_show_pretty():
    result = runner.invoke(app, ["schema", "show", "presentation", "--pretty"])
    assert result.exit_code == 0
    assert "\n" in result.stdout
