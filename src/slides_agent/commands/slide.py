"""slide command group — slide-level create/read/delete/duplicate/reorder.

Commands
--------
slides-agent slide list        List all slides with IDs and element counts.
slides-agent slide inspect     Full detail for a single slide.
slides-agent slide create      Add a new slide at a given position.
slides-agent slide delete      Remove a slide by ID.
slides-agent slide duplicate   Copy a slide within the same presentation.
slides-agent slide reorder     Move a slide to a new index.
slides-agent slide background  Change the background color of a slide.

All mutating commands support --dry-run.

How to find slide IDs
----------------------
Run `slides-agent deck inspect --presentation-id <id>` and extract the
`slide_id` fields from the `slides[]` array.

JSON output shape (slide list)
-------------------------------
{
  "ok": true,
  "presentation_id": "abc123",
  "slide_count": 3,
  "slides": [
    {"slide_id": "g1", "slide_index": 0, "layout_name": "TITLE", "elements": [...]}
  ],
  "warnings": [],
  "errors": []
}
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException
from slides_agent.core.output import emit, dry_run_envelope, success_envelope
from slides_agent.core.parser import parse_presentation, parse_slide
from slides_agent.schemas.slide import SlideListOutput, SlideMutationOutput, AppliedOperation

app = typer.Typer(
    name="slide",
    help="Slide-level operations: list, create, delete, duplicate, reorder.",
    no_args_is_help=True,
)


@app.command("list")
def list_slides(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
    schema: Annotated[bool, typer.Option("--schema", help="Emit JSON schema for the output and exit.")] = False,
) -> None:
    """List all slides with IDs, indices, layouts, and element counts.

    \b
    WHAT IT DOES
    Returns an ordered array of slide summaries. Use slide_id values from
    this output as targets for slide delete, duplicate, reorder, and notes
    commands. Element IDs in the `elements` array are used by text and image
    commands.

    \b
    REQUIRED
    --presentation-id    The presentation to inspect.

    \b
    OUTPUT FIELDS
    slide_id        Stable ID for this slide (use in mutation commands).
    slide_index     0-based position in the deck.
    layout_name     The predefined layout name (e.g. TITLE_AND_BODY).
    elements[]      Page elements; includes element_id, type, and text preview.

    \b
    EXAMPLES
    # Get just slide IDs as a JSON array:
    slides-agent slide list --presentation-id abc123 | jq '[.slides[].slide_id]'

    # Count slides:
    slides-agent slide list --presentation-id abc123 | jq '.slide_count'
    """
    if examples:
        print("slides-agent slide list --presentation-id abc123")
        print("slides-agent slide list --presentation-id abc123 | jq '[.slides[].slide_id]'")
        raise typer.Exit()

    if schema:
        import json
        print(json.dumps(SlideListOutput.model_json_schema(), indent=2))
        raise typer.Exit()

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    presentation = parse_presentation(raw)
    output = SlideListOutput(
        presentation_id=presentation_id,
        slide_count=presentation.slide_count,
        slides=presentation.slides,
    )
    emit(output, pretty=pretty)


@app.command("inspect")
def inspect_slide(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Return full detail for a single slide.

    \b
    WHAT IT DOES
    Returns all page elements, text content, notes, and bounding boxes for
    one slide. Use this for deep inspection before targeting specific elements.

    \b
    REQUIRED
    --presentation-id    The presentation containing the slide.
    --slide-id           The slide's object ID (from `slide list`).

    \b
    FAILURE MODES
    - not_found: The slide ID does not exist in this presentation.
    """
    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw_page = slides_client.get_page(presentation_id, slide_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    # Find the index from the full presentation
    try:
        raw_pres = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    index = next(
        (i for i, s in enumerate(raw_pres.get("slides", [])) if s.get("objectId") == slide_id),
        0,
    )
    slide = parse_slide(raw_page, index)
    emit({"ok": True, "presentation_id": presentation_id, "slide": slide.model_dump(), "warnings": [], "errors": []}, pretty=pretty)


@app.command("create")
def create_slide(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    insertion_index: Annotated[
        Optional[int],
        typer.Option("--insertion-index", "-i", help="0-based index. Appends at end if omitted."),
    ] = None,
    layout: Annotated[
        Optional[str],
        typer.Option(
            "--layout",
            help=(
                "Predefined layout type: BLANK, CAPTION_ONLY, TITLE, TITLE_AND_BODY, "
                "TITLE_AND_TWO_COLUMNS, TITLE_ONLY, ONE_COLUMN_TEXT, MAIN_POINT, "
                "BIG_NUMBER. Default: BLANK."
            ),
        ),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Validate and preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Add a new slide at a specified position.

    \b
    WHAT IT DOES
    Creates a new slide using a predefined layout. The response includes the
    new slide's object ID so subsequent commands can immediately target it.

    \b
    REQUIRED
    --presentation-id    The target presentation.

    \b
    OPTIONAL
    --insertion-index    0-based position (default: append at end).
    --layout             Layout preset name (default: BLANK).

    \b
    FAILURE MODES
    - auth_error: Run `slides-agent auth login` first.
    - not_found: Presentation does not exist.
    - validation_error: Unknown layout name.

    \b
    EXAMPLES
    slides-agent slide create --presentation-id abc123 --layout TITLE_AND_BODY
    slides-agent slide create --presentation-id abc123 --insertion-index 2 --layout BLANK
    slides-agent slide create --presentation-id abc123 --dry-run
    """
    if examples:
        print("slides-agent slide create --presentation-id abc123 --layout TITLE_AND_BODY")
        print("slides-agent slide create --presentation-id abc123 --insertion-index 2")
        print("slides-agent slide create --presentation-id abc123 --dry-run")
        raise typer.Exit()

    request: dict = {"createSlide": {}}
    if insertion_index is not None:
        request["createSlide"]["insertionIndex"] = insertion_index
    if layout:
        request["createSlide"]["slideLayoutReference"] = {"predefinedLayout": layout}

    if dry_run:
        emit(dry_run_envelope(presentation_id=presentation_id, would_apply=[request]), pretty=pretty)
        return

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        response = slides_client.batch_update(presentation_id, [request])
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    replies = response.get("replies", [{}])
    new_id = replies[0].get("createSlide", {}).get("objectId", "") if replies else ""

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[AppliedOperation(type="create_slide", slide_id=new_id, detail={"insertion_index": insertion_index, "layout": layout})],
    )
    emit(output, pretty=pretty)


@app.command("delete")
def delete_slide(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID to delete.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation prompt.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Delete a slide by its object ID. This is irreversible.

    \b
    WHAT IT DOES
    Permanently removes the slide from the presentation. All elements on the
    slide are also deleted. This operation CANNOT be undone via the CLI.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --slide-id           The slide's object ID (from `slide list`).

    \b
    SAFETY
    Use --dry-run to preview the API request without applying it.
    Use --force to skip the safety prompt in non-interactive mode.

    \b
    FAILURE MODES
    - not_found: The slide ID does not exist.
    - conflict: Presentation was modified concurrently.

    \b
    EXAMPLES
    slides-agent slide delete --presentation-id abc123 --slide-id g1a2b3 --dry-run
    slides-agent slide delete --presentation-id abc123 --slide-id g1a2b3 --force
    """
    if examples:
        print("slides-agent slide delete --presentation-id abc123 --slide-id g1a2b3 --dry-run")
        print("slides-agent slide delete --presentation-id abc123 --slide-id g1a2b3 --force")
        raise typer.Exit()

    request = {"deleteObject": {"objectId": slide_id}}

    if dry_run:
        emit(dry_run_envelope(presentation_id=presentation_id, would_apply=[request]), pretty=pretty)
        return

    if not force:
        confirm = typer.confirm(f"Delete slide {slide_id}? This cannot be undone.")
        if not confirm:
            emit({"ok": False, "error_code": "conflict", "detail": "Aborted by user."}, pretty=pretty)
            raise typer.Exit(1)

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        slides_client.batch_update(presentation_id, [request])
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[AppliedOperation(type="delete_slide", slide_id=slide_id)],
    )
    emit(output, pretty=pretty)


@app.command("duplicate")
def duplicate_slide(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID to copy.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Duplicate a slide within the same presentation.

    \b
    WHAT IT DOES
    Creates an exact copy of the specified slide immediately after it. The
    response includes the new slide's object ID.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --slide-id           The slide to duplicate.

    \b
    EXAMPLES
    slides-agent slide duplicate --presentation-id abc123 --slide-id g1a2b3
    slides-agent slide duplicate --presentation-id abc123 --slide-id g1a2b3 --dry-run
    """
    if examples:
        print("slides-agent slide duplicate --presentation-id abc123 --slide-id g1a2b3")
        print("slides-agent slide duplicate --presentation-id abc123 --slide-id g1a2b3 --dry-run")
        raise typer.Exit()

    request = {"duplicateObject": {"objectId": slide_id}}

    if dry_run:
        emit(dry_run_envelope(presentation_id=presentation_id, would_apply=[request]), pretty=pretty)
        return

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        response = slides_client.batch_update(presentation_id, [request])
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    replies = response.get("replies", [{}])
    new_id = replies[0].get("duplicateObject", {}).get("objectId", "") if replies else ""

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[AppliedOperation(type="duplicate_slide", slide_id=new_id, detail={"source_slide_id": slide_id})],
    )
    emit(output, pretty=pretty)


@app.command("reorder")
def reorder_slide(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID to move.")],
    insertion_index: Annotated[int, typer.Option("--insertion-index", "-i", help="Target 0-based index.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Move a slide to a new position in the deck.

    \b
    WHAT IT DOES
    Reorders the specified slide to the given 0-based insertion index. All
    other slides shift to accommodate the new position.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --slide-id           The slide to move.
    --insertion-index    The new 0-based position for the slide.

    \b
    EXAMPLES
    slides-agent slide reorder --presentation-id abc123 --slide-id g1a2b3 --insertion-index 0
    slides-agent slide reorder --presentation-id abc123 --slide-id g1a2b3 --insertion-index 3 --dry-run
    """
    if examples:
        print("slides-agent slide reorder --presentation-id abc123 --slide-id g1a2b3 --insertion-index 0")
        raise typer.Exit()

    request = {
        "updateSlidesPosition": {
            "slideObjectIds": [slide_id],
            "insertionIndex": insertion_index,
        }
    }

    if dry_run:
        emit(dry_run_envelope(presentation_id=presentation_id, would_apply=[request]), pretty=pretty)
        return

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        slides_client.batch_update(presentation_id, [request])
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[
            AppliedOperation(type="reorder_slide", slide_id=slide_id, detail={"insertion_index": insertion_index})
        ],
    )
    emit(output, pretty=pretty)


@app.command("background")
def set_background(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    color: Annotated[str, typer.Option("--color", "-c", help="Hex color e.g. '#1A73E8' or '1A73E8'.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Change the background color of a slide.

    \b
    WHAT IT DOES
    Updates the slide background to a solid color specified as a hex string.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --slide-id           The slide to update.
    --color              Hex color string, with or without leading '#'.

    \b
    EXAMPLES
    slides-agent slide background --presentation-id abc123 --slide-id g1 --color '#1A73E8'
    slides-agent slide background --presentation-id abc123 --slide-id g1 --color 'FFFFFF'
    """
    hex_color = color.lstrip("#")
    if len(hex_color) != 6:
        from slides_agent.core.errors import AgentError, ErrorCode
        AgentError(
            error_code=ErrorCode.validation_error,
            detail=f"Invalid hex color: {color!r}. Expected 6-character hex e.g. '#1A73E8'.",
            field="color",
        ).emit(pretty=pretty)

    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    request = {
        "updatePageProperties": {
            "objectId": slide_id,
            "pageProperties": {
                "pageBackgroundFill": {
                    "solidFill": {
                        "color": {"rgbColor": {"red": r, "green": g, "blue": b}}
                    }
                }
            },
            "fields": "pageBackgroundFill.solidFill.color",
        }
    }

    if dry_run:
        emit(dry_run_envelope(presentation_id=presentation_id, would_apply=[request]), pretty=pretty)
        return

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        slides_client.batch_update(presentation_id, [request])
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[
            AppliedOperation(type="change_background", slide_id=slide_id, detail={"color": f"#{hex_color.upper()}"})
        ],
    )
    emit(output, pretty=pretty)
