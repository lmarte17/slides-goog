"""Tests for the error model."""

from __future__ import annotations

import json

import pytest

from slides_agent.core.errors import AgentError, AgentException, ErrorCode, die


def test_agent_error_json():
    err = AgentError(
        error_code=ErrorCode.not_found,
        detail="Slide not found",
        hint="Check the slide ID.",
    )
    assert err.ok is False
    assert err.error_code == ErrorCode.not_found
    assert err.detail == "Slide not found"
    assert err.hint == "Check the slide ID."


def test_agent_error_model_dump_json():
    err = AgentError(error_code=ErrorCode.auth_error, detail="Token expired")
    data = json.loads(err.model_dump_json())
    assert data["ok"] is False
    assert data["error_code"] == "auth_error"


def test_agent_exception_carries_error():
    err = AgentError(error_code=ErrorCode.api_error, detail="API failed")
    exc = AgentException(err)
    assert exc.error is err
    assert str(exc) == "API failed"


def test_all_error_codes_valid():
    for code in ErrorCode:
        err = AgentError(error_code=code, detail="test")
        assert err.error_code == code


def test_agent_error_without_optional_fields():
    err = AgentError(error_code=ErrorCode.conflict, detail="Conflict")
    assert err.field is None
    assert err.hint is None
    assert err.raw is None
