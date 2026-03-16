"""notes command group — speaker notes operations.

Commands
--------
slides-agent notes get      Return the speaker notes for a slide.
slides-agent notes set      Replace speaker notes for a slide.
slides-agent notes clear    Remove speaker notes from a slide.

Speaker notes are stored on each slide's notes page, in the BODY
placeholder of that page. The Slides API does not expose a dedicated
notes endpoint — notes are modified by targeting the notes page element.

How to find the notes element ID
---------------------------------
Run `slides-agent deck inspect --presentation-id <id>` and look at the
`notes_text` field on each slide. The notes element ID is embedded in the
notes page, but this CLI handles the lookup automatically.
"""

from __future__ import annotations

from typing import Annotated

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException, AgentError, ErrorCode
from slides_agent.core.output import emit, dry_run_envelope
from slides_agent.core.parser import parse_presentation
from slides_agent.schemas.slide import AppliedOperation, SlideMutationOutput

app = typer.Typer(
    name="notes",
    help="Speaker notes operations: get, set, clear.",
    no_args_is_help=True,
)


def _find_notes_element_id(raw_presentation: dict, slide_id: str) -> str | None:
    """Return the object ID of the BODY element on a slide's notes page."""
    for slide in raw_presentation.get("slides", []):
        if slide.get("objectId") != slide_id:
            continue
        notes_page = slide.get("slideProperties", {}).get("notesPage", {})
        for element in notes_page.get("pageElements", []):
            shape = element.get("shape", {})
            if shape.get("placeholder", {}).get("type") == "BODY":
                return element.get("objectId")
    return None


@app.command("get")
def get_notes(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Return the speaker notes for a slide.

    \b
    WHAT IT DOES
    Fetches the presentation and extracts the plain-text speaker notes from
    the specified slide's notes page.

    \b
    REQUIRED
    --presentation-id    The presentation.
    --slide-id           The slide to read notes from.

    \b
    OUTPUT FIELDS
    notes_text    Plain text of the speaker notes, or null if empty.

    \b
    EXAMPLES
    slides-agent notes get -p abc123 -s g1
    slides-agent notes get -p abc123 -s g1 | jq -r '.notes_text'
    """
    if examples:
        print("slides-agent notes get -p abc123 -s g1")
        print("slides-agent notes get -p abc123 -s g1 | jq -r '.notes_text'")
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
        ).emit(pretty=pretty)

    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "notes_text": slide.notes_text,  # type: ignore[union-attr]
            "warnings": [],
            "errors": [],
        },
        pretty=pretty,
    )


@app.command("set")
def set_notes(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    text: Annotated[str, typer.Option("--text", "-t", help="Speaker notes text. Use \\n for newlines.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Replace speaker notes for a slide.

    \b
    WHAT IT DOES
    Clears existing notes and sets new speaker notes text for the specified
    slide. The BODY placeholder on the slide's notes page is targeted.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --slide-id           The slide to update.
    --text               The new speaker notes content.

    \b
    FAILURE MODES
    - not_found: Slide does not have a notes body placeholder.
    - api_error: Slides API rejection.

    \b
    EXAMPLES
    slides-agent notes set -p abc123 -s g1 --text 'Talk track: introduce the team.'
    slides-agent notes set -p abc123 -s g1 --text $'Point 1\\nPoint 2' --dry-run
    slides-agent notes set -p abc123 -s g1 --text 'Notes' --dry-run
    """
    if examples:
        print("slides-agent notes set -p abc123 -s g1 --text 'Talk track...'")
        print("slides-agent notes set -p abc123 -s g1 --text $'Point 1\\nPoint 2' --dry-run")
        raise typer.Exit()

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    notes_element_id = _find_notes_element_id(raw, slide_id)
    if notes_element_id is None:
        AgentError(
            error_code=ErrorCode.not_found,
            detail=f"No notes body placeholder found on slide '{slide_id}'.",
            hint="Some layouts may not include a notes body placeholder.",
        ).emit(pretty=pretty)

    requests = [
        {"deleteText": {"objectId": notes_element_id, "textRange": {"type": "ALL"}}},
        {"insertText": {"objectId": notes_element_id, "insertionIndex": 0, "text": text}},
    ]

    if dry_run:
        emit(
            dry_run_envelope(
                presentation_id=presentation_id,
                would_apply=requests,
                warnings=[f"Notes element ID: {notes_element_id}"],
            ),
            pretty=pretty,
        )
        return

    try:
        slides_client.batch_update(presentation_id, requests)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[
            AppliedOperation(
                type="set_notes",
                slide_id=slide_id,
                element_id=notes_element_id,
                detail={"text_length": len(text)},
            )
        ],
    )
    emit(output, pretty=pretty)


@app.command("clear")
def clear_notes(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Remove all speaker notes from a slide.

    \b
    EXAMPLES
    slides-agent notes clear -p abc123 -s g1
    slides-agent notes clear -p abc123 -s g1 --dry-run
    """
    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    notes_element_id = _find_notes_element_id(raw, slide_id)
    if notes_element_id is None:
        AgentError(
            error_code=ErrorCode.not_found,
            detail=f"No notes body placeholder found on slide '{slide_id}'.",
        ).emit(pretty=pretty)

    request = {"deleteText": {"objectId": notes_element_id, "textRange": {"type": "ALL"}}}

    if dry_run:
        emit(dry_run_envelope(presentation_id=presentation_id, would_apply=[request]), pretty=pretty)
        return

    try:
        slides_client.batch_update(presentation_id, [request])
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[AppliedOperation(type="clear_notes", slide_id=slide_id, element_id=notes_element_id)],
    )
    emit(output, pretty=pretty)
