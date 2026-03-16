# Google Slides Agentic CLI Spec

## Goal

Build a standalone CLI for Google Slides that is optimized for AI agents first and humans second.

The CLI should make it easy for an agent to inspect a deck, plan deterministic changes, and apply
those changes with precise, machine-stable outputs. The core use case is conversational slide work:
an agent and user iterate on theme, structure, copy, layout, and visual treatment, and the agent
can then implement those decisions reliably.

## Product Principles

- AI-first: every command must be scriptable, non-interactive, and JSON-friendly.
- Deterministic: outputs should be stable, explicit, and easy for an agent to chain.
- Inspectable: the CLI should make the current deck structure easy to query before edits.
- Verbose by design: help text, examples, schemas, and error explanations should be unusually detailed.
- Safe by default: support `--dry-run`, validation, and plan/apply workflows.
- Idempotent when possible: repeated commands should avoid accidental duplicate objects.

## Primary Use Cases

1. Inspect an existing presentation deeply.
2. Create a new presentation from a template or theme preset.
3. Update existing slide text, notes, images, shapes, and layout properties.
4. Re-theme a deck: colors, fonts, backgrounds, spacing, alignment, hierarchy.
5. Apply a structured patch plan produced by an LLM.
6. Export enough structural detail that an LLM can reason about the deck without screenshots.

## Non-Goals For MVP

- Full WYSIWYG editing.
- Real-time collaborative editing.
- Pixel-perfect screenshot understanding inside the CLI itself.
- Multi-provider abstraction beyond Google Slides.

## Recommended Stack

- Language: Python 3.12
- CLI framework: Typer
- Schemas/validation: Pydantic v2
- Google auth/API: Google Slides API + Google Drive API
- Output formatting: JSON first, optional pretty text second
- Testing: pytest

Rationale:

- Typer gives strong CLI ergonomics plus good help text.
- Pydantic gives explicit schemas an agent can trust.
- Direct Slides API access is required for true edit operations via `presentations.batchUpdate`.

## Core Requirement

Do not build this as a thin wrapper around natural-language prompting.

Build explicit, low-level commands that map cleanly to slide operations. Agents should be able to:

- inspect
- select targets
- plan changes
- apply changes
- verify results

without hidden heuristics.

## Command Design

Use top-level groups like:

- `auth`
- `deck`
- `slide`
- `element`
- `text`
- `image`
- `notes`
- `theme`
- `template`
- `patch`
- `export`
- `schema`

### Example Commands

```bash
slides-agent auth status --json

slides-agent deck inspect --presentation-id <id> --json
slides-agent deck duplicate --presentation-id <id> --title "QBR v2" --json

slides-agent slide list --presentation-id <id> --json
slides-agent slide create --presentation-id <id> --layout TITLE_AND_BODY --after slide_3 --json
slides-agent slide delete --presentation-id <id> --slide-id slide_7 --json

slides-agent text replace --presentation-id <id> --find "{{customer}}" --replace "Acme" --json
slides-agent text set --presentation-id <id> --shape-id title_2 --text "Migration Overview" --json

slides-agent image replace --presentation-id <id> --element-id image_4 --file ./hero.png --json

slides-agent notes set --presentation-id <id> --slide-id slide_2 --text "Talk track..." --json

slides-agent theme apply --presentation-id <id> --spec-file ./theme.json --json

slides-agent patch plan --presentation-id <id> --instruction-file ./request.md --json
slides-agent patch apply --presentation-id <id> --plan-file ./plan.json --json
```

## Agent-First Output Rules

Every mutating command should return:

- target presentation ID
- affected slide IDs
- affected element IDs
- exact API requests applied
- before/after summary
- validation warnings
- error category if failed

Example response shape:

```json
{
  "ok": true,
  "presentation_id": "abc123",
  "applied_operations": [
    {
      "type": "update_text",
      "slide_id": "slide_2",
      "element_id": "title_2"
    }
  ],
  "warnings": [],
  "errors": []
}
```

## Required Features

### 1. Deck Inspection

The CLI must expose a rich inspect command that returns:

- presentation metadata
- ordered slides
- slide layouts
- page elements per slide
- text content
- notes content
- image metadata
- table/chart placeholders if present
- theme/master references where available

This inspect output is the foundation for agent planning.

### 2. Addressable Element Model

Agents need stable references. Every inspect result should include:

- `presentation_id`
- `slide_id`
- `element_id`
- element type
- bounding box / transform when available
- placeholder type when available
- raw text payload for text-bearing elements

### 3. Text Operations

Support:

- replace all text
- set text for a specific element
- append/prepend text
- clear text
- style text ranges when practical

### 4. Slide Operations

Support:

- create slide
- duplicate slide
- delete slide
- reorder slide
- change slide background
- set slide notes

### 5. Image Operations

Support:

- insert image
- replace image
- resize/reposition image
- set alt text / metadata if practical

### 6. Theme / Style Operations

MVP can be limited, but there should be a clear path for:

- font family changes
- theme color updates
- title/body style presets
- background presets
- spacing presets
- alignment presets

If true theme/master mutation is too large for MVP, support a deck-wide style preset layer that
updates element styles consistently.

### 7. Template Support

Support:

- create from template
- inspect placeholders
- fill placeholders from JSON
- save reusable spec files

### 8. Plan / Apply Workflow

This is critical for agent safety.

`patch plan` should:

- inspect current state
- produce a structured list of proposed operations
- include validations and unresolved references
- avoid mutating anything

`patch apply` should:

- consume a plan JSON file
- validate references again
- apply operations deterministically
- return a structured execution report

## Help System Requirements

Help must be unusually verbose and agent-friendly.

Every command should support:

- `--help`
- `--examples`
- `--schema`

`--help` should explain:

- what the command changes
- what IDs are required
- how to discover those IDs
- common failure modes
- JSON output shape

`--examples` should show at least 3 realistic examples.

`--schema` should emit JSON schema for the command input and output when practical.

## Error Model

Use explicit machine-readable error categories, for example:

- `auth_error`
- `not_found`
- `invalid_reference`
- `validation_error`
- `unsupported_operation`
- `api_error`
- `rate_limited`
- `conflict`

Include human-readable detail, but always include a stable `error_code`.

## Safety Requirements

- `--dry-run` for all mutating commands.
- `--no-input` support.
- no hidden prompts by default.
- fail loudly on ambiguous selectors.
- optional `--force` only when destructive.

## Implementation Notes

Use Google Slides API `presentations.batchUpdate` for true edit operations.

Likely request types include:

- `CreateSlideRequest`
- `DeleteObjectRequest`
- `DuplicateObjectRequest`
- `InsertTextRequest`
- `DeleteTextRequest`
- `ReplaceAllTextRequest`
- `UpdateTextStyleRequest`
- `UpdateParagraphStyleRequest`
- `UpdateShapePropertiesRequest`
- `UpdatePageElementTransformRequest`
- `UpdatePagePropertiesRequest`
- `CreateImageRequest`
- `ReplaceImageRequest` or equivalent image update flow

Also use Drive API for:

- copy
- permissions
- export
- file metadata

## Suggested MVP Milestones

### Milestone 1

- auth
- deck inspect
- slide list/read/delete
- notes set
- text replace-all
- create from template with JSON replacements

### Milestone 2

- element-level text set
- image replace
- slide create/duplicate/reorder
- dry-run plan/apply

### Milestone 3

- theme/style presets
- structured patch planner
- richer validation and schemas

## Acceptance Criteria

The MVP is successful if an agent can:

1. Inspect a deck and identify slide and element IDs.
2. Create a copy from a template.
3. Replace placeholder text from JSON.
4. Delete or duplicate slides deterministically.
5. Update speaker notes.
6. Produce a plan before applying changes.
7. Return structured JSON that another agent can reliably consume.

## Suggested Handoff Prompt For Another Agent

```md
Build a new standalone project called `slides-agent`.

Requirements:

- Use Google Slides API directly.
- Optimize the CLI for AI agents first and humans second.
- Make all commands non-interactive and JSON-first.
- Implement verbose `--help`, `--examples`, and `--schema` support.
- Follow the spec in `google-slides-agentic-cli-spec.md`.

Prioritize this MVP:

1. auth status/login bootstrap
2. deck inspect
3. slide list/delete
4. notes set
5. create from template with JSON replacements
6. replace-all text
7. patch plan / patch apply skeleton

Technical preferences:

- Python 3.12
- Typer
- Pydantic v2
- pytest

Design constraints:

- deterministic IDs in output
- structured machine-readable errors
- `--dry-run` for mutating commands
- detailed JSON responses suitable for chaining by another agent

Deliverables:

- working CLI
- README
- example commands
- test suite
- sample inspect output
- sample patch plan/apply flow
```
