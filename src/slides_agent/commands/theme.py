"""theme command group — apply style presets deck-wide.

Commands
--------
slides-agent theme apply         Apply a theme spec file to all slides.
slides-agent theme list-presets  List built-in theme presets.

Theme spec format
-----------------
A theme spec is a JSON file matching the ThemeSpec schema:

{
  "name": "Corporate Blue",
  "colors": [
    {"name": "primary", "hex_color": "#1A73E8"},
    {"name": "secondary", "hex_color": "#34A853"}
  ],
  "title_font": {"family": "Google Sans", "size_pt": 36, "bold": true},
  "body_font": {"family": "Google Sans", "size_pt": 14},
  "background_color": "#FFFFFF"
}

What this does (and does not) do
----------------------------------
Because the Slides API does not expose direct theme/master mutation endpoints,
this command applies styles by iterating over all shape elements on all slides
and updating their text style properties directly. This is a "deck-wide style
preset layer" approach as described in the spec.

TRUE theme/master mutation (changing the master slide itself) requires using
the Slides API's presentations.batchUpdate with UpdateMasterRequest, which is
not supported in the MVP due to its complexity. The current approach is simpler,
deterministic, and fully reversible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException, AgentError, ErrorCode
from slides_agent.core.models import ThemeColor, ThemeSpec, FontSpec
from slides_agent.core.output import emit, dry_run_envelope
from slides_agent.core.parser import parse_presentation
from slides_agent.schemas.theme import ThemeApplyOutput, ThemeListOutput

app = typer.Typer(
    name="theme",
    help="Apply style presets deck-wide.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------

BUILTIN_PRESETS: list[ThemeSpec] = [
    ThemeSpec(
        name="corporate-blue",
        colors=[
            ThemeColor(name="primary", hex_color="#1A73E8"),
            ThemeColor(name="secondary", hex_color="#34A853"),
            ThemeColor(name="accent", hex_color="#FBBC04"),
        ],
        title_font=FontSpec(family="Google Sans", size_pt=36, bold=True),
        body_font=FontSpec(family="Google Sans", size_pt=14),
        background_color="#FFFFFF",
    ),
    ThemeSpec(
        name="dark-professional",
        colors=[
            ThemeColor(name="primary", hex_color="#FFFFFF"),
            ThemeColor(name="secondary", hex_color="#90CAF9"),
            ThemeColor(name="accent", hex_color="#FFB74D"),
        ],
        title_font=FontSpec(family="Roboto", size_pt=40, bold=True),
        body_font=FontSpec(family="Roboto", size_pt=16),
        background_color="#1A1A2E",
    ),
    ThemeSpec(
        name="minimal-clean",
        colors=[
            ThemeColor(name="primary", hex_color="#212121"),
            ThemeColor(name="secondary", hex_color="#757575"),
            ThemeColor(name="accent", hex_color="#F44336"),
        ],
        title_font=FontSpec(family="Open Sans", size_pt=32, bold=False),
        body_font=FontSpec(family="Open Sans", size_pt=13),
        background_color="#FAFAFA",
    ),
]


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0


def _build_style_requests(
    spec: ThemeSpec,
    presentation_id: str,
    raw: dict,
) -> list[dict]:
    """Build batchUpdate requests to apply theme styles to all shape elements."""
    requests = []
    slides = raw.get("slides", [])

    for slide in slides:
        slide_id = slide.get("objectId")

        # Change slide background if specified
        if spec.background_color:
            r, g, b = _hex_to_rgb(spec.background_color)
            requests.append({
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
            })

        for element in slide.get("pageElements", []):
            shape = element.get("shape")
            if not shape or not shape.get("text"):
                continue

            element_id = element.get("objectId")
            placeholder = shape.get("placeholder", {})
            placeholder_type = placeholder.get("type", "")
            is_title = placeholder_type in ("TITLE", "CENTERED_TITLE", "SUBTITLE")

            font = spec.title_font if is_title else spec.body_font
            if font is None:
                continue

            text_elements = shape.get("text", {}).get("textElements", [])
            for text_element in text_elements:
                text_run = text_element.get("textRun")
                if not text_run:
                    continue

                style: dict = {"fontFamily": font.family}
                if font.size_pt:
                    style["fontSize"] = {"magnitude": font.size_pt, "unit": "PT"}
                if font.bold:
                    style["bold"] = True

                if spec.colors:
                    r, g, b = _hex_to_rgb(spec.colors[0].hex_color)
                    style["foregroundColor"] = {
                        "opaqueColor": {"rgbColor": {"red": r, "green": g, "blue": b}}
                    }

                # Calculate the text range for this run
                start_index = text_element.get("startIndex", 0)
                end_index = text_element.get("endIndex", 0)

                requests.append({
                    "updateTextStyle": {
                        "objectId": element_id,
                        "textRange": {"type": "FIXED_RANGE", "startIndex": start_index, "endIndex": end_index},
                        "style": style,
                        "fields": "fontFamily,fontSize,bold,foregroundColor",
                    }
                })

    return requests


@app.command("apply")
def apply_theme(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    spec_file: Annotated[
        Optional[Path],
        typer.Option("--spec-file", "-f", help="Path to a theme JSON spec file."),
    ] = None,
    preset: Annotated[
        Optional[str],
        typer.Option("--preset", help="Built-in preset name (use `theme list-presets` to see options)."),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
    schema: Annotated[bool, typer.Option("--schema", help="Emit JSON schema for the theme spec.")] = False,
) -> None:
    """Apply a theme preset or spec file to all slides in a presentation.

    \b
    WHAT IT DOES
    Updates font families, sizes, colors, and background colors across all
    slides and shape elements. Title placeholders receive the title_font;
    all other text shapes receive the body_font. This is a deck-wide style
    layer — it does NOT modify the Google Slides theme/master object.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --spec-file OR --preset    (exactly one required)

    \b
    SPEC FILE FORMAT
    See `slides-agent theme list-presets --pretty` for example JSON structures.

    \b
    FAILURE MODES
    - io_error: Spec file not found or malformed JSON.
    - validation_error: Spec fails schema validation.

    \b
    EXAMPLES
    slides-agent theme apply -p abc123 --preset corporate-blue
    slides-agent theme apply -p abc123 --spec-file ./my_theme.json --dry-run
    slides-agent theme apply -p abc123 --preset dark-professional --pretty
    """
    if examples:
        print("slides-agent theme apply -p abc123 --preset corporate-blue")
        print("slides-agent theme apply -p abc123 --spec-file ./my_theme.json --dry-run")
        print("slides-agent theme apply -p abc123 --preset dark-professional --pretty")
        raise typer.Exit()

    if schema:
        print(json.dumps(ThemeSpec.model_json_schema(), indent=2))
        raise typer.Exit()

    if spec_file and preset:
        AgentError(
            error_code=ErrorCode.validation_error,
            detail="Provide either --spec-file or --preset, not both.",
        ).emit(pretty=pretty)

    if not spec_file and not preset:
        AgentError(
            error_code=ErrorCode.validation_error,
            detail="Either --spec-file or --preset is required.",
            hint="Run `slides-agent theme list-presets` to see available presets.",
        ).emit(pretty=pretty)

    # Load the theme spec
    if spec_file:
        if not spec_file.exists():
            AgentError(
                error_code=ErrorCode.io_error,
                detail=f"Theme spec file not found: {spec_file}",
            ).emit(pretty=pretty)
        try:
            spec_data = json.loads(spec_file.read_text())
            spec = ThemeSpec.model_validate(spec_data)
        except Exception as exc:
            AgentError(
                error_code=ErrorCode.validation_error,
                detail=f"Invalid theme spec: {exc}",
                field="spec_file",
            ).emit(pretty=pretty)
    else:
        spec = next((p for p in BUILTIN_PRESETS if p.name == preset), None)
        if spec is None:
            AgentError(
                error_code=ErrorCode.not_found,
                detail=f"Preset '{preset}' not found.",
                hint=f"Available: {', '.join(p.name for p in BUILTIN_PRESETS if p.name)}",
            ).emit(pretty=pretty)

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    requests = _build_style_requests(spec, presentation_id, raw)  # type: ignore[arg-type]
    slides_affected = list({s.get("objectId") for s in raw.get("slides", [])})

    if dry_run:
        emit(
            dry_run_envelope(
                presentation_id=presentation_id,
                would_apply=requests,
                warnings=[f"{len(requests)} style update requests prepared."],
            ),
            pretty=pretty,
        )
        return

    if requests:
        try:
            slides_client.batch_update(presentation_id, requests)
        except AgentException as exc:
            exc.error.emit(pretty=pretty)

    output = ThemeApplyOutput(
        presentation_id=presentation_id,
        applied_spec=spec,  # type: ignore[arg-type]
        slides_affected=slides_affected,
        elements_affected=len(requests),
    )
    emit(output, pretty=pretty)


@app.command("list-presets")
def list_presets(
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """List all built-in theme presets.

    \b
    WHAT IT DOES
    Returns JSON descriptions of all built-in theme presets. Use a preset
    name with `theme apply --preset <name>` or use one as a template for
    your own spec file.

    \b
    EXAMPLES
    slides-agent theme list-presets --pretty
    slides-agent theme list-presets | jq '[.presets[].name]'
    """
    output = ThemeListOutput(presets=BUILTIN_PRESETS)
    emit(output, pretty=pretty)
