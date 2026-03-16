"""schema command group — emit JSON schemas for all commands.

Commands
--------
slides-agent schema list         List all available schema names.
slides-agent schema show <name>  Emit the JSON schema for a named type.

Available schemas
-----------------
presentation    Full PresentationSummary output (deck inspect).
slide           SlideSummary output (slide list/inspect).
element         PageElement output (element list/inspect).
patch-plan      PatchPlan output (patch plan).
patch-apply     PatchApplyReport output (patch apply).
patch-operation All supported patch operation types.
theme-spec      ThemeSpec input (theme apply --spec-file).
error           AgentError error envelope.

Usage
-----
slides-agent schema show presentation | jq '.properties.slides'
slides-agent schema show patch-operation > ops-schema.json
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from slides_agent.core.output import emit

app = typer.Typer(
    name="schema",
    help="Emit JSON schemas for command inputs and outputs.",
    no_args_is_help=True,
)

SCHEMA_REGISTRY: dict[str, str] = {
    "presentation": "slides_agent.core.models:PresentationSummary",
    "slide": "slides_agent.core.models:SlideSummary",
    "element": "slides_agent.core.models:PageElement",
    "text-content": "slides_agent.core.models:TextContent",
    "theme-spec": "slides_agent.core.models:ThemeSpec",
    "patch-plan": "slides_agent.schemas.patch:PatchPlan",
    "patch-apply": "slides_agent.schemas.patch:PatchApplyReport",
    "patch-operation-update-text": "slides_agent.schemas.patch:UpdateTextOp",
    "patch-operation-replace-text": "slides_agent.schemas.patch:ReplaceTextOp",
    "patch-operation-set-notes": "slides_agent.schemas.patch:SetNotesOp",
    "patch-operation-create-slide": "slides_agent.schemas.patch:CreateSlideOp",
    "patch-operation-delete-slide": "slides_agent.schemas.patch:DeleteSlideOp",
    "patch-operation-duplicate-slide": "slides_agent.schemas.patch:DuplicateSlideOp",
    "patch-operation-reorder-slide": "slides_agent.schemas.patch:ReorderSlideOp",
    "patch-operation-insert-image": "slides_agent.schemas.patch:InsertImageOp",
    "patch-operation-replace-image": "slides_agent.schemas.patch:ReplaceImageOp",
    "patch-operation-change-background": "slides_agent.schemas.patch:ChangeBackgroundOp",
    "patch-operation-update-style": "slides_agent.schemas.patch:UpdateStyleOp",
    "error": "slides_agent.core.errors:AgentError",
    "deck-inspect": "slides_agent.schemas.deck:DeckInspectOutput",
    "deck-duplicate": "slides_agent.schemas.deck:DeckDuplicateOutput",
    "slide-list": "slides_agent.schemas.slide:SlideListOutput",
    "slide-mutation": "slides_agent.schemas.slide:SlideMutationOutput",
    "theme-apply": "slides_agent.schemas.theme:ThemeApplyOutput",
}


def _load_model(dotpath: str):
    """Import a class by 'module:ClassName' string."""
    module_path, class_name = dotpath.split(":")
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@app.command("list")
def list_schemas(
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """List all available schema names.

    \b
    EXAMPLES
    slides-agent schema list
    slides-agent schema list | jq '.schemas[]'
    """
    emit({"ok": True, "schemas": sorted(SCHEMA_REGISTRY.keys())}, pretty=pretty)


@app.command("show")
def show_schema(
    name: Annotated[str, typer.Argument(help="Schema name (from `schema list`).")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Emit the JSON schema for a named type.

    \b
    WHAT IT DOES
    Imports the Pydantic model for the named schema and emits its
    JSON Schema (draft 7) to stdout. Useful for validation, documentation,
    and code generation.

    \b
    EXAMPLES
    slides-agent schema show presentation
    slides-agent schema show patch-plan | jq '.properties'
    slides-agent schema show patch-operation-update-text > op-schema.json
    slides-agent schema show error
    """
    if name not in SCHEMA_REGISTRY:
        from slides_agent.core.errors import AgentError, ErrorCode
        AgentError(
            error_code=ErrorCode.not_found,
            detail=f"Schema '{name}' not found.",
            hint=f"Available schemas: {', '.join(sorted(SCHEMA_REGISTRY.keys()))}",
        ).emit(pretty=pretty)

    try:
        model_class = _load_model(SCHEMA_REGISTRY[name])
        schema = model_class.model_json_schema()
        print(json.dumps(schema, indent=2 if pretty else None))
    except Exception as exc:
        from slides_agent.core.errors import AgentError, ErrorCode
        AgentError(
            error_code=ErrorCode.api_error,
            detail=f"Failed to generate schema for '{name}': {exc}",
        ).emit(pretty=pretty)
