"""Tests for core output helpers."""

from __future__ import annotations

import json

from slides_agent.core.output import dry_run_envelope, emit, success_envelope


def test_success_envelope_minimal():
    env = success_envelope(presentation_id="abc")
    assert env["ok"] is True
    assert env["presentation_id"] == "abc"
    assert env["warnings"] == []
    assert env["errors"] == []


def test_success_envelope_with_ops():
    ops = [{"type": "update_text", "slide_id": "g1", "element_id": "e1"}]
    env = success_envelope(presentation_id="abc", applied_operations=ops)
    assert env["applied_operations"] == ops


def test_dry_run_envelope():
    env = dry_run_envelope(
        presentation_id="abc",
        would_apply=[{"createSlide": {}}],
        warnings=["Note: dry run"],
    )
    assert env["ok"] is True
    assert env["dry_run"] is True
    assert len(env["would_apply"]) == 1
    assert "Note: dry run" in env["warnings"]


def test_emit_dict(capsys):
    emit({"ok": True, "value": 42})
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["value"] == 42


def test_emit_pretty(capsys):
    emit({"ok": True}, pretty=True)
    out = capsys.readouterr().out
    assert "\n" in out  # pretty-printed has newlines
    data = json.loads(out)
    assert data["ok"] is True
