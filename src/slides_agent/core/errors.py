"""Structured, machine-readable error model for slides-agent.

Every command that fails emits a JSON object conforming to AgentError.
Error codes are stable strings suitable for programmatic branching.

Error categories
----------------
auth_error          OAuth token missing, expired, or invalid scopes.
not_found           Presentation, slide, or element ID does not exist.
invalid_reference   A supplied ID was found but refers to the wrong type.
validation_error    Input data failed schema validation.
unsupported_operation   The requested operation is not supported by the API.
api_error           Google API returned an unexpected error.
rate_limited        Google API quota exceeded (429 / rateLimitExceeded).
conflict            Concurrent modification detected.
io_error            File read/write failure (credentials, plan files, etc.).
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    auth_error = "auth_error"
    not_found = "not_found"
    invalid_reference = "invalid_reference"
    validation_error = "validation_error"
    unsupported_operation = "unsupported_operation"
    api_error = "api_error"
    rate_limited = "rate_limited"
    conflict = "conflict"
    io_error = "io_error"


class AgentError(BaseModel):
    """Machine-readable error envelope returned by all failing commands."""

    ok: bool = False
    error_code: ErrorCode
    detail: str
    field: str | None = Field(
        default=None,
        description="The specific input field that caused the error, if applicable.",
    )
    hint: str | None = Field(
        default=None,
        description="A suggested remediation step for the agent or operator.",
    )
    raw: dict[str, Any] | None = Field(
        default=None,
        description="The raw API error body, when available.",
    )

    def emit(self, pretty: bool = False) -> None:
        """Write the error JSON to stdout and exit with code 1."""
        indent = 2 if pretty else None
        print(self.model_dump_json(indent=indent))
        sys.exit(1)


class AgentException(Exception):
    """Raised internally to short-circuit command execution with a structured error."""

    def __init__(self, error: AgentError) -> None:
        self.error = error
        super().__init__(error.detail)


def die(
    code: ErrorCode,
    detail: str,
    *,
    field: str | None = None,
    hint: str | None = None,
    raw: dict[str, Any] | None = None,
    pretty: bool = False,
) -> None:
    """Emit a structured error JSON to stdout and exit 1."""
    err = AgentError(error_code=code, detail=detail, field=field, hint=hint, raw=raw)
    err.emit(pretty=pretty)


def api_error_from_http(exc: Exception) -> AgentError:
    """Convert a googleapiclient.errors.HttpError into an AgentError."""
    from googleapiclient.errors import HttpError  # type: ignore[import]

    if isinstance(exc, HttpError):
        status = exc.resp.status
        try:
            body = json.loads(exc.content.decode())
        except Exception:
            body = {}

        message = body.get("error", {}).get("message", str(exc))
        errors = body.get("error", {}).get("errors", [])
        reason = errors[0].get("reason", "") if errors else ""

        if status == 401:
            code = ErrorCode.auth_error
            hint = "Run `slides-agent auth login` to refresh your credentials."
        elif status == 403 and "rateLimitExceeded" in reason:
            code = ErrorCode.rate_limited
            hint = "Wait a moment and retry, or reduce request frequency."
        elif status == 403:
            code = ErrorCode.auth_error
            hint = "Ensure your OAuth2 credentials have the required scopes."
        elif status == 404:
            code = ErrorCode.not_found
            hint = "Verify the presentation_id, slide_id, or element_id exists."
        elif status == 409:
            code = ErrorCode.conflict
            hint = "The presentation may have been modified concurrently. Retry."
        else:
            code = ErrorCode.api_error
            hint = None

        return AgentError(
            error_code=code,
            detail=message,
            hint=hint,
            raw=body or None,
        )

    return AgentError(
        error_code=ErrorCode.api_error,
        detail=str(exc),
    )
