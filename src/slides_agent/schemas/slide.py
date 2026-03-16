"""Pydantic output schemas for slide commands."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from slides_agent.core.models import SlideSummary


class SlideListOutput(BaseModel):
    ok: bool = True
    presentation_id: str
    slide_count: int
    slides: list[SlideSummary]
    warnings: list[str] = []
    errors: list[str] = []


class AppliedOperation(BaseModel):
    """A single operation that was applied (or would be applied) to a presentation."""

    type: str
    slide_id: str | None = None
    element_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class SlideMutationOutput(BaseModel):
    """Standard response for create/delete/duplicate/reorder operations."""

    ok: bool = True
    dry_run: bool = False
    presentation_id: str
    applied_operations: list[AppliedOperation] = []
    would_apply: list[dict[str, Any]] = Field(
        default_factory=list,
        description="API request objects that would be sent (dry-run only).",
    )
    warnings: list[str] = []
    errors: list[str] = []
