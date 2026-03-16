"""image command group — image insert, replace, and resize.

Commands
--------
slides-agent image insert    Add a new image to a slide from a URL or local file.
slides-agent image replace   Swap an existing image element's content.
slides-agent image resize    Reposition or resize an existing image element.

Image sources
--------------
The Slides API requires images to be publicly accessible via URL at the time
of insertion. For local files, use --file to upload via Drive first.

Position and size units
------------------------
All position and size values use EMUs (English Metric Units):
  1 inch  = 914400 EMU
  1 point = 12700 EMU

A standard Google Slides canvas (widescreen) is:
  9144000 EMU wide (10 inches)
  5143500 EMU tall (~5.63 inches)
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.api import build_clients
from slides_agent.core.errors import AgentException, AgentError, ErrorCode
from slides_agent.core.output import emit, dry_run_envelope
from slides_agent.schemas.slide import AppliedOperation, SlideMutationOutput

app = typer.Typer(
    name="image",
    help="Image operations: insert, replace, resize.",
    no_args_is_help=True,
)


@app.command("insert")
def insert_image(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Target slide object ID.")],
    url: Annotated[Optional[str], typer.Option("--url", help="Publicly accessible image URL.")] = None,
    file: Annotated[Optional[Path], typer.Option("--file", help="Local image file path (uploads to Drive).")] = None,
    left: Annotated[float, typer.Option("--left", help="Left offset in EMUs from slide left edge.")] = 0.0,
    top: Annotated[float, typer.Option("--top", help="Top offset in EMUs from slide top edge.")] = 0.0,
    width: Annotated[Optional[float], typer.Option("--width", help="Width in EMUs.")] = None,
    height: Annotated[Optional[float], typer.Option("--height", help="Height in EMUs.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Insert a new image onto a slide.

    \b
    WHAT IT DOES
    Adds an image element to the specified slide. The image must be publicly
    accessible via URL, or you can provide a local file which will be uploaded
    to Drive first.

    \b
    REQUIRED
    --presentation-id    The target presentation.
    --slide-id           The target slide.
    --url OR --file      Image source (exactly one required).

    \b
    OPTIONAL
    --left / --top       Position in EMUs from top-left of slide (default: 0, 0).
    --width / --height   Size in EMUs. If omitted, the image's natural size is used.

    \b
    EMU CONVERSIONS
    1 inch  = 914400 EMU
    Center of a 10in wide slide = 4572000 EMU

    \b
    FAILURE MODES
    - validation_error: Neither --url nor --file provided, or both provided.
    - io_error: Local file not found.
    - api_error: Image URL not accessible or unsupported format.

    \b
    EXAMPLES
    slides-agent image insert -p abc123 -s g1 --url 'https://example.com/logo.png'
    slides-agent image insert -p abc123 -s g1 --file ./hero.png --left 914400 --top 457200
    slides-agent image insert -p abc123 -s g1 --url 'https://...' --width 3657600 --height 2057400
    """
    if examples:
        print("slides-agent image insert -p abc123 -s g1 --url 'https://example.com/logo.png'")
        print("slides-agent image insert -p abc123 -s g1 --file ./hero.png --left 914400 --top 457200")
        print("slides-agent image insert -p abc123 -s g1 --url 'https://...' --width 3657600 --height 2057400 --dry-run")
        raise typer.Exit()

    if url and file:
        AgentError(
            error_code=ErrorCode.validation_error,
            detail="Provide either --url or --file, not both.",
            field="url/file",
        ).emit(pretty=pretty)

    if not url and not file:
        AgentError(
            error_code=ErrorCode.validation_error,
            detail="Either --url or --file is required.",
            field="url/file",
        ).emit(pretty=pretty)

    image_url = url

    if file:
        if not file.exists():
            AgentError(
                error_code=ErrorCode.io_error,
                detail=f"File not found: {file}",
                field="file",
            ).emit(pretty=pretty)
        if not dry_run:
            creds = auth_core.require_credentials()
            _, drive_client = build_clients(creds)
            try:
                image_url = drive_client.upload_image(str(file))
            except AgentException as exc:
                exc.error.emit(pretty=pretty)
        else:
            image_url = f"<uploaded:{file}>"

    element_properties: dict = {
        "pageObjectId": slide_id,
        "transform": {
            "scaleX": 1,
            "scaleY": 1,
            "translateX": left,
            "translateY": top,
            "unit": "EMU",
        },
    }
    if width and height:
        element_properties["size"] = {
            "width": {"magnitude": width, "unit": "EMU"},
            "height": {"magnitude": height, "unit": "EMU"},
        }

    request = {
        "createImage": {
            "url": image_url,
            "elementProperties": element_properties,
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
    new_id = replies[0].get("createImage", {}).get("objectId", "") if replies else ""

    output = SlideMutationOutput(
        presentation_id=presentation_id,
        applied_operations=[
            AppliedOperation(type="insert_image", slide_id=slide_id, element_id=new_id, detail={"image_url": image_url})
        ],
    )
    emit(output, pretty=pretty)


@app.command("replace")
def replace_image(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    element_id: Annotated[str, typer.Option("--element-id", "-e", help="Image element object ID to replace.")],
    url: Annotated[Optional[str], typer.Option("--url", help="New image URL.")] = None,
    file: Annotated[Optional[Path], typer.Option("--file", help="Local image file to upload and use.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Replace an existing image element's content.

    \b
    WHAT IT DOES
    Swaps the image content of an existing element without changing its
    position or size. The element_id must refer to an image element.

    \b
    REQUIRED
    --presentation-id / --slide-id / --element-id
    --url OR --file (exactly one)

    \b
    HOW TO FIND IMAGE ELEMENT IDs
    Run `slides-agent element list --type image` to see image element IDs.

    \b
    EXAMPLES
    slides-agent image replace -p abc123 -s g1 -e img_4 --url 'https://example.com/new.png'
    slides-agent image replace -p abc123 -s g1 -e img_4 --file ./new_hero.png
    slides-agent image replace -p abc123 -s g1 -e img_4 --url 'https://...' --dry-run
    """
    if examples:
        print("slides-agent image replace -p abc123 -s g1 -e img_4 --url 'https://example.com/new.png'")
        print("slides-agent image replace -p abc123 -s g1 -e img_4 --file ./new_hero.png")
        raise typer.Exit()

    if url and file:
        AgentError(
            error_code=ErrorCode.validation_error,
            detail="Provide either --url or --file, not both.",
        ).emit(pretty=pretty)
    if not url and not file:
        AgentError(
            error_code=ErrorCode.validation_error,
            detail="Either --url or --file is required.",
        ).emit(pretty=pretty)

    image_url = url

    if file:
        if not file.exists():
            AgentError(error_code=ErrorCode.io_error, detail=f"File not found: {file}").emit(pretty=pretty)
        if not dry_run:
            creds = auth_core.require_credentials()
            _, drive_client = build_clients(creds)
            try:
                image_url = drive_client.upload_image(str(file))
            except AgentException as exc:
                exc.error.emit(pretty=pretty)
        else:
            image_url = f"<uploaded:{file}>"

    request = {
        "replaceImage": {
            "imageObjectId": element_id,
            "url": image_url,
            "imageReplaceMethod": "CENTER_INSIDE",
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
            AppliedOperation(type="replace_image", slide_id=slide_id, element_id=element_id, detail={"image_url": image_url})
        ],
    )
    emit(output, pretty=pretty)


@app.command("resize")
def resize_image(
    presentation_id: Annotated[str, typer.Option("--presentation-id", "-p", help="Presentation ID.")],
    slide_id: Annotated[str, typer.Option("--slide-id", "-s", help="Slide object ID.")],
    element_id: Annotated[str, typer.Option("--element-id", "-e", help="Image element object ID.")],
    left: Annotated[Optional[float], typer.Option("--left", help="New left offset in EMUs.")] = None,
    top: Annotated[Optional[float], typer.Option("--top", help="New top offset in EMUs.")] = None,
    width: Annotated[Optional[float], typer.Option("--width", help="New width in EMUs.")] = None,
    height: Annotated[Optional[float], typer.Option("--height", help="New height in EMUs.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying.")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Reposition or resize an image element.

    \b
    WHAT IT DOES
    Updates the position and/or size of an existing image element. Provide
    any combination of --left, --top, --width, --height. Only the fields
    you specify are updated.

    \b
    EXAMPLES
    slides-agent image resize -p abc123 -s g1 -e img_4 --left 914400 --top 457200
    slides-agent image resize -p abc123 -s g1 -e img_4 --width 3657600 --height 2057400
    slides-agent image resize -p abc123 -s g1 -e img_4 --left 0 --top 0 --width 9144000 --height 5143500
    """
    if not any([left, top, width, height]):
        AgentError(
            error_code=ErrorCode.validation_error,
            detail="Provide at least one of --left, --top, --width, --height.",
        ).emit(pretty=pretty)

    transform: dict = {"scaleX": 1, "scaleY": 1, "unit": "EMU"}
    size: dict = {}
    fields = []

    if left is not None:
        transform["translateX"] = left
        fields.append("transform.translateX")
    if top is not None:
        transform["translateY"] = top
        fields.append("transform.translateY")
    if width is not None:
        size["width"] = {"magnitude": width, "unit": "EMU"}
        fields.append("size.width")
    if height is not None:
        size["height"] = {"magnitude": height, "unit": "EMU"}
        fields.append("size.height")

    request_body: dict = {"objectId": element_id}
    if transform:
        request_body["transform"] = transform
    if size:
        request_body["size"] = size

    request = {
        "updatePageElementTransform": {
            "objectId": element_id,
            "transform": transform,
            "applyMode": "ABSOLUTE",
        }
    }

    requests = [request]
    if size:
        requests.append({
            "updateShapeProperties": {
                "objectId": element_id,
                "shapeProperties": {},
                "fields": "size",
            }
        })

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
            AppliedOperation(type="resize_image", slide_id=slide_id, element_id=element_id)
        ],
    )
    emit(output, pretty=pretty)
