"""deck command group — presentation-level operations.

Commands
--------
slides-agent deck inspect      Return full structured JSON for a presentation.
slides-agent deck duplicate    Copy a presentation via the Drive API.

Deck inspect is the foundation for agent planning. Run it first to discover
slide IDs, element IDs, and layout names before issuing any mutations.

JSON output shape (deck inspect)
---------------------------------
{
  "ok": true,
  "presentation": {
    "presentation_id": "abc123",
    "title": "My Deck",
    "slide_count": 5,
    "slides": [
      {
        "slide_id": "g1a2b3",
        "slide_index": 0,
        "layout_name": "TITLE",
        "elements": [
          {
            "element_id": "p1",
            "element_type": "shape",
            "placeholder_type": "TITLE",
            "text": {"raw_text": "Hello World", "paragraphs": [...]},
            ...
          }
        ]
      }
    ],
    "masters": [...],
    "layouts": [...]
  },
  "warnings": [],
  "errors": []
}

How to find a presentation ID
------------------------------
The presentation ID is the long alphanumeric string in the Google Slides URL:
  https://docs.google.com/presentation/d/<PRESENTATION_ID>/edit
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException, ErrorCode, AgentError
from slides_agent.core.output import emit
from slides_agent.core.parser import parse_presentation
from slides_agent.schemas.deck import DeckDuplicateOutput, DeckInspectOutput

app = typer.Typer(
    name="deck",
    help="Presentation-level operations: inspect, duplicate.",
    no_args_is_help=True,
)

_EXAMPLES_INSPECT = """
# Inspect a presentation and pipe through jq to get slide IDs:
slides-agent deck inspect --presentation-id abc123 | jq '[.presentation.slides[].slide_id]'

# Inspect and save to a file:
slides-agent deck inspect --presentation-id abc123 > deck.json

# Pretty-print for human review:
slides-agent deck inspect --presentation-id abc123 --pretty
"""

_EXAMPLES_DUPLICATE = """
# Duplicate a presentation:
slides-agent deck duplicate --presentation-id abc123 --title "QBR v2"

# Duplicate with pretty output:
slides-agent deck duplicate --presentation-id abc123 --title "Copy of Deck" --pretty
"""


@app.command("inspect")
def inspect(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Google Slides presentation ID.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
    schema: Annotated[bool, typer.Option("--schema", help="Emit JSON schema for the output and exit.")] = False,
) -> None:
    """Return the full structure of a presentation as JSON.

    \b
    WHAT IT DOES
    Fetches the presentation from the Slides API and returns a rich JSON
    document describing every slide, element, text run, image, placeholder,
    bounding box, and speaker note. This output is the foundation for all
    agent planning — inspect before mutating.

    \b
    REQUIRED
    --presentation-id    The presentation ID from the URL.

    \b
    HOW TO FIND THE PRESENTATION ID
    Open the presentation in Google Slides. The ID is the segment between
    /d/ and /edit in the URL:
      https://docs.google.com/presentation/d/<ID>/edit

    \b
    OUTPUT FIELDS
    presentation_id     Stable ID — use in all subsequent commands.
    title               Current presentation title.
    slide_count         Total number of slides.
    slides[]            Ordered list of slide objects.
      slide_id          Stable slide reference for slide/notes commands.
      slide_index       0-based position.
      layout_name       Name of the applied layout.
      elements[]        All page elements on this slide.
        element_id      Stable reference for text/image commands.
        element_type    shape | image | table | chart | video | line | group.
        placeholder_type  TITLE | BODY | SUBTITLE | etc. (shapes only).
        text.raw_text   Plain concatenated text (shapes only).
        size / transform  Bounding box in EMUs.
    masters / layouts   Theme structure references.

    \b
    FAILURE MODES
    - auth_error: Run `slides-agent auth login` first.
    - not_found: The presentation ID does not exist or you lack access.
    """
    if examples:
        print(_EXAMPLES_INSPECT)
        raise typer.Exit()

    if schema:
        import json
        print(json.dumps(DeckInspectOutput.model_json_schema(), indent=2))
        raise typer.Exit()

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    presentation = parse_presentation(raw)
    output = DeckInspectOutput(presentation=presentation)
    emit(output, pretty=pretty)


@app.command("duplicate")
def duplicate(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Google Slides presentation ID to copy.")],
    title: Annotated[str, typer.Option("--title", "-t", help="Title for the new presentation.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
    schema: Annotated[bool, typer.Option("--schema", help="Emit JSON schema for the output and exit.")] = False,
) -> None:
    """Copy a presentation using the Drive API.

    \b
    WHAT IT DOES
    Creates an exact copy of the presentation in your Google Drive and
    returns the new presentation's ID and URL. The copy is independent —
    edits to the copy do not affect the original.

    \b
    REQUIRED
    --presentation-id    The source presentation to copy.
    --title              The name to give the new presentation.

    \b
    IDEMPOTENCY
    This command always creates a new copy. It does NOT check for existing
    copies with the same name. Run with care to avoid duplicate decks.

    \b
    FAILURE MODES
    - auth_error: Run `slides-agent auth login` first.
    - not_found: The source presentation does not exist.
    - api_error: Drive API failure.
    """
    if examples:
        print(_EXAMPLES_DUPLICATE)
        raise typer.Exit()

    if schema:
        import json
        print(json.dumps(DeckDuplicateOutput.model_json_schema(), indent=2))
        raise typer.Exit()

    creds = auth_core.require_credentials()
    _, drive_client = build_clients(creds)

    try:
        result = drive_client.copy_file(presentation_id, title)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    new_id = result.get("id", "")
    output = DeckDuplicateOutput(
        original_presentation_id=presentation_id,
        new_presentation_id=new_id,
        new_title=title,
        drive_url=f"https://docs.google.com/presentation/d/{new_id}/edit" if new_id else None,
    )
    emit(output, pretty=pretty)
