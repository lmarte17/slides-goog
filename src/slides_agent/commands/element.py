"""element command group — inspect and list page elements.

Commands
--------
slides-agent element list      List all elements on a slide.
slides-agent element inspect   Full detail for one element.

Element IDs from these commands are used as targets for text, image,
and style mutation commands.

Element types
-------------
shape     Text boxes, placeholders, shapes with text.
image     Bitmap images.
table     Data tables.
chart     Embedded Sheets charts.
video     Embedded videos.
line      Lines and connectors.
group     Grouped elements.
other     Anything not listed above.
"""

from __future__ import annotations

from typing import Annotated

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException, AgentError, ErrorCode
from slides_agent.core.output import emit
from slides_agent.core.parser import parse_presentation

app = typer.Typer(
    name="element",
    help="Inspect and list page elements on slides.",
    no_args_is_help=True,
)


@app.command("list")
def list_elements(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    element_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by element type: shape, image, table, chart, etc.")
    ] = None,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """List all elements on a slide with IDs, types, and text previews.

    \b
    WHAT IT DOES
    Returns every page element on the specified slide. Use the element_id
    values to target specific elements in text, image, and style commands.

    \b
    REQUIRED
    --presentation-id    The presentation containing the slide.
    --slide-id           The slide to inspect.

    \b
    OPTIONAL
    --type               Filter to only return elements of a specific type.

    \b
    OUTPUT FIELDS
    element_id        Stable ID for mutation commands.
    element_type      shape | image | table | chart | video | line | group.
    placeholder_type  TITLE | BODY | SUBTITLE | etc. (shapes with placeholders).
    text.raw_text     Plain text content (shapes only).
    size              Width and height in EMUs.
    transform         Position and scale transform in EMUs.

    \b
    EXAMPLES
    # List all elements:
    slides-agent element list --presentation-id abc123 --slide-id g1

    # List only images:
    slides-agent element list --presentation-id abc123 --slide-id g1 --type image

    # Get element IDs for text operations:
    slides-agent element list --presentation-id abc123 --slide-id g1 | jq '[.elements[].element_id]'
    """
    if examples:
        print("slides-agent element list --presentation-id abc123 --slide-id g1")
        print("slides-agent element list --presentation-id abc123 --slide-id g1 --type image")
        raise typer.Exit()

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    presentation = parse_presentation(raw)
    slide = next((s for s in presentation.slides if s.slide_id == slide_id), None)
    if slide is None:
        AgentError(
            error_code=ErrorCode.not_found,
            detail=f"Slide '{slide_id}' not found in presentation '{presentation_id}'.",
            hint="Run `slides-agent slide list` to get valid slide IDs.",
        ).emit(pretty=pretty)

    elements = slide.elements  # type: ignore[union-attr]
    if element_type:
        elements = [e for e in elements if e.element_type == element_type]

    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "element_count": len(elements),
            "elements": [e.model_dump() for e in elements],
            "warnings": [],
            "errors": [],
        },
        pretty=pretty,
    )


@app.command("inspect")
def inspect_element(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    element_id: Annotated[str, typer.Option("--element-id", "-e", help="Element object ID.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Return full detail for a single page element.

    \b
    WHAT IT DOES
    Returns the complete metadata for one element: type, placeholder type,
    full text with paragraph and run structure, image URLs, bounding box,
    and transform. Use this for precise targeting before mutations.

    \b
    REQUIRED
    --presentation-id    The presentation.
    --slide-id           The slide containing the element.
    --element-id         The element's object ID (from `element list`).

    \b
    FAILURE MODES
    - not_found: Either the slide or element ID does not exist.

    \b
    EXAMPLES
    slides-agent element inspect --presentation-id abc123 --slide-id g1 --element-id p2
    """
    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    presentation = parse_presentation(raw)
    slide = next((s for s in presentation.slides if s.slide_id == slide_id), None)
    if slide is None:
        AgentError(
            error_code=ErrorCode.not_found,
            detail=f"Slide '{slide_id}' not found.",
        ).emit(pretty=pretty)

    element = next((e for e in slide.elements if e.element_id == element_id), None)  # type: ignore[union-attr]
    if element is None:
        AgentError(
            error_code=ErrorCode.not_found,
            detail=f"Element '{element_id}' not found on slide '{slide_id}'.",
            hint="Run `slides-agent element list` to get valid element IDs.",
        ).emit(pretty=pretty)

    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "element": element.model_dump(),  # type: ignore[union-attr]
            "warnings": [],
            "errors": [],
        },
        pretty=pretty,
    )
