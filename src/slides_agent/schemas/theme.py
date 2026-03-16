"""Pydantic schemas for theme/style commands."""

from __future__ import annotations

from pydantic import BaseModel

from slides_agent.core.models import ThemeSpec


class ThemeApplyOutput(BaseModel):
    ok: bool = True
    dry_run: bool = False
    presentation_id: str
    applied_spec: ThemeSpec
    slides_affected: list[str] = []
    elements_affected: int = 0
    warnings: list[str] = []
    errors: list[str] = []


class ThemeListOutput(BaseModel):
    ok: bool = True
    presets: list[ThemeSpec] = []
