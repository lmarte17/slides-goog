"""Pydantic output schemas for deck commands."""

from __future__ import annotations

from pydantic import BaseModel, Field

from slides_agent.core.models import PresentationSummary


class DeckInspectOutput(BaseModel):
    ok: bool = True
    presentation: PresentationSummary
    warnings: list[str] = []
    errors: list[str] = []


class DeckDuplicateOutput(BaseModel):
    ok: bool = True
    original_presentation_id: str
    new_presentation_id: str
    new_title: str
    drive_url: str | None = None
    warnings: list[str] = []
    errors: list[str] = []
