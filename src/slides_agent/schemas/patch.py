"""Pydantic schemas for patch plan/apply workflow.

Patch operations
----------------
Each operation in a patch plan is typed and carries all the information
needed to generate the corresponding Google Slides API batchUpdate request.

Supported operation types
-------------------------
update_text         Replace the full text of a specific element.
replace_text        Replace all occurrences of a string across the deck.
set_notes           Set speaker notes for a slide.
create_slide        Add a new slide at a given position.
delete_slide        Remove a slide by ID.
duplicate_slide     Copy a slide.
reorder_slide       Move a slide to a new index.
insert_image        Add an image to a slide.
replace_image       Swap an existing image element.
change_background   Change the background color of one or all slides.
update_style        Update text style properties on a specific element.
"""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Individual operation models
# ---------------------------------------------------------------------------


class UpdateTextOp(BaseModel):
    type: Literal["update_text"] = "update_text"
    presentation_id: str
    slide_id: str
    element_id: str
    text: str = Field(description="The new full text to set on the element.")


class ReplaceTextOp(BaseModel):
    type: Literal["replace_text"] = "replace_text"
    presentation_id: str
    find: str
    replace: str
    match_case: bool = True


class SetNotesOp(BaseModel):
    type: Literal["set_notes"] = "set_notes"
    presentation_id: str
    slide_id: str
    text: str


class CreateSlideOp(BaseModel):
    type: Literal["create_slide"] = "create_slide"
    presentation_id: str
    insertion_index: int | None = Field(
        default=None,
        description="0-based index where slide will be inserted. Appends if omitted.",
    )
    layout: str | None = Field(
        default=None,
        description="Layout predefined type e.g. 'TITLE_AND_BODY'.",
    )


class DeleteSlideOp(BaseModel):
    type: Literal["delete_slide"] = "delete_slide"
    presentation_id: str
    slide_id: str


class DuplicateSlideOp(BaseModel):
    type: Literal["duplicate_slide"] = "duplicate_slide"
    presentation_id: str
    slide_id: str


class ReorderSlideOp(BaseModel):
    type: Literal["reorder_slide"] = "reorder_slide"
    presentation_id: str
    slide_id: str
    insertion_index: int = Field(description="0-based target index.")


class InsertImageOp(BaseModel):
    type: Literal["insert_image"] = "insert_image"
    presentation_id: str
    slide_id: str
    image_url: str = Field(description="Publicly accessible URL for the image.")
    left_emu: float = 0.0
    top_emu: float = 0.0
    width_emu: float | None = None
    height_emu: float | None = None


class ReplaceImageOp(BaseModel):
    type: Literal["replace_image"] = "replace_image"
    presentation_id: str
    slide_id: str
    element_id: str
    image_url: str


class ChangeBackgroundOp(BaseModel):
    type: Literal["change_background"] = "change_background"
    presentation_id: str
    slide_id: str | None = Field(
        default=None,
        description="Specific slide to change. If omitted, applies to all slides.",
    )
    color_hex: str = Field(description="Hex color string e.g. '#1A73E8'.")


class UpdateStyleOp(BaseModel):
    type: Literal["update_style"] = "update_style"
    presentation_id: str
    slide_id: str
    element_id: str
    bold: bool | None = None
    italic: bool | None = None
    font_family: str | None = None
    font_size_pt: float | None = None
    foreground_color_hex: str | None = None


# Union of all operation types
PatchOperation = Union[
    UpdateTextOp,
    ReplaceTextOp,
    SetNotesOp,
    CreateSlideOp,
    DeleteSlideOp,
    DuplicateSlideOp,
    ReorderSlideOp,
    InsertImageOp,
    ReplaceImageOp,
    ChangeBackgroundOp,
    UpdateStyleOp,
]


# ---------------------------------------------------------------------------
# Plan and apply schemas
# ---------------------------------------------------------------------------


class ValidationWarning(BaseModel):
    operation_index: int
    message: str
    severity: Literal["warning", "error"] = "warning"


class PatchPlan(BaseModel):
    """Output of `patch plan`: a validated, apply-ready list of operations."""

    ok: bool = True
    presentation_id: str
    operation_count: int
    operations: list[dict[str, Any]] = Field(
        description="The validated operation list, ready to pass to `patch apply`."
    )
    unresolved_references: list[str] = Field(
        default_factory=list,
        description="IDs that could not be validated against the current presentation.",
    )
    validation_warnings: list[ValidationWarning] = []
    warnings: list[str] = []
    errors: list[str] = []


class PatchApplyReport(BaseModel):
    """Output of `patch apply`: execution results for each operation."""

    ok: bool = True
    dry_run: bool = False
    presentation_id: str
    total_operations: int
    succeeded: int
    failed: int
    results: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
