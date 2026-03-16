"""text command group — read and mutate text on slides.

Commands
--------
slides-agent text replace    Replace all occurrences of a string across the deck.
slides-agent text set        Set the full text of a specific element.
slides-agent text append     Append text to an element.
slides-agent text clear      Remove all text from an element.
slides-agent text get        Return the text content of an element.

All mutating commands support --dry-run.

How to target elements
-----------------------
Run `slides-agent element list --presentation-id <id> --slide-id <sid>`
to discover element IDs. Text shapes will have element_type == "shape" and
text.raw_text will contain their current content.

Encoding note
--------------
All text values are UTF-8 strings. Newlines within text should be
encoded as \\n in shell arguments: --text $'Line 1\\nLine 2'.
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException
from slides_agent.core.output import emit, dry_run_envelope
from slides_agent.schemas.slide import AppliedOperation, SlideMutationOutput

app = typer.Typer(
    name="text",
    help="Read and mutate text on slides.",
    no_args_is_help=True,
)


@app.command("replace")
def replace_text(
    presentation_id: Annotated[Optional[str], typer.Option("--presentation-id", "-p", help="Presentation ID.")] = None,
    find: Annotated[Optional[str], typer.Option("--find", "-f", help="Text to find (exact match).")] = None,
    replace: Annotated[Optional[str], typer.Option("--replace", "-r", help="Replacement text.")] = None,
    match_case: Annotated[bool, typer.Option("--match-case/--no-match-case", help="Case-sensitive matching.")] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Replace all occurrences of a string across the entire presentation.

    \b
    WHAT IT DOES
    Uses the Slides API `replaceAllText` request to find and replace text
    across every slide, notes page, and element in the presentation. This is
    the recommended way to fill template placeholders.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --find               The string to search for.
    --replace            The replacement string.

    \b
    OPTIONAL
    --match-case / --no-match-case    Case sensitivity (default: case-sensitive).

    \b
    TEMPLATE WORKFLOW
    Use placeholder tokens like {{customer}}, {{date}}, {{version}} in your
    template slide text, then call this command to fill them:
      slides-agent text replace --presentation-id abc123 --find '{{customer}}' --replace 'Acme Corp'
      slides-agent text replace --presentation-id abc123 --find '{{date}}' --replace '2025-01-01'

    \b
    FAILURE MODES
    - not_found: Presentation does not exist.
    - api_error: Slides API rejection (e.g., text exceeds limits).

    \b
    EXAMPLES
    slides-agent text replace -p abc123 --find '{{name}}' --replace 'Acme'
    slides-agent text replace -p abc123 --find 'DRAFT' --replace 'FINAL' --no-match-case
    slides-agent text replace -p abc123 --find '{{placeholder}}' --replace 'Value' --dry-run
    """
    if examples:
        print("slides-agent text replace -p abc123 --find '{{name}}' --replace 'Acme'")
        print("slides-agent text replace -p abc123 --find 'DRAFT' --replace 'FINAL' --no-match-case")
        print("slides-agent text replace -p abc123 --find '{{placeholder}}' --replace 'Value' --dry-run")
        raise typer.Exit()

    if not presentation_id or find is None or replace is None:
        raise typer.BadParameter("--presentation-id, --find, and --replace are required.")

    request = {
        "replaceAllText": {
            "containsText": {"text": find, "matchCase": match_case},
            "replaceText": replace,
        }
    }

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
    occurrences = replies[0].get("replaceAllText", {}).get("occurrencesChanged", 0) if replies else 0

    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "applied_operations": [{"type": "replace_text", "find": find, "replace": replace, "occurrences_changed": occurrences}],
            "warnings": [] if occurrences > 0 else [f"No occurrences of {find!r} found."],
            "errors": [],
        },
        pretty=pretty,
    )


@app.command("set")
def set_text(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    element_id: Annotated[str, typer.Option("--element-id", "-e", help="Shape element object ID.")],
    text: Annotated[str, typer.Option("--text", "-t", help="New text content. Use \\n for newlines.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Replace all text in a specific element with new text.

    \b
    WHAT IT DOES
    Clears all existing text in the element and inserts the new text.
    Styling from the element's default placeholder style is preserved.
    Complex inline formatting from the original is lost — use `patch apply`
    for style-preserving edits.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --slide-id           The slide containing the element.
    --element-id         The shape element whose text will be replaced.
    --text               The new text content.

    \b
    HOW TO FIND ELEMENT IDs
    Run `slides-agent element list --presentation-id <id> --slide-id <sid>`.
    Look for elements with element_type == "shape". The placeholder_type field
    (e.g. TITLE, BODY) helps identify the right element.

    \b
    FAILURE MODES
    - not_found: Element does not exist on the slide.
    - invalid_reference: Element is not a text-bearing shape.
    - validation_error: Text length exceeds API limits.

    \b
    EXAMPLES
    slides-agent text set -p abc123 -s g1 -e title_1 --text "New Title"
    slides-agent text set -p abc123 -s g1 -e body_1 --text $'Line 1\\nLine 2'
    slides-agent text set -p abc123 -s g1 -e title_1 --text "Draft" --dry-run
    """
    if examples:
        print("slides-agent text set -p abc123 -s g1 -e title_1 --text 'New Title'")
        print("slides-agent text set -p abc123 -s g1 -e body_1 --text $'Line 1\\nLine 2'")
        print("slides-agent text set -p abc123 -s g1 -e title_1 --text 'Draft' --dry-run")
        raise typer.Exit()

    requests = [
        {"deleteText": {"objectId": element_id, "textRange": {"type": "ALL"}}},
        {"insertText": {"objectId": element_id, "insertionIndex": 0, "text": text}},
    ]

    if dry_run:
        emit(dry_run_envelope(presentation_id=presentation_id, would_apply=requests), pretty=pretty)
        return

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        slides_client.batch_update(presentation_id, requests)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[
            AppliedOperation(type="update_text", slide_id=slide_id, element_id=element_id, detail={"text_length": len(text)})
        ],
    )
    emit(output, pretty=pretty)


@app.command("append")
def append_text(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    element_id: Annotated[str, typer.Option("--element-id", "-e", help="Shape element object ID.")],
    text: Annotated[str, typer.Option("--text", "-t", help="Text to append.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Append text to the end of an element's current content.

    \b
    WHAT IT DOES
    Inserts text at the end of the element's existing text body. Does not
    clear existing content.

    \b
    REQUIRED
    --presentation-id / --slide-id / --element-id / --text

    \b
    EXAMPLES
    slides-agent text append -p abc123 -s g1 -e body_1 --text '\\nNew bullet point'
    """
    request = {"insertText": {"objectId": element_id, "text": text}}

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
            AppliedOperation(type="append_text", slide_id=slide_id, element_id=element_id)
        ],
    )
    emit(output, pretty=pretty)


@app.command("clear")
def clear_text(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    element_id: Annotated[str, typer.Option("--element-id", "-e", help="Shape element object ID.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Remove all text from a specific element.

    \b
    WHAT IT DOES
    Deletes all text content from the specified shape element. The element
    remains on the slide but is empty.

    \b
    REQUIRED
    --presentation-id / --slide-id / --element-id

    \b
    EXAMPLES
    slides-agent text clear -p abc123 -s g1 -e title_1
    slides-agent text clear -p abc123 -s g1 -e body_1 --dry-run
    """
    request = {"deleteText": {"objectId": element_id, "textRange": {"type": "ALL"}}}

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
        applied_operations=[AppliedOperation(type="clear_text", slide_id=slide_id, element_id=element_id)],
    )
    emit(output, pretty=pretty)


@app.command("get")
def get_text(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    element_id: Annotated[str, typer.Option("--element-id", "-e", help="Shape element object ID.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Return the text content of a specific element.

    \b
    WHAT IT DOES
    Returns the raw_text and structured paragraph/run data for a shape element.

    \b
    EXAMPLES
    slides-agent text get -p abc123 -s g1 -e title_1
    slides-agent text get -p abc123 -s g1 -e body_1 | jq '.text.raw_text'
    """
    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    from slides_agent.core.parser import parse_presentation
    from slides_agent.core.errors import AgentError, ErrorCode

    presentation = parse_presentation(raw)
    slide = next((s for s in presentation.slides if s.slide_id == slide_id), None)
    if not slide:
        AgentError(error_code=ErrorCode.not_found, detail=f"Slide '{slide_id}' not found.").emit(pretty=pretty)

    element = next((e for e in slide.elements if e.element_id == element_id), None)  # type: ignore[union-attr]
    if not element:
        AgentError(error_code=ErrorCode.not_found, detail=f"Element '{element_id}' not found.").emit(pretty=pretty)

    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "element_id": element_id,
            "text": element.text.model_dump() if element.text else None,  # type: ignore[union-attr]
            "warnings": [],
            "errors": [],
        },
        pretty=pretty,
    )
