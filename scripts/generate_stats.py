#!/usr/bin/env python3
"""Generate the two profile statistics cards (contributions and languages).

Run from the repository root::

    STATS_TOKEN=... python scripts/generate_stats.py

See ``docs/stats.md`` for the exact token requirements and the limitations of
the generated data.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stats_cli import main  # noqa: E402  (path shim has to run first)

if __name__ == "__main__":
    raise SystemExit(main())
