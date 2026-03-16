"""export command group — export presentations to different formats.

Commands
--------
slides-agent export pdf      Export the presentation as a PDF.
slides-agent export json     Export the raw presentation JSON from the API.
slides-agent export thumbnail  Not supported via CLI (use Google Slides directly).

Export formats
--------------
pdf         application/pdf
pptx        application/vnd.openxmlformats-officedocument.presentationml.presentation
txt         text/plain (slide text only)
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException, AgentError, ErrorCode
from slides_agent.core.output import emit

app = typer.Typer(
    name="export",
    help="Export presentations to PDF, PPTX, or raw JSON.",
    no_args_is_help=True,
)


@app.command("pdf")
def export_pdf(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    output_file: Annotated[Path, typer.Option("--output", "-o", help="Output file path (e.g. deck.pdf).")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON status output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Export a presentation as a PDF file.

    \b
    WHAT IT DOES
    Uses the Google Drive export API to download the presentation as a PDF.
    The PDF is written to --output. Status JSON is written to stdout.

    \b
    REQUIRED
    --presentation-id    The presentation to export.
    --output             Destination file path.

    \b
    FAILURE MODES
    - auth_error: Insufficient permissions to export.
    - io_error: Cannot write to the output path.

    \b
    EXAMPLES
    slides-agent export pdf -p abc123 --output ./deck.pdf
    slides-agent export pdf -p abc123 -o /tmp/export.pdf --pretty
    """
    if examples:
        print("slides-agent export pdf -p abc123 --output ./deck.pdf")
        print("slides-agent export pdf -p abc123 -o /tmp/export.pdf --pretty")
        raise typer.Exit()

    creds = auth_core.require_credentials()
    _, drive_client = build_clients(creds)

    try:
        content = drive_client.export_file(presentation_id, "application/pdf")
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    try:
        output_file.write_bytes(content)
    except OSError as exc:
        AgentError(
            error_code=ErrorCode.io_error,
            detail=f"Failed to write PDF: {exc}",
            field="output",
        ).emit(pretty=pretty)

    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "format": "pdf",
            "output_file": str(output_file.resolve()),
            "size_bytes": len(content),
            "warnings": [],
            "errors": [],
        },
        pretty=pretty,
    )


@app.command("pptx")
def export_pptx(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    output_file: Annotated[Path, typer.Option("--output", "-o", help="Output file path (e.g. deck.pptx).")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON status output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Export a presentation as a PowerPoint (.pptx) file.

    \b
    WHAT IT DOES
    Uses the Google Drive export API to download the presentation in
    PowerPoint format. The .pptx is written to --output.

    \b
    EXAMPLES
    slides-agent export pptx -p abc123 --output ./deck.pptx
    """
    if examples:
        print("slides-agent export pptx -p abc123 --output ./deck.pptx")
        raise typer.Exit()

    creds = auth_core.require_credentials()
    _, drive_client = build_clients(creds)

    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    try:
        content = drive_client.export_file(presentation_id, mime)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    try:
        output_file.write_bytes(content)
    except OSError as exc:
        AgentError(error_code=ErrorCode.io_error, detail=f"Failed to write file: {exc}").emit(pretty=pretty)

    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "format": "pptx",
            "output_file": str(output_file.resolve()),
            "size_bytes": len(content),
            "warnings": [],
            "errors": [],
        },
        pretty=pretty,
    )


@app.command("json")
def export_json(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    output_file: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path. If omitted, writes to stdout."),
    ] = None,
    raw: Annotated[bool, typer.Option("--raw", help="Export raw API response instead of parsed model.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Export the presentation as structured JSON.

    \b
    WHAT IT DOES
    Fetches the presentation and writes it as JSON. By default, the output
    uses the parsed PresentationSummary model format (same as `deck inspect`).
    Use --raw to get the unmodified Google Slides API response.

    \b
    OPTIONAL
    --output    Write to a file instead of stdout.
    --raw       Output the raw API JSON (useful for debugging).

    \b
    EXAMPLES
    slides-agent export json -p abc123 > deck.json
    slides-agent export json -p abc123 --output deck.json --pretty
    slides-agent export json -p abc123 --raw | jq '.slides[0].pageElements'
    """
    if examples:
        print("slides-agent export json -p abc123 > deck.json")
        print("slides-agent export json -p abc123 --output deck.json --pretty")
        print("slides-agent export json -p abc123 --raw | jq '.slides[0].pageElements'")
        raise typer.Exit()

    import json as json_lib

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        api_response = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    if raw:
        content = json_lib.dumps(api_response, indent=2 if pretty else None, default=str)
    else:
        from slides_agent.core.parser import parse_presentation
        presentation = parse_presentation(api_response)
        content = presentation.model_dump_json(indent=2 if pretty else None)

    if output_file:
        try:
            output_file.write_text(content)
        except OSError as exc:
            AgentError(error_code=ErrorCode.io_error, detail=f"Failed to write file: {exc}").emit(pretty=pretty)
        emit(
            {
                "ok": True,
                "presentation_id": presentation_id,
                "format": "json",
                "output_file": str(output_file.resolve()),
                "warnings": [],
                "errors": [],
            },
            pretty=pretty,
        )
    else:
        print(content)
