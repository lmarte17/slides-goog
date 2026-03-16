"""Google OAuth2 authentication helpers for slides-agent.

Credentials flow
----------------
1. User runs `slides-agent auth login --credentials-file /path/to/client_secret.json`
2. The OAuth2 browser flow opens; user grants access.
3. Token is cached at ~/.config/slides-agent/token.json (or SLIDES_AGENT_TOKEN_FILE).
4. Subsequent commands load the cached token, refreshing automatically.

Environment variables
---------------------
SLIDES_AGENT_CREDENTIALS   Path to client_secret.json (overrides --credentials-file).
SLIDES_AGENT_TOKEN_FILE    Path to token cache file (default: ~/.config/slides-agent/token.json).

Required OAuth2 scopes
----------------------
https://www.googleapis.com/auth/presentations
https://www.googleapis.com/auth/drive
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

_DEFAULT_TOKEN_DIR = Path.home() / ".config" / "slides-agent"
_DEFAULT_TOKEN_FILE = _DEFAULT_TOKEN_DIR / "token.json"


def token_path() -> Path:
    """Return the resolved path for the token cache file."""
    env = os.environ.get("SLIDES_AGENT_TOKEN_FILE")
    return Path(env) if env else _DEFAULT_TOKEN_FILE


def credentials_path_from_env() -> Path | None:
    """Return credentials file path from env var, or None."""
    env = os.environ.get("SLIDES_AGENT_CREDENTIALS")
    return Path(env) if env else None


def load_credentials() -> Any:
    """Load and optionally refresh cached OAuth2 credentials.

    Returns
    -------
    google.oauth2.credentials.Credentials or None if no token exists.
    """
    from google.oauth2.credentials import Credentials  # type: ignore[import]
    from google.auth.transport.requests import Request  # type: ignore[import]

    tp = token_path()
    if not tp.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(tp), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(creds)

    return creds if creds and creds.valid else None


def run_login_flow(credentials_file: Path) -> Any:
    """Run the OAuth2 installed-app flow and cache the resulting token.

    Parameters
    ----------
    credentials_file:
        Path to the client_secret.json downloaded from Google Cloud Console.

    Returns
    -------
    google.oauth2.credentials.Credentials
    """
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import]

    if not credentials_file.exists():
        from .errors import AgentError, ErrorCode

        AgentError(
            error_code=ErrorCode.io_error,
            detail=f"Credentials file not found: {credentials_file}",
            hint=(
                "Download client_secret.json from Google Cloud Console → "
                "APIs & Services → Credentials and pass it with --credentials-file."
            ),
        ).emit()

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_credentials(creds)
    return creds


def _save_credentials(creds: Any) -> None:
    """Persist credentials to the token cache file."""
    tp = token_path()
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(creds.to_json())


def revoke_credentials() -> None:
    """Delete the cached token file."""
    tp = token_path()
    if tp.exists():
        tp.unlink()


def require_credentials(credentials_file: Path | None = None) -> Any:
    """Return valid credentials or exit with an auth_error.

    Checks the token cache first. If not found, exits with guidance to run
    `slides-agent auth login`.

    Parameters
    ----------
    credentials_file:
        Optional path override for the client_secret.json. Used only when
        triggering an automatic refresh that needs the client info.
    """
    creds = load_credentials()
    if creds is None:
        from .errors import AgentError, ErrorCode

        AgentError(
            error_code=ErrorCode.auth_error,
            detail="No valid credentials found.",
            hint=(
                "Run `slides-agent auth login --credentials-file /path/to/client_secret.json` "
                "to authenticate."
            ),
        ).emit()

    return creds


def credentials_status() -> dict[str, Any]:
    """Return a dict describing current credential state (for auth status command)."""
    tp = token_path()

    if not tp.exists():
        return {
            "authenticated": False,
            "token_file": str(tp),
            "token_exists": False,
            "scopes": SCOPES,
        }

    try:
        from google.oauth2.credentials import Credentials  # type: ignore[import]

        creds = Credentials.from_authorized_user_file(str(tp), SCOPES)
        return {
            "authenticated": creds.valid,
            "token_file": str(tp),
            "token_exists": True,
            "expired": creds.expired,
            "scopes": list(creds.scopes) if creds.scopes else SCOPES,
            "client_id": creds.client_id,
        }
    except Exception as exc:
        return {
            "authenticated": False,
            "token_file": str(tp),
            "token_exists": True,
            "error": str(exc),
        }
