"""Entry point for ``python -m behave_trace``."""

from __future__ import annotations

import sys

from behave_trace.cli.app import main

if __name__ == "__main__":
    sys.exit(main())
