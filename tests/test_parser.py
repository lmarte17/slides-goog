"""Tests for the Google API response parser."""

from __future__ import annotations

import pytest

from slides_agent.core.parser import parse_presentation, parse_slide
from tests.conftest import SAMPLE_PRESENTATION, SAMPLE_SLIDE


def test_parse_presentation_basic():
    result = parse_presentation(SAMPLE_PRESENTATION)
    assert result.presentation_id == "test_presentation_id"
    assert result.title == "Test Presentation"
    assert result.slide_count == 2
    assert result.locale == "en"
    assert result.slide_width_emu == 9144000
    assert result.slide_height_emu == 5143500


def test_parse_presentation_slides():
    result = parse_presentation(SAMPLE_PRESENTATION)
    assert len(result.slides) == 2
    slide = result.slides[0]
    assert slide.slide_id == "slide_1"
    assert slide.slide_index == 0
    assert slide.layout_object_id == "layout_title"
    assert slide.master_object_id == "master_1"


def test_parse_presentation_elements():
    result = parse_presentation(SAMPLE_PRESENTATION)
    slide = result.slides[0]
    assert len(slide.elements) == 2

    title_el = slide.elements[0]
    assert title_el.element_id == "title_element_1"
    assert title_el.element_type == "shape"
    assert title_el.placeholder_type == "TITLE"
    assert title_el.text is not None
    assert title_el.text.raw_text == "Hello World"


def test_parse_presentation_image_element():
    result = parse_presentation(SAMPLE_PRESENTATION)
    slide = result.slides[0]
    image_el = slide.elements[1]
    assert image_el.element_id == "image_element_1"
    assert image_el.element_type == "image"
    assert image_el.image is not None
    assert image_el.image.content_url == "https://example.com/image.png"


def test_parse_presentation_notes():
    result = parse_presentation(SAMPLE_PRESENTATION)
    slide = result.slides[0]
    assert slide.notes_text == "Talk track here."


def test_parse_presentation_background():
    result = parse_presentation(SAMPLE_PRESENTATION)
    slide = result.slides[0]
    assert slide.background_color == "#FFFFFF"


def test_parse_presentation_masters():
    result = parse_presentation(SAMPLE_PRESENTATION)
    assert len(result.masters) == 1
    assert result.masters[0]["master_id"] == "master_1"


def test_parse_presentation_layouts():
    result = parse_presentation(SAMPLE_PRESENTATION)
    assert len(result.layouts) == 1
    assert result.layouts[0]["layout_id"] == "layout_title"
    assert result.layouts[0]["predefined_layout"] == "TITLE"


def test_parse_slide_index():
    slide = parse_slide(SAMPLE_SLIDE, 3)
    assert slide.slide_index == 3


def test_parse_slide_empty_elements():
    raw = {
        "objectId": "empty_slide",
        "pageElements": [],
        "slideProperties": {},
    }
    slide = parse_slide(raw, 0)
    assert slide.slide_id == "empty_slide"
    assert slide.elements == []
    assert slide.notes_text is None


def test_parse_token_element():
    """Test that a slide with {{token}} in text is parsed correctly."""
    result = parse_presentation(SAMPLE_PRESENTATION)
    slide = result.slides[1]
    assert len(slide.elements) == 1
    el = slide.elements[0]
    assert "{{customer}}" in el.text.raw_text
