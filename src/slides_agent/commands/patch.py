"""patch command group — plan and apply structured operation sets.

Commands
--------
slides-agent patch plan      Validate a set of operations against the current presentation.
slides-agent patch apply     Apply a validated patch plan to the presentation.
slides-agent patch validate  Validate a plan file without applying it.

The plan/apply workflow
-----------------------
This is the safest way to make multiple changes to a presentation:

1. Build an operations JSON file:
   [
     {"type": "update_text", "presentation_id": "abc123", "slide_id": "g1", "element_id": "title_1", "text": "New Title"},
     {"type": "set_notes",   "presentation_id": "abc123", "slide_id": "g1", "text": "Talk track..."},
     {"type": "replace_text","presentation_id": "abc123", "find": "{{customer}}", "replace": "Acme Corp"}
   ]

2. Validate the plan:
   slides-agent patch plan --presentation-id abc123 --operations-file ops.json > plan.json

3. Review plan.json — check for unresolved_references and validation_warnings.

4. Apply the plan:
   slides-agent patch apply --plan-file plan.json

5. Review the execution report for succeeded/failed counts.

Supported operation types
--------------------------
update_text, replace_text, set_notes, create_slide, delete_slide,
duplicate_slide, reorder_slide, insert_image, replace_image,
change_background, update_style

See `slides-agent schema patch` for the full operation schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException, AgentError, ErrorCode
from slides_agent.core.output import emit, dry_run_envelope
from slides_agent.core.parser import parse_presentation
from slides_agent.schemas.patch import (
    PatchApplyReport,
    PatchPlan,
    ValidationWarning,
)

app = typer.Typer(
    name="patch",
    help="Plan and apply structured operation sets.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Operation executor
# ---------------------------------------------------------------------------


def _build_request_for_operation(op: dict, raw: dict) -> tuple[list[dict], list[str]]:
    """Convert a typed operation dict into Slides API batchUpdate requests.

    Returns (requests, warnings).
    """
    op_type = op.get("type")
    requests = []
    warnings = []

    if op_type == "update_text":
        element_id = op["element_id"]
        text = op["text"]
        requests = [
            {"deleteText": {"objectId": element_id, "textRange": {"type": "ALL"}}},
            {"insertText": {"objectId": element_id, "insertionIndex": 0, "text": text}},
        ]

    elif op_type == "replace_text":
        requests = [{
            "replaceAllText": {
                "containsText": {"text": op["find"], "matchCase": op.get("match_case", True)},
                "replaceText": op["replace"],
            }
        }]

    elif op_type == "set_notes":
        slide_id = op["slide_id"]
        text = op["text"]
        notes_element_id = _find_notes_element_id(raw, slide_id)
        if notes_element_id is None:
            warnings.append(f"No notes body placeholder on slide '{slide_id}'.")
        else:
            requests = [
                {"deleteText": {"objectId": notes_element_id, "textRange": {"type": "ALL"}}},
                {"insertText": {"objectId": notes_element_id, "insertionIndex": 0, "text": text}},
            ]

    elif op_type == "create_slide":
        req: dict = {}
        if "insertion_index" in op and op["insertion_index"] is not None:
            req["insertionIndex"] = op["insertion_index"]
        if "layout" in op and op["layout"]:
            req["slideLayoutReference"] = {"predefinedLayout": op["layout"]}
        requests = [{"createSlide": req}]

    elif op_type == "delete_slide":
        requests = [{"deleteObject": {"objectId": op["slide_id"]}}]

    elif op_type == "duplicate_slide":
        requests = [{"duplicateObject": {"objectId": op["slide_id"]}}]

    elif op_type == "reorder_slide":
        requests = [{
            "updateSlidesPosition": {
                "slideObjectIds": [op["slide_id"]],
                "insertionIndex": op["insertion_index"],
            }
        }]

    elif op_type == "insert_image":
        element_properties: dict = {
            "pageObjectId": op["slide_id"],
            "transform": {
                "scaleX": 1,
                "scaleY": 1,
                "translateX": op.get("left_emu", 0),
                "translateY": op.get("top_emu", 0),
                "unit": "EMU",
            },
        }
        if op.get("width_emu") and op.get("height_emu"):
            element_properties["size"] = {
                "width": {"magnitude": op["width_emu"], "unit": "EMU"},
                "height": {"magnitude": op["height_emu"], "unit": "EMU"},
            }
        requests = [{"createImage": {"url": op["image_url"], "elementProperties": element_properties}}]

    elif op_type == "replace_image":
        requests = [{
            "replaceImage": {
                "imageObjectId": op["element_id"],
                "url": op["image_url"],
                "imageReplaceMethod": "CENTER_INSIDE",
            }
        }]

    elif op_type == "change_background":
        hex_color = op["color_hex"].lstrip("#")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        slide_ids = [op["slide_id"]] if op.get("slide_id") else [s.get("objectId") for s in raw.get("slides", [])]
        for sid in slide_ids:
            requests.append({
                "updatePageProperties": {
                    "objectId": sid,
                    "pageProperties": {
                        "pageBackgroundFill": {
                            "solidFill": {"color": {"rgbColor": {"red": r, "green": g, "blue": b}}}
                        }
                    },
                    "fields": "pageBackgroundFill.solidFill.color",
                }
            })

    elif op_type == "update_style":
        style: dict = {}
        fields = []
        if op.get("bold") is not None:
            style["bold"] = op["bold"]
            fields.append("bold")
        if op.get("italic") is not None:
            style["italic"] = op["italic"]
            fields.append("italic")
        if op.get("font_family"):
            style["fontFamily"] = op["font_family"]
            fields.append("fontFamily")
        if op.get("font_size_pt"):
            style["fontSize"] = {"magnitude": op["font_size_pt"], "unit": "PT"}
            fields.append("fontSize")
        if op.get("foreground_color_hex"):
            hex_c = op["foreground_color_hex"].lstrip("#")
            style["foregroundColor"] = {
                "opaqueColor": {
                    "rgbColor": {
                        "red": int(hex_c[0:2], 16) / 255.0,
                        "green": int(hex_c[2:4], 16) / 255.0,
                        "blue": int(hex_c[4:6], 16) / 255.0,
                    }
                }
            }
            fields.append("foregroundColor")

        if style and fields:
            requests = [{
                "updateTextStyle": {
                    "objectId": op["element_id"],
                    "textRange": {"type": "ALL"},
                    "style": style,
                    "fields": ",".join(fields),
                }
            }]

    else:
        warnings.append(f"Unknown operation type: {op_type!r}")

    return requests, warnings


def _find_notes_element_id(raw: dict, slide_id: str) -> str | None:
    for slide in raw.get("slides", []):
        if slide.get("objectId") != slide_id:
            continue
        notes_page = slide.get("slideProperties", {}).get("notesPage", {})
        for element in notes_page.get("pageElements", []):
            if element.get("shape", {}).get("placeholder", {}).get("type") == "BODY":
                return element.get("objectId")
    return None


def _validate_operation(op: dict, raw: dict, index: int) -> list[ValidationWarning]:
    """Check that referenced IDs exist in the raw presentation."""
    warnings = []
    op_type = op.get("type", "")
    slide_ids = {s.get("objectId") for s in raw.get("slides", [])}
    element_ids = {
        e.get("objectId")
        for s in raw.get("slides", [])
        for e in s.get("pageElements", [])
    }

    if op_type in ("update_text", "set_notes", "delete_slide", "duplicate_slide", "reorder_slide", "change_background"):
        slide_id = op.get("slide_id")
        if slide_id and slide_id not in slide_ids:
            warnings.append(ValidationWarning(
                operation_index=index,
                message=f"slide_id '{slide_id}' not found in presentation.",
                severity="error",
            ))

    if op_type in ("update_text", "replace_image", "update_style"):
        element_id = op.get("element_id")
        if element_id and element_id not in element_ids:
            warnings.append(ValidationWarning(
                operation_index=index,
                message=f"element_id '{element_id}' not found in presentation.",
                severity="error",
            ))

    return warnings


@app.command("plan")
def plan(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    operations_file: Annotated[Path, typer.Option("--operations-file", "-o", help="JSON file containing an array of typed operations.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
    schema: Annotated[bool, typer.Option("--schema", help="Emit JSON schema for operations and exit.")] = False,
) -> None:
    """Validate a set of operations against the current presentation state.

    \b
    WHAT IT DOES
    Reads the operations file, fetches the current presentation, validates
    all referenced IDs (slides, elements), and produces a validated plan
    JSON file suitable for `patch apply`. Does NOT mutate anything.

    \b
    REQUIRED
    --presentation-id      The presentation to validate against.
    --operations-file      JSON array of typed operation objects.

    \b
    OPERATIONS FILE FORMAT
    [
      {"type": "update_text", "presentation_id": "...", "slide_id": "...",
       "element_id": "...", "text": "New Title"},
      {"type": "replace_text", "presentation_id": "...",
       "find": "{{customer}}", "replace": "Acme Corp"},
      {"type": "set_notes", "presentation_id": "...",
       "slide_id": "...", "text": "Talk track"}
    ]

    \b
    OUTPUT
    A PatchPlan JSON including the operations list, any validation warnings
    or errors, and a list of unresolved ID references.

    \b
    EXAMPLES
    slides-agent patch plan -p abc123 --operations-file ops.json > plan.json
    slides-agent patch plan -p abc123 -o ops.json --pretty
    slides-agent patch plan -p abc123 -o ops.json | jq '.unresolved_references'
    """
    if examples:
        print("slides-agent patch plan -p abc123 --operations-file ops.json > plan.json")
        print("slides-agent patch plan -p abc123 -o ops.json --pretty")
        print("slides-agent patch plan -p abc123 -o ops.json | jq '.unresolved_references'")
        raise typer.Exit()

    if schema:
        print(json.dumps(PatchPlan.model_json_schema(), indent=2))
        raise typer.Exit()

    if not operations_file.exists():
        AgentError(
            error_code=ErrorCode.io_error,
            detail=f"Operations file not found: {operations_file}",
        ).emit(pretty=pretty)

    try:
        operations = json.loads(operations_file.read_text())
    except Exception as exc:
        AgentError(
            error_code=ErrorCode.validation_error,
            detail=f"Invalid JSON in operations file: {exc}",
        ).emit(pretty=pretty)

    if not isinstance(operations, list):
        AgentError(
            error_code=ErrorCode.validation_error,
            detail="Operations file must contain a JSON array.",
        ).emit(pretty=pretty)

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    all_warnings: list[ValidationWarning] = []
    unresolved = []

    for i, op in enumerate(operations):
        op_warnings = _validate_operation(op, raw, i)
        all_warnings.extend(op_warnings)
        for w in op_warnings:
            if w.severity == "error":
                ref = op.get("slide_id") or op.get("element_id") or "?"
                if ref not in unresolved:
                    unresolved.append(ref)

    output = PatchPlan(
        presentation_id=presentation_id,
        operation_count=len(operations),
        operations=operations,
        unresolved_references=unresolved,
        validation_warnings=all_warnings,
        warnings=[f"{len(all_warnings)} validation issue(s) found." if all_warnings else "All references resolved."],
    )
    emit(output, pretty=pretty)


@app.command("apply")
def apply_plan(
    plan_file: Annotated[Path, typer.Option("--plan-file", "-f", help="JSON plan file from `patch plan`.")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Validate and preview without applying.")] = False,
    skip_validation: Annotated[bool, typer.Option("--skip-validation", help="Skip re-validation of IDs.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Apply a validated patch plan to a presentation.

    \b
    WHAT IT DOES
    Reads the plan JSON produced by `patch plan`, optionally re-validates
    all references against the current presentation state, then applies
    each operation in order via batchUpdate. Returns an execution report.

    \b
    REQUIRED
    --plan-file    Path to the plan JSON file from `patch plan`.

    \b
    SAFETY
    If the plan has unresolved_references, apply will abort unless you pass
    --skip-validation. Always review the plan before applying.

    \b
    FAILURE MODES
    - io_error: Plan file not found.
    - validation_error: Plan has unresolved references (without --skip-validation).
    - api_error: One or more operations rejected by the Slides API.

    \b
    EXAMPLES
    slides-agent patch apply --plan-file plan.json
    slides-agent patch apply --plan-file plan.json --dry-run
    slides-agent patch apply --plan-file plan.json --skip-validation
    """
    if examples:
        print("slides-agent patch apply --plan-file plan.json")
        print("slides-agent patch apply --plan-file plan.json --dry-run")
        raise typer.Exit()

    if not plan_file.exists():
        AgentError(error_code=ErrorCode.io_error, detail=f"Plan file not found: {plan_file}").emit(pretty=pretty)

    try:
        plan_data = json.loads(plan_file.read_text())
    except Exception as exc:
        AgentError(error_code=ErrorCode.validation_error, detail=f"Invalid JSON in plan file: {exc}").emit(pretty=pretty)

    presentation_id = plan_data.get("presentation_id", "")
    operations = plan_data.get("operations", [])
    unresolved = plan_data.get("unresolved_references", [])

    if unresolved and not skip_validation:
        AgentError(
            error_code=ErrorCode.validation_error,
            detail=f"Plan has {len(unresolved)} unresolved reference(s): {unresolved}",
            hint="Fix the referenced IDs or use --skip-validation to force apply.",
        ).emit(pretty=pretty)

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    # Build all API requests
    all_api_requests = []
    all_warnings = []
    results = []

    for i, op in enumerate(operations):
        api_requests, op_warnings = _build_request_for_operation(op, raw)
        all_warnings.extend(op_warnings)
        results.append({
            "operation_index": i,
            "type": op.get("type"),
            "api_requests": api_requests,
            "warnings": op_warnings,
        })
        all_api_requests.extend(api_requests)

    if dry_run:
        emit(
            dry_run_envelope(
                presentation_id=presentation_id,
                would_apply=all_api_requests,
                warnings=all_warnings,
            ),
            pretty=pretty,
        )
        return

    # Apply in batches (Slides API has a limit of ~100 per batchUpdate)
    succeeded = 0
    failed = 0
    BATCH_SIZE = 50

    for batch_start in range(0, len(all_api_requests), BATCH_SIZE):
        batch = all_api_requests[batch_start : batch_start + BATCH_SIZE]
        try:
            slides_client.batch_update(presentation_id, batch)
            succeeded += len(batch)
        except AgentException as exc:
            failed += len(batch)
            all_warnings.append(f"Batch starting at index {batch_start} failed: {exc.error.detail}")

    output = PatchApplyReport(
        ok=failed == 0,
        presentation_id=presentation_id,
        total_operations=len(operations),
        succeeded=succeeded,
        failed=failed,
        results=results,
        warnings=all_warnings,
        errors=[f"{failed} API request(s) failed."] if failed else [],
    )
    emit(output, pretty=pretty)


@app.command("validate")
def validate_plan(
    plan_file: Annotated[Path, typer.Option("--plan-file", "-f", help="JSON plan file to validate.")],
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Validate a plan file against the current presentation without applying it.

    \b
    WHAT IT DOES
    Re-fetches the presentation and checks that all slide IDs and element IDs
    referenced in the plan still exist. Returns a validation report.

    \b
    EXAMPLES
    slides-agent patch validate --plan-file plan.json
    slides-agent patch validate --plan-file plan.json --pretty
    """
    if not plan_file.exists():
        AgentError(error_code=ErrorCode.io_error, detail=f"Plan file not found: {plan_file}").emit(pretty=pretty)

    try:
        plan_data = json.loads(plan_file.read_text())
    except Exception as exc:
        AgentError(error_code=ErrorCode.validation_error, detail=f"Invalid JSON: {exc}").emit(pretty=pretty)

    presentation_id = plan_data.get("presentation_id", "")
    operations = plan_data.get("operations", [])

    creds = auth_core.require_credentials()
    slides_client, _ = build_clients(creds)

    try:
        raw = slides_client.get_presentation(presentation_id)
    except AgentException as exc:
        exc.error.emit(pretty=pretty)

    all_warnings = []
    unresolved = []

    for i, op in enumerate(operations):
        op_warnings = _validate_operation(op, raw, i)
        all_warnings.extend(op_warnings)
        for w in op_warnings:
            if w.severity == "error":
                ref = op.get("slide_id") or op.get("element_id") or "?"
                if ref not in unresolved:
                    unresolved.append(ref)

    valid = len(unresolved) == 0
    emit(
        {
            "ok": valid,
            "presentation_id": presentation_id,
            "operation_count": len(operations),
            "valid": valid,
            "unresolved_references": unresolved,
            "validation_warnings": [w.model_dump() for w in all_warnings],
            "warnings": [],
            "errors": [f"{len(unresolved)} unresolved reference(s)."] if unresolved else [],
        },
        pretty=pretty,
    )
