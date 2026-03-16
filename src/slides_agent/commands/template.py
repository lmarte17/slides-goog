"""template command group — create and fill presentation templates.

Commands
--------
slides-agent template create    Duplicate a template presentation and optionally fill it.
slides-agent template inspect   List all placeholder tokens found in a presentation.
slides-agent template fill      Fill placeholder tokens from a JSON values file.

Template tokens
----------------
Use double-brace syntax in your slide text: {{variable_name}}
Examples: {{customer}}, {{date}}, {{version}}, {{revenue}}

Fill values format (JSON)
--------------------------
{
  "customer": "Acme Corp",
  "date": "2025-01-15",
  "revenue": "$4.2M",
  "version": "v3"
}

Workflow
--------
1. Build a template presentation with {{token}} placeholders.
2. Run `template inspect` to verify all tokens.
3. Prepare a JSON values file.
4. Run `template fill` to replace all tokens.

Or in one step:
  slides-agent template create --template-id <id> --title "New Deck" --values-file ./values.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Optional

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException, AgentError, ErrorCode
from slides_agent.core.output import emit, dry_run_envelope
from slides_agent.core.parser import parse_presentation

app = typer.Typer(
    name="template",
    help="Create presentations from templates and fill placeholder tokens.",
    no_args_is_help=True,
)

_TOKEN_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


def _find_tokens(raw: dict) -> dict[str, list[str]]:
    """Return a dict mapping token name -> list of slide IDs containing the token."""
    token_slides: dict[str, list[str]] = {}

    for slide in raw.get("slides", []):
        slide_id = slide.get("objectId", "")
        for element in slide.get("pageElements", []):
            shape = element.get("shape", {})
            text_content = shape.get("text", {})
            for text_element in text_content.get("textElements", []):
                run = text_element.get("textRun", {})
                content = run.get("content", "")
                for match in _TOKEN_PATTERN.finditer(content):
                    token = match.group(1).strip()
                    if token not in token_slides:
                        token_slides[token] = []
                    if slide_id not in token_slides[token]:
                        token_slides[token].append(slide_id)

    return token_slides


@app.command("create")
def create_from_template(
    template_id: Annotated[str, typer.Option("--template-id", help="Source template presentation ID.")],
    title: Annotated[str, typer.Option("--title", "-t", help="Title for the new presentation.")],
    values_file: Annotated[
        Optional[Path],
        typer.Option("--values-file", "-v", help="JSON file with token replacement values."),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without creating.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Create a new presentation from a template and optionally fill tokens.

    \b
    WHAT IT DOES
    1. Duplicates the template presentation via the Drive API.
    2. If --values-file is provided, replaces all {{token}} placeholders
       with the corresponding values from the JSON file.

    \b
    REQUIRED
    --template-id    The source presentation to duplicate.
    --title          Name for the new presentation.

    \b
    OPTIONAL
    --values-file    JSON file mapping token names to replacement strings.

    \b
    EXAMPLES
    slides-agent template create --template-id abc123 --title "Acme QBR Q1"
    slides-agent template create --template-id abc123 --title "Acme QBR" --values-file ./acme.json
    slides-agent template create --template-id abc123 --title "Test Copy" --dry-run
    """
    if examples:
        print("slides-agent template create --template-id abc123 --title 'Acme QBR Q1'")
        print("slides-agent template create --template-id abc123 --title 'Acme QBR' --values-file ./acme.json")
        print("slides-agent template create --template-id abc123 --title 'Test Copy' --dry-run")
        raise typer.Exit()

    values: dict[str, str] = {}
    if values_file:
        if not values_file.exists():
            AgentError(
                error_code=ErrorCode.io_error,
                detail=f"Values file not found: {values_file}",
            ).emit(pretty=pretty)
        try:
            values = json.loads(values_file.read_text())
        except Exception as exc:
            AgentError(
                error_code=ErrorCode.validation_error,
                detail=f"Invalid JSON in values file: {exc}",
                field="values_file",
            ).emit(pretty=pretty)

    if dry_run:
        replace_requests = [
            {"replaceAllText": {"containsText": {"text": f"{{{{{k}}}}}", "matchCase": True}, "replaceText": v}}
            for k, v in values.items()
        ]
        emit(
            dry_run_envelope(
                presentation_id=f"<copy of {template_id}>",
                would_apply=[{"copyPresentation": {"title": title}}, *replace_requests],
                warnings=[f"Would copy template {template_id!r} and apply {len(values)} replacements."],
            ),
            pretty=pretty,
        )
        return

    creds = auth_core.require_credentials()
    slides_client, drive_client = build_clients(creds)

    try:
        copy_result = drive_client.copy_file(template_id, title)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    new_id = copy_result.get("id", "")
    applied_replacements = []

    if values:
        replace_requests = [
            {"replaceAllText": {"containsText": {"text": f"{{{{{k}}}}}", "matchCase": True}, "replaceText": v}}
            for k, v in values.items()
        ]
        try:
            response = slides_client.batch_update(new_id, replace_requests)
        except AgentException as exc:
            exc.error.emit(pretty=pretty)

        for i, (k, v) in enumerate(values.items()):
            replies = response.get("replies", [])
            occurrences = replies[i].get("replaceAllText", {}).get("occurrencesChanged", 0) if i < len(replies) else 0
            applied_replacements.append({"token": k, "value": v, "occurrences_changed": occurrences})

    emit(
        {
            "ok": True,
            "template_id": template_id,
            "new_presentation_id": new_id,
            "new_title": title,
            "drive_url": f"https://docs.google.com/presentation/d/{new_id}/edit",
            "applied_replacements": applied_replacements,
            "warnings": [],
            "errors": [],
        },
        pretty=pretty,
    )


@app.command("inspect")
def inspect_template(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """List all {{token}} placeholders found in a presentation.

    \b
    WHAT IT DOES
    Scans all text content across all slides and returns a list of unique
    {{token}} placeholders, along with which slides contain them.

    \b
    OUTPUT FIELDS
    tokens    Dict mapping token name to list of slide IDs containing it.
    unfilled  List of token names — all of them, since none are filled yet.

    \b
    EXAMPLES
    slides-agent template inspect --presentation-id abc123
    slides-agent template inspect --presentation-id abc123 | jq '[.tokens | keys]'
    slides-agent template inspect --presentation-id abc123 --pretty
    """
    if examples:
        print("slides-agent template inspect --presentation-id abc123")
        print("slides-agent template inspect --presentation-id abc123 | jq '[.tokens | keys]'")
        raise typer.Exit()

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    tokens = _find_tokens(raw)
    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "token_count": len(tokens),
            "tokens": tokens,
            "unfilled": sorted(tokens.keys()),
            "warnings": [] if tokens else ["No {{token}} placeholders found in this presentation."],
            "errors": [],
        },
        pretty=pretty,
    )


@app.command("fill")
def fill_template(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    values_file: Annotated[Path, typer.Option("--values-file", "-v", help="JSON file with token values.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Fill {{token}} placeholders in an existing presentation from a JSON values file.

    \b
    WHAT IT DOES
    Reads the JSON values file and replaces each {{token}} found in the
    presentation with the corresponding value. Tokens not present in the
    values file are left unchanged and reported as warnings.

    \b
    REQUIRED
    --presentation-id    The presentation to fill.
    --values-file        JSON file: {"token_name": "replacement_value", ...}

    \b
    FAILURE MODES
    - io_error: Values file not found or unreadable.
    - validation_error: Values file is not valid JSON.

    \b
    EXAMPLES
    slides-agent template fill -p abc123 --values-file ./values.json
    slides-agent template fill -p abc123 --values-file ./values.json --dry-run
    slides-agent template fill -p abc123 --values-file ./values.json --pretty
    """
    if examples:
        print("slides-agent template fill -p abc123 --values-file ./values.json")
        print("slides-agent template fill -p abc123 --values-file ./values.json --dry-run")
        raise typer.Exit()

    if not values_file.exists():
        AgentError(error_code=ErrorCode.io_error, detail=f"Values file not found: {values_file}").emit(pretty=pretty)

    try:
        values: dict[str, str] = json.loads(values_file.read_text())
    except Exception as exc:
        AgentError(error_code=ErrorCode.validation_error, detail=f"Invalid JSON: {exc}").emit(pretty=pretty)

    requests = [
        {"replaceAllText": {"containsText": {"text": f"{{{{{k}}}}}", "matchCase": True}, "replaceText": str(v)}}
        for k, v in values.items()
    ]

    if dry_run:
        emit(dry_run_envelope(presentation_id=presentation_id, would_apply=requests), pretty=pretty)
        return

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    unfilled_tokens = _find_tokens(raw)
    unfilled_warnings = [
        f"Token '{{{{{t}}}}}' not in values file — left unchanged."
        for t in unfilled_tokens
        if t not in values
    ]

    try:
        response = slides_client.batch_update(presentation_id, requests)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    applied = []
    for i, (k, v) in enumerate(values.items()):
        replies = response.get("replies", [])
        occurrences = replies[i].get("replaceAllText", {}).get("occurrencesChanged", 0) if i < len(replies) else 0
        applied.append({"token": k, "value": v, "occurrences_changed": occurrences})

    emit(
        {
            "ok": True,
            "presentation_id": presentation_id,
            "applied_replacements": applied,
            "warnings": unfilled_warnings,
            "errors": [],
        },
        pretty=pretty,
    )
