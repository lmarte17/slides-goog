"""auth command group — manage Google OAuth2 credentials.

Commands
--------
slides-agent auth login     Run the OAuth2 browser flow and cache a token.
slides-agent auth status    Check whether current credentials are valid.
slides-agent auth logout    Delete the cached token.

How credentials work
--------------------
1. Download client_secret.json from Google Cloud Console → APIs & Services → Credentials.
2. Run `slides-agent auth login --credentials-file /path/to/client_secret.json`.
3. Your browser opens; grant access to the requested scopes.
4. The token is cached at ~/.config/slides-agent/token.json.
5. All subsequent commands use the cached token automatically.

Environment variables
---------------------
SLIDES_AGENT_CREDENTIALS    Path to client_secret.json (overrides --credentials-file).
SLIDES_AGENT_TOKEN_FILE     Override the default token cache path.

Required Google Cloud scopes
-----------------------------
https://www.googleapis.com/auth/presentations
https://www.googleapis.com/auth/drive

JSON output shape (auth status)
--------------------------------
{
  "ok": true,
  "authenticated": true,
  "token_file": "/Users/you/.config/slides-agent/token.json",
  "token_exists": true,
  "expired": false,
  "scopes": ["https://www.googleapis.com/auth/presentations", ...],
  "client_id": "..."
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from slides_agent.core import auth as auth_core
from slides_agent.core.output import emit

app = typer.Typer(
    name="auth",
    help="Manage Google OAuth2 credentials for slides-agent.",
    no_args_is_help=True,
)

_EXAMPLES = """
# Check current auth state:
slides-agent auth status

# Login using a credentials file:
slides-agent auth login --credentials-file ~/Downloads/client_secret.json

# Login using an environment variable:
SLIDES_AGENT_CREDENTIALS=~/Downloads/client_secret.json slides-agent auth login

# Logout (revoke cached token):
slides-agent auth logout
"""


@app.command("login")
def login(
    credentials_file: Annotated[
        Optional[Path],
        typer.Option(
            "--credentials-file",
            "-c",
            help=(
                "Path to client_secret.json from Google Cloud Console. "
                "Falls back to SLIDES_AGENT_CREDENTIALS env var."
            ),
            envvar="SLIDES_AGENT_CREDENTIALS",
        ),
    ] = None,
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Run the Google OAuth2 browser flow and cache credentials.

    \b
    WHAT IT DOES
    Launches a local OAuth2 server, opens your browser, and prompts you to
    grant the application access to Google Slides and Drive. The resulting
    token is cached locally so you do not need to re-authenticate.

    \b
    REQUIRED
    A client_secret.json file from the Google Cloud Console. The file must
    be of type "OAuth2 client ID" for a "Desktop app".

    \b
    HOW TO GET client_secret.json
    1. Go to https://console.cloud.google.com
    2. Select your project → APIs & Services → Credentials
    3. Create or select an OAuth 2.0 Client ID (type: Desktop app)
    4. Download the JSON file

    \b
    FAILURE MODES
    - io_error: credentials file not found or malformed.
    - auth_error: Google rejected the OAuth flow.
    """
    if examples:
        print(_EXAMPLES)
        raise typer.Exit()

    creds_path = credentials_file or auth_core.credentials_path_from_env()
    if not creds_path:
        from slides_agent.core.errors import AgentError, ErrorCode

        AgentError(
            error_code=ErrorCode.io_error,
            detail="No credentials file specified.",
            hint=(
                "Provide --credentials-file /path/to/client_secret.json "
                "or set SLIDES_AGENT_CREDENTIALS."
            ),
        ).emit(pretty=pretty)

    creds = auth_core.run_login_flow(creds_path)  # type: ignore[arg-type]
    result = {
        "ok": True,
        "authenticated": creds.valid,
        "token_file": str(auth_core.token_path()),
        "scopes": SCOPES if not creds.scopes else list(creds.scopes),
        "message": "Login successful. Token cached.",
    }
    emit(result, pretty=pretty)


@app.command("status")
def status(
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
    examples: Annotated[bool, typer.Option("--examples", help="Show usage examples and exit.")] = False,
) -> None:
    """Check whether current credentials are valid.

    \b
    WHAT IT DOES
    Reads the cached token file and reports its validity. Does NOT open a
    browser or make API calls — safe to call in CI or non-interactive shells.

    \b
    OUTPUT FIELDS
    authenticated   true if a valid, non-expired token exists.
    token_file      Path where the token is cached.
    token_exists    true if the token file is present on disk.
    expired         true if the token has expired (can be refreshed).
    scopes          List of granted OAuth2 scopes.
    client_id       The OAuth2 client ID from the credentials file.

    \b
    FAILURE MODES
    - auth_error: Token file is corrupt or could not be parsed.
    """
    if examples:
        print(_EXAMPLES)
        raise typer.Exit()

    result = auth_core.credentials_status()
    result["ok"] = True
    emit(result, pretty=pretty)


@app.command("logout")
def logout(
    pretty: Annotated[bool, typer.Option("--pretty", help="Pretty-print JSON output.")] = False,
) -> None:
    """Delete the cached token file.

    \b
    WHAT IT DOES
    Removes the token cache file. The next command requiring authentication
    will fail with auth_error until you run `auth login` again.

    \b
    THIS DOES NOT revoke the token on Google's servers. For full revocation,
    visit https://myaccount.google.com/permissions.
    """
    auth_core.revoke_credentials()
    emit({"ok": True, "message": "Token cache deleted. Run `auth login` to re-authenticate."}, pretty=pretty)


SCOPES = auth_core.SCOPES
