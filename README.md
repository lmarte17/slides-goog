# slides-agent

**AI-first CLI for Google Slides** — optimized for agents, scriptable, non-interactive, and JSON-native.

`slides-agent` gives AI agents (and humans) a deterministic, low-level interface to inspect and modify Google Slides presentations. Every command returns structured JSON. Every mutating command supports `--dry-run`. Every command has `--help`, `--examples`, and `--schema`.

---

## Table of Contents

- [Design Principles](#design-principles)
- [Installation](#installation)
- [Authentication Setup](#authentication-setup)
- [Quick Start](#quick-start)
- [Command Reference](#command-reference)
  - [auth](#auth)
  - [deck](#deck)
  - [slide](#slide)
  - [element](#element)
  - [text](#text)
  - [notes](#notes)
  - [image](#image)
  - [theme](#theme)
  - [template](#template)
  - [patch](#patch)
  - [export](#export)
  - [schema](#schema)
- [Agent Workflow Examples](#agent-workflow-examples)
- [Output Format](#output-format)
- [Error Model](#error-model)
- [Safety Features](#safety-features)
- [JSON Schema Reference](#json-schema-reference)
- [Development](#development)

---

## Design Principles

| Principle | What it means |
|-----------|---------------|
| **AI-first** | Every command is non-interactive, scriptable, and JSON-friendly. |
| **Deterministic** | Outputs have stable IDs. The same command always returns the same shape. |
| **Inspectable** | `deck inspect` gives agents everything they need to plan before mutating. |
| **Safe by default** | `--dry-run` on all mutating commands. Fail loudly on ambiguous inputs. |
| **Idempotent where possible** | `text replace` and `template fill` can be re-run safely. |
| **Verbose** | Unusually detailed `--help`, `--examples`, and `--schema` on every command. |

---

## Installation

**Requirements:** Python 3.12+

```bash
# Clone the repository
git clone <repo-url>
cd slides-goog

# Install (editable mode recommended for development)
pip install -e .

# Verify
slides-agent --version
slides-agent --help
```

For production use:
```bash
pip install slides-agent
```

---

## Authentication Setup

`slides-agent` uses Google OAuth2. You need a `client_secret.json` file from Google Cloud Console.

### Step 1 — Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or select an existing one)
3. Enable the **Google Slides API** and **Google Drive API**:
   - APIs & Services → Library → "Google Slides API" → Enable
   - APIs & Services → Library → "Google Drive API" → Enable

### Step 2 — Create OAuth2 Credentials

1. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
2. Application type: **Desktop app**
3. Download the JSON file — this is your `client_secret.json`

### Step 3 — Authenticate

```bash
slides-agent auth login --credentials-file ~/Downloads/client_secret.json
```

Your browser opens. Grant access. The token is cached at `~/.config/slides-agent/token.json`.

### Step 4 — Verify

```bash
slides-agent auth status
```

```json
{
  "ok": true,
  "authenticated": true,
  "token_file": "/Users/you/.config/slides-agent/token.json",
  "token_exists": true,
  "expired": false,
  "scopes": [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive"
  ],
  "client_id": "..."
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SLIDES_AGENT_CREDENTIALS` | Path to `client_secret.json` (overrides `--credentials-file`) |
| `SLIDES_AGENT_TOKEN_FILE` | Override the token cache path (default: `~/.config/slides-agent/token.json`) |

---

## Quick Start

```bash
# 1. Find your presentation ID from the URL:
#    https://docs.google.com/presentation/d/<PRESENTATION_ID>/edit

PRES_ID="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"

# 2. Inspect the full structure
slides-agent deck inspect --presentation-id $PRES_ID --pretty

# 3. List all slides and their IDs
slides-agent slide list --presentation-id $PRES_ID | jq '[.slides[] | {slide_id, slide_index}]'

# 4. Get all elements on slide 1
slides-agent element list --presentation-id $PRES_ID --slide-id <slide_id>

# 5. Replace all {{customer}} tokens
slides-agent text replace --presentation-id $PRES_ID --find '{{customer}}' --replace 'Acme Corp'

# 6. Set speaker notes
slides-agent notes set --presentation-id $PRES_ID --slide-id <slide_id> --text 'Talk track...'
```

---

## Command Reference

### How to Find IDs

**Presentation ID:** The segment between `/d/` and `/edit` in the Google Slides URL:
```
https://docs.google.com/presentation/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                       This is your presentation_id
```

**Slide IDs and Element IDs:** Run `deck inspect` or `slide list` and extract from the JSON output:
```bash
slides-agent deck inspect --presentation-id <id> | jq '.presentation.slides[].slide_id'
slides-agent element list --presentation-id <id> --slide-id <sid> | jq '.elements[].element_id'
```

---

### `auth`

Manage Google OAuth2 credentials.

#### `auth login`

```bash
slides-agent auth login --credentials-file /path/to/client_secret.json
```

| Flag | Description |
|------|-------------|
| `--credentials-file` / `-c` | Path to `client_secret.json`. Env: `SLIDES_AGENT_CREDENTIALS`. |
| `--pretty` | Pretty-print output. |

**Output:**
```json
{
  "ok": true,
  "authenticated": true,
  "token_file": "/Users/you/.config/slides-agent/token.json",
  "scopes": ["https://www.googleapis.com/auth/presentations", "..."],
  "message": "Login successful. Token cached."
}
```

#### `auth status`

```bash
slides-agent auth status
slides-agent auth status --pretty
```

Returns the current authentication state without making API calls.

#### `auth logout`

```bash
slides-agent auth logout
```

Deletes the cached token file. Does **not** revoke the token on Google's servers.

---

### `deck`

Presentation-level operations.

#### `deck inspect`

```bash
slides-agent deck inspect --presentation-id <id>
slides-agent deck inspect --presentation-id <id> --pretty
slides-agent deck inspect --presentation-id <id> --schema  # emit JSON schema
```

Returns the complete presentation structure: all slides, all elements, all text, all images, speaker notes, and theme references.

**This is the foundation for agent planning. Run it first.**

| Flag | Description |
|------|-------------|
| `--presentation-id` / `-p` | Presentation ID (required). |
| `--pretty` | Pretty-print output. |
| `--examples` | Show usage examples. |
| `--schema` | Emit JSON schema for the output. |

**Output shape:** See [examples/sample_inspect.json](examples/sample_inspect.json).

Key output fields:
- `presentation.slides[].slide_id` — use in slide/notes commands
- `presentation.slides[].elements[].element_id` — use in text/image commands
- `presentation.slides[].elements[].placeholder_type` — `TITLE`, `BODY`, `SUBTITLE`, etc.
- `presentation.slides[].elements[].text.raw_text` — current text content
- `presentation.slides[].notes_text` — current speaker notes

**Examples:**
```bash
# Get all slide IDs
slides-agent deck inspect -p abc123 | jq '[.presentation.slides[].slide_id]'

# Find all TITLE elements
slides-agent deck inspect -p abc123 | jq '[.presentation.slides[].elements[] | select(.placeholder_type == "TITLE") | {slide_id: .element_id, text: .text.raw_text}]'

# Get all text content across the deck
slides-agent deck inspect -p abc123 | jq '[.presentation.slides[].elements[] | select(.text != null) | .text.raw_text]'
```

#### `deck duplicate`

```bash
slides-agent deck duplicate --presentation-id <id> --title "QBR v2"
```

Creates an exact copy of the presentation. Returns the new presentation ID and URL.

| Flag | Description |
|------|-------------|
| `--presentation-id` / `-p` | Source presentation ID. |
| `--title` / `-t` | Title for the new presentation. |

**Output:**
```json
{
  "ok": true,
  "original_presentation_id": "abc123",
  "new_presentation_id": "xyz789",
  "new_title": "QBR v2",
  "drive_url": "https://docs.google.com/presentation/d/xyz789/edit",
  "warnings": [],
  "errors": []
}
```

---

### `slide`

Slide-level operations.

#### `slide list`

```bash
slides-agent slide list --presentation-id <id>
slides-agent slide list --presentation-id <id> | jq '[.slides[] | {slide_id, slide_index, layout_name}]'
```

Returns all slides with their IDs, indices, layouts, and element summaries.

#### `slide inspect`

```bash
slides-agent slide inspect --presentation-id <id> --slide-id <slide_id>
```

Full detail for a single slide — all elements, text, transforms, and notes.

#### `slide create`

```bash
slides-agent slide create --presentation-id <id> --layout TITLE_AND_BODY
slides-agent slide create --presentation-id <id> --layout BLANK --insertion-index 2
slides-agent slide create --presentation-id <id> --dry-run
```

| Flag | Description |
|------|-------------|
| `--insertion-index` / `-i` | 0-based position (appends at end if omitted). |
| `--layout` | Layout preset: `BLANK`, `CAPTION_ONLY`, `TITLE`, `TITLE_AND_BODY`, `TITLE_AND_TWO_COLUMNS`, `TITLE_ONLY`, `ONE_COLUMN_TEXT`, `MAIN_POINT`, `BIG_NUMBER`. |
| `--dry-run` | Preview without applying. |

**Output includes the new slide's `objectId` so you can immediately target it.**

#### `slide delete`

```bash
slides-agent slide delete --presentation-id <id> --slide-id <slide_id> --force
slides-agent slide delete --presentation-id <id> --slide-id <slide_id> --dry-run
```

⚠️ **Irreversible.** Use `--dry-run` first. Use `--force` to skip the confirmation prompt in non-interactive mode.

#### `slide duplicate`

```bash
slides-agent slide duplicate --presentation-id <id> --slide-id <slide_id>
```

Copies a slide immediately after the original. Returns the new slide's ID.

#### `slide reorder`

```bash
slides-agent slide reorder --presentation-id <id> --slide-id <slide_id> --insertion-index 0
```

Moves a slide to a 0-based index position.

#### `slide background`

```bash
slides-agent slide background --presentation-id <id> --slide-id <slide_id> --color '#1A73E8'
slides-agent slide background --presentation-id <id> --slide-id <slide_id> --color 'FFFFFF'
```

Changes the background color of a single slide to a solid color.

---

### `element`

Inspect and list page elements.

#### `element list`

```bash
slides-agent element list --presentation-id <id> --slide-id <slide_id>
slides-agent element list --presentation-id <id> --slide-id <slide_id> --type image
slides-agent element list --presentation-id <id> --slide-id <slide_id> | jq '.elements[] | {element_id, element_type, placeholder_type}'
```

| Flag | Description |
|------|-------------|
| `--type` / `-t` | Filter by type: `shape`, `image`, `table`, `chart`, `video`, `line`, `group`. |

**Element types:**
- `shape` — Text boxes and placeholders (these contain text)
- `image` — Bitmap images
- `table` — Data tables
- `chart` — Embedded Sheets charts
- `video` — Embedded videos
- `line` — Lines and connectors
- `group` — Grouped elements

#### `element inspect`

```bash
slides-agent element inspect --presentation-id <id> --slide-id <slide_id> --element-id <element_id>
```

Full detail for one element: type, placeholder, full text with paragraph/run structure, image URLs, bounding box, and transform.

---

### `text`

Read and mutate slide text.

#### `text replace`

```bash
slides-agent text replace --presentation-id <id> --find '{{customer}}' --replace 'Acme Corp'
slides-agent text replace --presentation-id <id> --find 'DRAFT' --replace 'FINAL' --no-match-case
slides-agent text replace --presentation-id <id> --find '{{date}}' --replace '2025-01-15' --dry-run
```

Replaces **all occurrences** of a string across the entire presentation (all slides, all elements, all notes). Uses the Slides API `replaceAllText` request.

This is the recommended way to fill template placeholders like `{{customer}}`, `{{date}}`, `{{version}}`.

| Flag | Description |
|------|-------------|
| `--find` / `-f` | The text to search for. |
| `--replace` / `-r` | The replacement text. |
| `--match-case` / `--no-match-case` | Case sensitivity (default: case-sensitive). |
| `--dry-run` | Preview the API request without applying. |

**Output:**
```json
{
  "ok": true,
  "presentation_id": "abc123",
  "applied_operations": [
    {"type": "replace_text", "find": "{{customer}}", "replace": "Acme Corp", "occurrences_changed": 3}
  ],
  "warnings": [],
  "errors": []
}
```

#### `text set`

```bash
slides-agent text set --presentation-id <id> --slide-id <sid> --element-id <eid> --text "New Title"
slides-agent text set --presentation-id <id> --slide-id <sid> --element-id <eid> --text $'Line 1\nLine 2'
slides-agent text set --presentation-id <id> --slide-id <sid> --element-id <eid> --text "Draft" --dry-run
```

Replaces **all text** in a specific element. The element is first cleared, then the new text is inserted. Element styling is preserved; inline formatting is reset.

#### `text append`

```bash
slides-agent text append --presentation-id <id> --slide-id <sid> --element-id <eid> --text '\nNew bullet'
```

Appends text to the end of an element's existing content.

#### `text clear`

```bash
slides-agent text clear --presentation-id <id> --slide-id <sid> --element-id <eid>
slides-agent text clear --presentation-id <id> --slide-id <sid> --element-id <eid> --dry-run
```

Removes all text from an element.

#### `text get`

```bash
slides-agent text get --presentation-id <id> --slide-id <sid> --element-id <eid>
slides-agent text get --presentation-id <id> --slide-id <sid> --element-id <eid> | jq -r '.text.raw_text'
```

Returns the text content of an element, including the full paragraph/run structure.

---

### `notes`

Speaker notes operations.

#### `notes get`

```bash
slides-agent notes get --presentation-id <id> --slide-id <slide_id>
slides-agent notes get --presentation-id <id> --slide-id <slide_id> | jq -r '.notes_text'
```

Returns the plain text of the speaker notes for a slide.

#### `notes set`

```bash
slides-agent notes set --presentation-id <id> --slide-id <slide_id> --text 'Talk track...'
slides-agent notes set --presentation-id <id> --slide-id <slide_id> --text $'Point 1\nPoint 2\nPoint 3'
slides-agent notes set --presentation-id <id> --slide-id <slide_id> --text 'Notes' --dry-run
```

Replaces the speaker notes for a slide with new text.

#### `notes clear`

```bash
slides-agent notes clear --presentation-id <id> --slide-id <slide_id>
```

Removes all speaker notes from a slide.

---

### `image`

Image operations.

#### `image insert`

```bash
# From a URL (image must be publicly accessible)
slides-agent image insert --presentation-id <id> --slide-id <sid> \
  --url 'https://example.com/logo.png' \
  --left 457200 --top 457200 \
  --width 3657600 --height 1828800

# From a local file (uploads to Drive first)
slides-agent image insert --presentation-id <id> --slide-id <sid> \
  --file ./hero.png \
  --left 0 --top 0
```

**EMU conversion:** `1 inch = 914400 EMU`. A standard 10-inch wide slide is `9144000 EMU`.

| Flag | Description |
|------|-------------|
| `--url` | Publicly accessible image URL. |
| `--file` | Local image file (uploads to Drive). |
| `--left` | Left offset in EMUs (default: 0). |
| `--top` | Top offset in EMUs (default: 0). |
| `--width` | Width in EMUs. |
| `--height` | Height in EMUs. |

#### `image replace`

```bash
slides-agent image replace --presentation-id <id> --slide-id <sid> \
  --element-id <image_element_id> \
  --url 'https://example.com/new-logo.png'
```

Swaps the image content of an existing element. Position and size are preserved.

#### `image resize`

```bash
slides-agent image resize --presentation-id <id> --slide-id <sid> --element-id <eid> \
  --left 457200 --top 457200 --width 4572000 --height 2571750
```

Repositions and/or resizes an image element.

---

### `theme`

Apply style presets deck-wide.

#### `theme list-presets`

```bash
slides-agent theme list-presets --pretty
slides-agent theme list-presets | jq '[.presets[].name]'
```

Lists all built-in theme presets. Available presets:

| Name | Description |
|------|-------------|
| `corporate-blue` | Google Blue primary, white background, Google Sans font |
| `dark-professional` | Dark navy background, Roboto font, light text |
| `minimal-clean` | White background, Open Sans font, minimal accent |

#### `theme apply`

```bash
# Apply a built-in preset
slides-agent theme apply --presentation-id <id> --preset corporate-blue

# Apply a custom spec file
slides-agent theme apply --presentation-id <id> --spec-file ./my_theme.json

# Preview without applying
slides-agent theme apply --presentation-id <id> --preset dark-professional --dry-run

# Get the schema for the spec file format
slides-agent theme apply --schema
```

**Theme spec format** (see [examples/sample_theme.json](examples/sample_theme.json)):
```json
{
  "name": "my-theme",
  "colors": [
    {"name": "primary", "hex_color": "#1A73E8"},
    {"name": "secondary", "hex_color": "#34A853"}
  ],
  "title_font": {"family": "Google Sans", "size_pt": 36, "bold": true},
  "body_font": {"family": "Google Sans", "size_pt": 14},
  "background_color": "#FFFFFF"
}
```

**How it works:** Updates font family, size, color, and background on all shape elements across all slides. Titles use `title_font`; all other text shapes use `body_font`. This is a deck-wide style layer — it does not modify the underlying Google Slides theme/master object.

---

### `template`

Create and fill presentation templates.

#### Template Token Syntax

Use double-brace tokens in your slide text:
```
{{customer}}  →  Acme Corporation
{{quarter}}   →  Q1 2025
{{date}}      →  January 15, 2025
{{arr}}       →  $4.2M
```

#### `template inspect`

```bash
slides-agent template inspect --presentation-id <id>
slides-agent template inspect --presentation-id <id> | jq '[.tokens | keys]'
```

Scans all text across all slides and returns every `{{token}}` found, along with which slide IDs contain each token.

**Output:**
```json
{
  "ok": true,
  "presentation_id": "abc123",
  "token_count": 4,
  "tokens": {
    "customer": ["slide_1", "slide_3"],
    "quarter": ["slide_1"],
    "date": ["slide_2"],
    "arr": ["slide_4"]
  },
  "unfilled": ["customer", "date", "arr", "quarter"],
  "warnings": [],
  "errors": []
}
```

#### `template fill`

```bash
slides-agent template fill --presentation-id <id> --values-file ./values.json
slides-agent template fill --presentation-id <id> --values-file ./values.json --dry-run
```

Fills all `{{token}}` placeholders from a JSON values file:
```json
{
  "customer": "Acme Corporation",
  "quarter": "Q1 2025",
  "date": "January 15, 2025",
  "arr": "$4.2M"
}
```

Tokens not present in the values file are left unchanged and reported as warnings.

#### `template create`

```bash
# Duplicate a template and fill it in one step
slides-agent template create \
  --template-id <template_presentation_id> \
  --title "Acme QBR Q1 2025" \
  --values-file ./acme_values.json
```

Duplicates a template presentation and optionally fills all token placeholders. The new presentation's ID and URL are returned.

---

### `patch`

Plan and apply structured operation sets.

The patch workflow is the **safest way to make multiple changes** to a presentation. It follows an explicit plan → review → apply sequence.

#### Patch Workflow

**Step 1 — Build an operations file:**

```json
[
  {"type": "update_text", "presentation_id": "abc123", "slide_id": "g1", "element_id": "title_1", "text": "New Title"},
  {"type": "replace_text", "presentation_id": "abc123", "find": "{{customer}}", "replace": "Acme Corp"},
  {"type": "set_notes", "presentation_id": "abc123", "slide_id": "g1", "text": "Talk track..."},
  {"type": "create_slide", "presentation_id": "abc123", "insertion_index": 2, "layout": "TITLE_AND_BODY"},
  {"type": "delete_slide", "presentation_id": "abc123", "slide_id": "g5"},
  {"type": "change_background", "presentation_id": "abc123", "slide_id": "g1", "color_hex": "#1A73E8"}
]
```

**Step 2 — Validate:**
```bash
slides-agent patch plan --presentation-id abc123 --operations-file ops.json > plan.json
```

**Step 3 — Review:** Check `unresolved_references` and `validation_warnings` in `plan.json`.

**Step 4 — Apply:**
```bash
slides-agent patch apply --plan-file plan.json
```

**Step 5 — Verify:**
```bash
slides-agent deck inspect --presentation-id abc123 --pretty
```

#### Supported Operation Types

| Type | Required Fields |
|------|----------------|
| `update_text` | `presentation_id`, `slide_id`, `element_id`, `text` |
| `replace_text` | `presentation_id`, `find`, `replace` |
| `set_notes` | `presentation_id`, `slide_id`, `text` |
| `create_slide` | `presentation_id`, `insertion_index`?, `layout`? |
| `delete_slide` | `presentation_id`, `slide_id` |
| `duplicate_slide` | `presentation_id`, `slide_id` |
| `reorder_slide` | `presentation_id`, `slide_id`, `insertion_index` |
| `insert_image` | `presentation_id`, `slide_id`, `image_url` |
| `replace_image` | `presentation_id`, `slide_id`, `element_id`, `image_url` |
| `change_background` | `presentation_id`, `slide_id`?, `color_hex` |
| `update_style` | `presentation_id`, `slide_id`, `element_id`, + style fields |

See `slides-agent schema show patch-plan` for the full schema.

#### `patch plan`

```bash
slides-agent patch plan --presentation-id <id> --operations-file ops.json
slides-agent patch plan --presentation-id <id> --operations-file ops.json > plan.json
slides-agent patch plan --presentation-id <id> --operations-file ops.json --pretty
slides-agent patch plan --schema  # emit operation JSON schema
```

Validates all operations against the current presentation. Returns a `PatchPlan` JSON with:
- `operations` — the validated operation list
- `unresolved_references` — IDs that couldn't be found
- `validation_warnings` — non-blocking issues

**Does not mutate anything.**

#### `patch apply`

```bash
slides-agent patch apply --plan-file plan.json
slides-agent patch apply --plan-file plan.json --dry-run
slides-agent patch apply --plan-file plan.json --skip-validation  # apply even with unresolved refs
```

Applies a validated plan. Re-validates ID references before applying. Operations are applied in order via `batchUpdate`. Returns a `PatchApplyReport` with `succeeded` and `failed` counts.

#### `patch validate`

```bash
slides-agent patch validate --plan-file plan.json
```

Re-validates a plan file against the current presentation state without applying it. Useful for checking that IDs haven't changed since the plan was created.

---

### `export`

Export presentations.

#### `export pdf`

```bash
slides-agent export pdf --presentation-id <id> --output ./deck.pdf
slides-agent export pdf --presentation-id <id> --output /tmp/presentation.pdf --pretty
```

Exports the presentation as a PDF using the Google Drive export API.

#### `export pptx`

```bash
slides-agent export pptx --presentation-id <id> --output ./deck.pptx
```

Exports the presentation as a PowerPoint (.pptx) file.

#### `export json`

```bash
# Export parsed model to stdout
slides-agent export json --presentation-id <id>

# Export to a file
slides-agent export json --presentation-id <id> --output deck.json --pretty

# Export raw API response
slides-agent export json --presentation-id <id> --raw | jq '.slides[0].pageElements'
```

Exports the presentation as JSON. By default, uses the parsed `PresentationSummary` model format (same as `deck inspect`). Use `--raw` to get the unmodified Google Slides API response.

---

### `schema`

Emit JSON schemas for all command inputs and outputs.

```bash
# List all available schemas
slides-agent schema list

# Show a schema
slides-agent schema show presentation
slides-agent schema show patch-plan | jq '.properties'
slides-agent schema show error

# Get the schema for update_text operations
slides-agent schema show patch-operation-update-text > update-text-schema.json
```

Available schemas:

| Name | Description |
|------|-------------|
| `presentation` | Full `PresentationSummary` (deck inspect output) |
| `slide` | `SlideSummary` (slide list/inspect output) |
| `element` | `PageElement` (element list/inspect output) |
| `text-content` | `TextContent` model |
| `theme-spec` | `ThemeSpec` input for `theme apply` |
| `patch-plan` | `PatchPlan` output from `patch plan` |
| `patch-apply` | `PatchApplyReport` output from `patch apply` |
| `patch-operation-update-text` | Schema for `update_text` operations |
| `patch-operation-replace-text` | Schema for `replace_text` operations |
| `patch-operation-set-notes` | Schema for `set_notes` operations |
| `patch-operation-create-slide` | Schema for `create_slide` operations |
| `patch-operation-delete-slide` | Schema for `delete_slide` operations |
| `patch-operation-duplicate-slide` | Schema for `duplicate_slide` operations |
| `patch-operation-reorder-slide` | Schema for `reorder_slide` operations |
| `patch-operation-insert-image` | Schema for `insert_image` operations |
| `patch-operation-replace-image` | Schema for `replace_image` operations |
| `patch-operation-change-background` | Schema for `change_background` operations |
| `patch-operation-update-style` | Schema for `update_style` operations |
| `error` | `AgentError` error envelope |
| `deck-inspect` | `DeckInspectOutput` |
| `deck-duplicate` | `DeckDuplicateOutput` |
| `slide-list` | `SlideListOutput` |
| `slide-mutation` | `SlideMutationOutput` |
| `theme-apply` | `ThemeApplyOutput` |

---

## Agent Workflow Examples

### Workflow 1: Inspect → Plan → Apply

```bash
PRES_ID="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"

# 1. Full inspection
slides-agent deck inspect --presentation-id $PRES_ID > inspection.json

# 2. Extract slide and element IDs for planning
SLIDE_1=$(cat inspection.json | jq -r '.presentation.slides[0].slide_id')
TITLE_EL=$(cat inspection.json | jq -r '.presentation.slides[0].elements[] | select(.placeholder_type == "TITLE") | .element_id')

# 3. Build operations file
cat > ops.json <<EOF
[
  {"type": "update_text", "presentation_id": "$PRES_ID", "slide_id": "$SLIDE_1", "element_id": "$TITLE_EL", "text": "Updated Title"},
  {"type": "set_notes", "presentation_id": "$PRES_ID", "slide_id": "$SLIDE_1", "text": "New talk track."},
  {"type": "replace_text", "presentation_id": "$PRES_ID", "find": "{{customer}}", "replace": "Acme Corp"}
]
EOF

# 4. Validate
slides-agent patch plan --presentation-id $PRES_ID --operations-file ops.json > plan.json
cat plan.json | jq '.unresolved_references'

# 5. Apply
slides-agent patch apply --plan-file plan.json

# 6. Verify
slides-agent deck inspect --presentation-id $PRES_ID | jq '.presentation.slides[0].elements[].text.raw_text'
```

### Workflow 2: Template → Fill → Export

```bash
TEMPLATE_ID="template_presentation_id"
VALUES='{"customer": "Acme Corp", "quarter": "Q2 2025", "date": "April 1, 2025"}'

# 1. Inspect the template to verify tokens
slides-agent template inspect --presentation-id $TEMPLATE_ID

# 2. Create and fill in one step
echo $VALUES > values.json
RESULT=$(slides-agent template create \
  --template-id $TEMPLATE_ID \
  --title "Acme QBR Q2 2025" \
  --values-file values.json)

NEW_ID=$(echo $RESULT | jq -r '.new_presentation_id')

# 3. Export as PDF
slides-agent export pdf --presentation-id $NEW_ID --output ./acme-qbr-q2-2025.pdf
```

### Workflow 3: Bulk Notes Update

```bash
PRES_ID="abc123"

# Get all slide IDs
SLIDE_IDS=$(slides-agent slide list --presentation-id $PRES_ID | jq -r '[.slides[].slide_id] | @tsv')

# Build operations for notes
python3 -c "
import json, sys
slide_ids = sys.argv[1].split()
notes = ['Opening remarks', 'Key metrics', 'Roadmap overview', 'Q&A']
ops = [{'type': 'set_notes', 'presentation_id': '$PRES_ID', 'slide_id': sid, 'text': notes[i % len(notes)]} for i, sid in enumerate(slide_ids)]
print(json.dumps(ops, indent=2))
" "$SLIDE_IDS" > notes_ops.json

# Plan and apply
slides-agent patch plan --presentation-id $PRES_ID --operations-file notes_ops.json > plan.json
slides-agent patch apply --plan-file plan.json
```

---

## Output Format

Every command returns JSON to stdout.

### Success Envelope (mutating commands)

```json
{
  "ok": true,
  "presentation_id": "abc123",
  "applied_operations": [
    {
      "type": "update_text",
      "slide_id": "g1a2b3",
      "element_id": "title_1",
      "detail": {}
    }
  ],
  "warnings": [],
  "errors": []
}
```

### Dry-Run Envelope

```json
{
  "ok": true,
  "dry_run": true,
  "presentation_id": "abc123",
  "would_apply": [
    {"deleteText": {"objectId": "title_1", "textRange": {"type": "ALL"}}},
    {"insertText": {"objectId": "title_1", "insertionIndex": 0, "text": "New Title"}}
  ],
  "warnings": [],
  "errors": []
}
```

---

## Error Model

All errors return a structured JSON object with a stable `error_code`:

```json
{
  "ok": false,
  "error_code": "not_found",
  "detail": "Slide 'g99x' not found in presentation 'abc123'.",
  "hint": "Run `slides-agent slide list` to get valid slide IDs.",
  "field": null,
  "raw": null
}
```

### Error Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `auth_error` | OAuth failure | Token expired, wrong scopes, not logged in |
| `not_found` | Resource doesn't exist | Wrong presentation/slide/element ID |
| `invalid_reference` | ID wrong type | Targeting an image with `text set` |
| `validation_error` | Bad input | Invalid JSON, missing required field, wrong format |
| `unsupported_operation` | Not supported | Feature not in MVP |
| `api_error` | Google API error | Unexpected API rejection |
| `rate_limited` | Quota exceeded | Too many requests |
| `conflict` | Concurrent modification | Presentation edited simultaneously |
| `io_error` | File I/O failure | File not found, permission denied |

---

## Safety Features

| Feature | Description |
|---------|-------------|
| `--dry-run` | All mutating commands support this. Returns `would_apply` with API requests instead of applying them. |
| `--force` | Required on destructive operations (e.g., `slide delete`) to skip confirmation in non-interactive mode. |
| `--no-input` compatible | No hidden prompts by default. Use `--force` for automation. |
| Plan/apply workflow | `patch plan` validates all IDs before `patch apply` mutates anything. |
| Loud failures | Ambiguous selectors fail with `not_found` or `invalid_reference` rather than guessing. |
| Token cache | OAuth tokens are cached locally and never logged or printed. |

---

## JSON Schema Reference

Get JSON schemas for any input or output type:

```bash
# List all schemas
slides-agent schema list

# Get a schema
slides-agent schema show presentation > presentation-schema.json
slides-agent schema show patch-plan > patch-plan-schema.json
slides-agent schema show error > error-schema.json
```

Use schemas for:
- Validating your operations files before running `patch plan`
- Generating type definitions in your agent code
- Documentation and API contracts

---

## Development

### Setup

```bash
# Clone and install in dev mode
git clone <repo>
cd slides-goog
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/ -v
pytest tests/ --cov=slides_agent --cov-report=html
```

Tests use mocked Google API responses — no real credentials required.

### Project Structure

```
src/slides_agent/
├── main.py              # Root Typer app
├── core/
│   ├── auth.py          # OAuth2 flow and credential storage
│   ├── api.py           # Google Slides and Drive API clients
│   ├── models.py        # Shared Pydantic v2 models
│   ├── parser.py        # Google API response → Pydantic model parsers
│   ├── output.py        # JSON output helpers
│   └── errors.py        # Structured error model
├── commands/
│   ├── auth.py          # `slides-agent auth *`
│   ├── deck.py          # `slides-agent deck *`
│   ├── slide.py         # `slides-agent slide *`
│   ├── element.py       # `slides-agent element *`
│   ├── text.py          # `slides-agent text *`
│   ├── notes.py         # `slides-agent notes *`
│   ├── image.py         # `slides-agent image *`
│   ├── theme.py         # `slides-agent theme *`
│   ├── template.py      # `slides-agent template *`
│   ├── patch.py         # `slides-agent patch *`
│   ├── export.py        # `slides-agent export *`
│   └── schema.py        # `slides-agent schema *`
└── schemas/
    ├── deck.py          # DeckInspectOutput, DeckDuplicateOutput
    ├── slide.py         # SlideListOutput, SlideMutationOutput
    ├── patch.py         # PatchPlan, PatchApplyReport, operation types
    └── theme.py         # ThemeApplyOutput, ThemeListOutput
```

### Adding a New Command

1. Add a function to the relevant file in `commands/`
2. Add Pydantic output schema to `schemas/` if needed
3. Register with `@app.command("command-name")`
4. Add `--examples` and `--schema` flags
5. Write tests in `tests/test_<module>.py`

### Lint

```bash
ruff check src/ tests/
ruff format src/ tests/
```
