"""Tests for patch plan/apply commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slides_agent.main import app
from tests.conftest import SAMPLE_PRESENTATION

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_all(mock_auth, mock_build_clients):
    yield


def test_patch_plan_ok(mock_build_clients, tmp_ops_file):
    result = runner.invoke(
        app,
        [
            "patch", "plan",
            "--presentation-id", "test_presentation_id",
            "--operations-file", str(tmp_ops_file),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["presentation_id"] == "test_presentation_id"
    assert data["operation_count"] == 2
    assert len(data["operations"]) == 2


def test_patch_plan_resolves_valid_references(mock_build_clients, tmp_ops_file):
    result = runner.invoke(
        app,
        [
            "patch", "plan",
            "--presentation-id", "test_presentation_id",
            "--operations-file", str(tmp_ops_file),
        ],
    )
    data = json.loads(result.stdout)
    assert data["unresolved_references"] == []


def test_patch_plan_detects_invalid_references(mock_build_clients, tmp_path):
    ops = [
        {
            "type": "update_text",
            "presentation_id": "test_presentation_id",
            "slide_id": "nonexistent_slide",
            "element_id": "nonexistent_element",
            "text": "Hi",
        }
    ]
    ops_file = tmp_path / "bad_ops.json"
    ops_file.write_text(json.dumps(ops))

    result = runner.invoke(
        app,
        [
            "patch", "plan",
            "--presentation-id", "test_presentation_id",
            "--operations-file", str(ops_file),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data["unresolved_references"]) > 0


def test_patch_plan_missing_file(mock_build_clients):
    result = runner.invoke(
        app,
        [
            "patch", "plan",
            "--presentation-id", "test_presentation_id",
            "--operations-file", "/nonexistent/ops.json",
        ],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error_code"] == "io_error"


def test_patch_apply_dry_run(mock_build_clients, tmp_path, tmp_ops_file):
    # First create a plan
    plan_result = runner.invoke(
        app,
        [
            "patch", "plan",
            "--presentation-id", "test_presentation_id",
            "--operations-file", str(tmp_ops_file),
        ],
    )
    plan_data = json.loads(plan_result.stdout)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan_data))

    # Now apply in dry-run
    result = runner.invoke(
        app,
        ["patch", "apply", "--plan-file", str(plan_file), "--dry-run"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert len(data["would_apply"]) > 0


def test_patch_apply_ok(mock_build_clients, tmp_path, tmp_ops_file):
    plan_result = runner.invoke(
        app,
        [
            "patch", "plan",
            "--presentation-id", "test_presentation_id",
            "--operations-file", str(tmp_ops_file),
        ],
    )
    plan_data = json.loads(plan_result.stdout)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan_data))

    result = runner.invoke(
        app,
        ["patch", "apply", "--plan-file", str(plan_file)],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["failed"] == 0


def test_patch_validate_ok(mock_build_clients, tmp_path, tmp_ops_file):
    # Create a valid plan
    plan_result = runner.invoke(
        app,
        [
            "patch", "plan",
            "--presentation-id", "test_presentation_id",
            "--operations-file", str(tmp_ops_file),
        ],
    )
    plan_data = json.loads(plan_result.stdout)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan_data))

    result = runner.invoke(app, ["patch", "validate", "--plan-file", str(plan_file)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["valid"] is True
    assert data["unresolved_references"] == []


def test_patch_plan_invalid_json(mock_build_clients, tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json {")
    result = runner.invoke(
        app,
        [
            "patch", "plan",
            "--presentation-id", "test_presentation_id",
            "--operations-file", str(bad_file),
        ],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error_code"] == "validation_error"
