"""
Minimal .env loader.

Deliberately not python-dotenv: this needs one small, dependency-free function,
and one fewer package to install is one fewer thing to go wrong when someone
sets the project up from requirements.txt.

Reads `backend/.env` if it exists. Real environment variables always win, so
exporting ANTHROPIC_API_KEY in the shell overrides the file.
"""

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env(path=None):
    """
    Load KEY=VALUE lines from a .env file into os.environ.

    Returns the list of names that were set. Never raises on a malformed file:
    a bad line is skipped rather than taking the server down at import time.
    """
    target = Path(path) if path else ENV_PATH

    if not target.is_file():
        return []

    applied = []

    try:
        raw = target.read_text(encoding="utf-8-sig")
    except OSError:
        return []

    for line in raw.splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        # Tolerate `export FOO=bar`, which is what people paste in.
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()

        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()

        if not name:
            continue

        # Strip one layer of matching quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        # A real environment variable beats the file.
        if name in os.environ and os.environ[name]:
            continue

        os.environ[name] = value
        applied.append(name)

    return applied
