"""Shared Pydantic v2 models used across all slides-agent commands.

These models define the canonical data shapes that agents consume.
Every inspect/list command returns instances of these models serialised to JSON.

Model hierarchy
---------------
PresentationSummary
  └─ slides: list[SlideSummary]
       └─ elements: list[PageElement]
            ├─ text: TextContent | None
            └─ image: ImageContent | None

Agents should use `presentation_id`, `slide_id`, and `element_id` as stable
handles to target specific objects in subsequent mutation commands.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


class Size(BaseModel):
    """Width and height in EMUs (English Metric Units). 914400 EMUs = 1 inch."""

    width: float
    height: float
    unit: str = "EMU"


class Transform(BaseModel):
    """AffineTransform from the Slides API: position + scale + shear."""

    scale_x: float = 1.0
    scale_y: float = 1.0
    shear_x: float = 0.0
    shear_y: float = 0.0
    translate_x: float = 0.0
    translate_y: float = 0.0
    unit: str = "EMU"


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


class TextRun(BaseModel):
    """A single run of text with uniform styling."""

    content: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_family: str | None = None
    font_size_pt: float | None = None
    foreground_color: str | None = Field(
        default=None, description="Hex color string e.g. '#FF0000'."
    )
    link_url: str | None = None


class Paragraph(BaseModel):
    """A paragraph consisting of one or more text runs."""

    runs: list[TextRun] = []
    alignment: str | None = None  # "LEFT" | "CENTER" | "RIGHT" | "JUSTIFIED"
    space_above_pt: float | None = None
    space_below_pt: float | None = None


class TextContent(BaseModel):
    """Full text content of a text-bearing element."""

    raw_text: str = Field(description="Plain concatenated text, all runs joined.")
    paragraphs: list[Paragraph] = []


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


class ImageContent(BaseModel):
    """Image element metadata."""

    content_url: str | None = Field(
        default=None, description="Public URL of the image content."
    )
    source_url: str | None = Field(
        default=None, description="Original source URL if the image was inserted by URL."
    )


# ---------------------------------------------------------------------------
# Page Elements
# ---------------------------------------------------------------------------


class PageElement(BaseModel):
    """A single element on a slide (shape, image, table, chart, etc.)."""

    element_id: str
    element_type: Literal["shape", "image", "table", "chart", "video", "line", "group", "other"]
    title: str | None = Field(default=None, description="Alt text title.")
    description: str | None = Field(default=None, description="Alt text description.")
    placeholder_type: str | None = Field(
        default=None,
        description=(
            "Placeholder type if this is a layout placeholder "
            "(e.g. 'TITLE', 'BODY', 'SUBTITLE')."
        ),
    )
    size: Size | None = None
    transform: Transform | None = None
    text: TextContent | None = None
    image: ImageContent | None = None
    row_count: int | None = Field(default=None, description="For tables: number of rows.")
    column_count: int | None = Field(default=None, description="For tables: number of columns.")


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------


class SlideSummary(BaseModel):
    """A single slide, including its elements and notes."""

    slide_id: str
    slide_index: int = Field(description="0-based position in the deck.")
    layout_name: str | None = None
    layout_object_id: str | None = None
    master_object_id: str | None = None
    notes_text: str | None = Field(
        default=None, description="Plain text of the speaker notes."
    )
    elements: list[PageElement] = []
    background_color: str | None = Field(
        default=None, description="Hex color of the slide background, if solid."
    )


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


class PresentationSummary(BaseModel):
    """Full inspection result for a presentation."""

    presentation_id: str
    title: str
    locale: str | None = None
    slide_width_emu: float | None = None
    slide_height_emu: float | None = None
    slide_count: int
    slides: list[SlideSummary] = []
    masters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of master objects with their IDs and names.",
    )
    layouts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of layout objects with their IDs, names, and types.",
    )


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


class ThemeColor(BaseModel):
    """A named theme color."""

    name: str
    hex_color: str = Field(description="Hex color string e.g. '#1A73E8'.")


class FontSpec(BaseModel):
    """A font specification for title or body text."""

    family: str
    size_pt: float | None = None
    bold: bool = False
    italic: bool = False


class ThemeSpec(BaseModel):
    """A theme preset that can be applied deck-wide via `theme apply`."""

    name: str | None = None
    colors: list[ThemeColor] = []
    title_font: FontSpec | None = None
    body_font: FontSpec | None = None
    background_color: str | None = Field(
        default=None, description="Hex color for slide backgrounds."
    )


# ---------------------------------------------------------------------------
# Operations (patch plan types)
# ---------------------------------------------------------------------------


class OperationType(str):
    UPDATE_TEXT = "update_text"
    DELETE_SLIDE = "delete_slide"
    CREATE_SLIDE = "create_slide"
    DUPLICATE_SLIDE = "duplicate_slide"
    REORDER_SLIDE = "reorder_slide"
    SET_NOTES = "set_notes"
    REPLACE_TEXT = "replace_text"
    INSERT_IMAGE = "insert_image"
    REPLACE_IMAGE = "replace_image"
    UPDATE_STYLE = "update_style"
    CHANGE_BACKGROUND = "change_background"
