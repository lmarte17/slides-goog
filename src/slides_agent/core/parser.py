"""Parsers that convert raw Google Slides API responses into Pydantic models.

The Google Slides API returns deeply nested JSON. These functions extract
the relevant fields and return typed Pydantic model instances.

All functions are pure and have no side effects — they only transform data.
"""

from __future__ import annotations

from typing import Any

from .models import (
    ImageContent,
    PageElement,
    Paragraph,
    PresentationSummary,
    Size,
    SlideSummary,
    TextContent,
    TextRun,
    Transform,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hex_from_rgb(rgb: dict[str, Any]) -> str:
    """Convert a Slides API RGB dict (0.0–1.0 floats) to a hex string."""
    r = int(rgb.get("red", 0) * 255)
    g = int(rgb.get("green", 0) * 255)
    b = int(rgb.get("blue", 0) * 255)
    return f"#{r:02X}{g:02X}{b:02X}"


def _color_from_property(prop: dict[str, Any] | None) -> str | None:
    if not prop:
        return None
    opaque_color = prop.get("opaqueColor")
    if opaque_color:
        rgb = opaque_color.get("rgbColor")
        if rgb:
            return _hex_from_rgb(rgb)
        theme_color = opaque_color.get("themeColor")
        if theme_color:
            return f"theme:{theme_color}"
    return None


def _parse_transform(raw: dict[str, Any] | None) -> Transform | None:
    if not raw:
        return None
    return Transform(
        scale_x=raw.get("scaleX", 1.0),
        scale_y=raw.get("scaleY", 1.0),
        shear_x=raw.get("shearX", 0.0),
        shear_y=raw.get("shearY", 0.0),
        translate_x=raw.get("translateX", 0.0),
        translate_y=raw.get("translateY", 0.0),
        unit=raw.get("unit", "EMU"),
    )


def _parse_size(raw: dict[str, Any] | None) -> Size | None:
    if not raw:
        return None
    w = raw.get("width", {})
    h = raw.get("height", {})
    return Size(
        width=w.get("magnitude", 0.0),
        height=h.get("magnitude", 0.0),
        unit=w.get("unit", "EMU"),
    )


def _parse_text_run(element: dict[str, Any]) -> TextRun | None:
    text_run = element.get("textRun")
    if not text_run:
        return None
    content = text_run.get("content", "")
    style = text_run.get("style", {})
    fg = _color_from_property(style.get("foregroundColor"))
    link = style.get("link", {}).get("url")
    font_size = style.get("fontSize", {})
    font_size_pt = font_size.get("magnitude") if font_size else None
    return TextRun(
        content=content,
        bold=style.get("bold", False),
        italic=style.get("italic", False),
        underline=style.get("underline", False),
        font_family=style.get("fontFamily"),
        font_size_pt=font_size_pt,
        foreground_color=fg,
        link_url=link,
    )


def _parse_text_content(text_content: dict[str, Any] | None) -> TextContent | None:
    if not text_content:
        return None

    raw_paragraphs = []
    for item in text_content.get("textElements", []):
        para_marker = item.get("paragraphMarker")
        if para_marker is not None:
            raw_paragraphs.append({"style": para_marker.get("style", {}), "runs": []})
        text_run = item.get("textRun")
        if text_run and raw_paragraphs:
            raw_paragraphs[-1]["runs"].append(item)

    paragraphs = []
    for rp in raw_paragraphs:
        runs = []
        for r in rp["runs"]:
            tr = _parse_text_run(r)
            if tr:
                runs.append(tr)
        style = rp.get("style", {})
        paragraph = Paragraph(
            runs=runs,
            alignment=style.get("alignment"),
        )
        paragraphs.append(paragraph)

    raw_text = "".join(
        run.content
        for para in paragraphs
        for run in para.runs
    )

    return TextContent(raw_text=raw_text, paragraphs=paragraphs)


def _parse_element(raw: dict[str, Any]) -> PageElement:
    element_id = raw.get("objectId", "")
    size = _parse_size(raw.get("size"))
    transform = _parse_transform(raw.get("transform"))

    # Determine type
    element_type: str = "other"
    text_content = None
    image_content = None
    placeholder_type = None
    row_count = None
    col_count = None
    title = raw.get("title")
    description = raw.get("description")

    shape = raw.get("shape")
    image = raw.get("image")
    table = raw.get("table")
    video = raw.get("video")
    line = raw.get("line")
    element_group = raw.get("elementGroup")
    chart = raw.get("sheetsChart")

    if shape:
        element_type = "shape"
        placeholder = shape.get("placeholder")
        if placeholder:
            placeholder_type = placeholder.get("type")
        text_content = _parse_text_content(shape.get("text"))
    elif image:
        element_type = "image"
        image_content = ImageContent(
            content_url=image.get("contentUrl"),
            source_url=image.get("sourceUrl"),
        )
    elif table:
        element_type = "table"
        row_count = table.get("rows", 0)
        col_count = table.get("columns", 0)
    elif video:
        element_type = "video"
    elif line:
        element_type = "line"
    elif element_group:
        element_type = "group"
    elif chart:
        element_type = "chart"

    return PageElement(
        element_id=element_id,
        element_type=element_type,  # type: ignore[arg-type]
        title=title,
        description=description,
        placeholder_type=placeholder_type,
        size=size,
        transform=transform,
        text=text_content,
        image=image_content,
        row_count=row_count,
        column_count=col_count,
    )


def _parse_notes(notes_page: dict[str, Any] | None) -> str | None:
    """Extract plain text from a slide's notes page."""
    if not notes_page:
        return None
    for element in notes_page.get("pageElements", []):
        shape = element.get("shape", {})
        placeholder = shape.get("placeholder", {})
        if placeholder.get("type") == "BODY":
            text_content = _parse_text_content(shape.get("text"))
            if text_content:
                return text_content.raw_text.strip() or None
    return None


def _background_color(page_properties: dict[str, Any] | None) -> str | None:
    if not page_properties:
        return None
    bg = page_properties.get("pageBackgroundFill", {})
    solid = bg.get("solidFill", {})
    color = solid.get("color", {})
    rgb = color.get("rgbColor")
    if rgb:
        return _hex_from_rgb(rgb)
    return None


def parse_slide(raw: dict[str, Any], index: int) -> SlideSummary:
    """Parse a single slide dict from the Slides API into a SlideSummary."""
    slide_id = raw.get("objectId", "")
    layout_ref = raw.get("slideProperties", {})
    layout_id = layout_ref.get("layoutObjectId")
    master_id = layout_ref.get("masterObjectId")
    notes_page = layout_ref.get("notesPage")

    elements = [_parse_element(e) for e in raw.get("pageElements", [])]
    notes_text = _parse_notes(notes_page)
    bg_color = _background_color(raw.get("pageProperties"))

    return SlideSummary(
        slide_id=slide_id,
        slide_index=index,
        layout_object_id=layout_id,
        master_object_id=master_id,
        notes_text=notes_text,
        elements=elements,
        background_color=bg_color,
    )


def parse_presentation(raw: dict[str, Any]) -> PresentationSummary:
    """Parse a full presentations.get() response into a PresentationSummary."""
    presentation_id = raw.get("presentationId", "")
    title = raw.get("title", "Untitled")
    locale = raw.get("locale")

    page_size = raw.get("pageSize", {})
    w = page_size.get("width", {})
    h = page_size.get("height", {})
    slide_width = w.get("magnitude")
    slide_height = h.get("magnitude")

    slides_raw = raw.get("slides", [])
    slides = [parse_slide(s, i) for i, s in enumerate(slides_raw)]

    masters_raw = raw.get("masters", [])
    masters = [
        {"master_id": m.get("objectId"), "name": m.get("masterProperties", {}).get("displayName")}
        for m in masters_raw
    ]

    layouts_raw = raw.get("layouts", [])
    layouts = [
        {
            "layout_id": l.get("objectId"),
            "name": l.get("layoutProperties", {}).get("displayName"),
            "predefined_layout": l.get("layoutProperties", {}).get("name"),
            "master_id": l.get("layoutProperties", {}).get("masterObjectId"),
        }
        for l in layouts_raw
    ]

    return PresentationSummary(
        presentation_id=presentation_id,
        title=title,
        locale=locale,
        slide_width_emu=slide_width,
        slide_height_emu=slide_height,
        slide_count=len(slides),
        slides=slides,
        masters=masters,
        layouts=layouts,
    )
