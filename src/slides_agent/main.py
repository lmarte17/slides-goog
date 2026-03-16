"""slides-agent — AI-first CLI for Google Slides.

Entry point for all command groups. Run `slides-agent --help` for an overview.

Quick start
-----------
1. Authenticate:
   slides-agent auth login --credentials-file /path/to/client_secret.json

2. Inspect a presentation:
   slides-agent deck inspect --presentation-id <id> --pretty

3. List slides:
   slides-agent slide list --presentation-id <id>

4. Replace template tokens:
   slides-agent text replace --presentation-id <id> --find '{{customer}}' --replace 'Acme'

5. Apply a patch plan:
   slides-agent patch plan --presentation-id <id> --operations-file ops.json > plan.json
   slides-agent patch apply --plan-file plan.json

Design principles
-----------------
- AI-first: all commands are non-interactive and JSON-first.
- Deterministic: stable IDs in all outputs.
- Inspectable: deep inspect before edits.
- Safe: --dry-run on all mutating commands.
- Verbose: --help, --examples, --schema on every command.
"""

from __future__ import annotations

import typer

from slides_agent.commands import (
    auth,
    deck,
    element,
    export,
    image,
    notes,
    patch,
    schema,
    slide,
    template,
    text,
    theme,
)

app = typer.Typer(
    name="slides-agent",
    help=(
        "AI-first CLI for Google Slides. "
        "Every command is non-interactive and returns JSON.\n\n"
        "Run any command with --help for detailed documentation.\n"
        "Run any command with --examples to see realistic usage examples.\n"
        "Run any command with --schema to see the JSON schema for inputs/outputs."
    ),
    no_args_is_help=True,
    rich_markup_mode="markdown",
)

# Register all command groups
app.add_typer(auth.app, name="auth")
app.add_typer(deck.app, name="deck")
app.add_typer(slide.app, name="slide")
app.add_typer(element.app, name="element")
app.add_typer(text.app, name="text")
app.add_typer(image.app, name="image")
app.add_typer(notes.app, name="notes")
app.add_typer(theme.app, name="theme")
app.add_typer(template.app, name="template")
app.add_typer(patch.app, name="patch")
app.add_typer(export.app, name="export")
app.add_typer(schema.app, name="schema")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit."),
) -> None:
    """slides-agent: AI-first CLI for Google Slides."""
    if version:
        from slides_agent import __version__
        typer.echo(f"slides-agent {__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
