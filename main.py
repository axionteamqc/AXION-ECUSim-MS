"""Convenience entrypoint for CLI runner."""

from __future__ import annotations

import sys

from ecusim_ms.cli_runner import main


if __name__ == "__main__":
    sys.exit(main())
