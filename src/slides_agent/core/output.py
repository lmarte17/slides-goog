"""JSON output helpers for slides-agent.

All commands emit JSON to stdout. This module provides the standard
output envelope and helpers for consistent formatting.

Standard success envelope
-------------------------
{
  "ok": true,
  "presentation_id": "...",         # present for presentation-scoped commands
  "applied_operations": [...],       # for mutating commands
  "warnings": [],
  "errors": []
}

Standard dry-run envelope
-------------------------
{
  "ok": true,
  "dry_run": true,
  "presentation_id": "...",
  "would_apply": [...],             # API request objects that would be sent
  "warnings": [],
  "errors": []
}
"""

from __future__ import annotations

import json
import sys
from typing import Any

from pydantic import BaseModel


def emit(data: Any, pretty: bool = False) -> None:
    """Write data to stdout as JSON.

    Parameters
    ----------
    data:
        A dict, Pydantic model, or any JSON-serialisable value.
    pretty:
        If True, output indented JSON for human readability.
    """
    indent = 2 if pretty else None
    if isinstance(data, BaseModel):
        print(data.model_dump_json(indent=indent))
    elif isinstance(data, dict) or isinstance(data, list):
        print(json.dumps(data, indent=indent, default=str))
    else:
        print(json.dumps(data, indent=indent, default=str))


def success_envelope(
    *,
    presentation_id: str | None = None,
    applied_operations: list[dict[str, Any]] | None = None,
    data: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a standard success response envelope."""
    out: dict[str, Any] = {"ok": True}
    if presentation_id is not None:
        out["presentation_id"] = presentation_id
    if applied_operations is not None:
        out["applied_operations"] = applied_operations
    if data is not None:
        out.update(data)
    out["warnings"] = warnings or []
    out["errors"] = []
    return out


def dry_run_envelope(
    *,
    presentation_id: str | None = None,
    would_apply: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a standard dry-run response envelope."""
    return {
        "ok": True,
        "dry_run": True,
        "presentation_id": presentation_id,
        "would_apply": would_apply or [],
        "warnings": warnings or [],
        "errors": [],
    }
