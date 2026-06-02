"""Entry point: `uv run python -m assistant.audit ...` delega para a CLI."""

import sys

from assistant.audit.cli import main

if __name__ == "__main__":
    sys.exit(main())
