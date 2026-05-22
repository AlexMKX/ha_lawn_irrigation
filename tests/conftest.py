"""Pytest configuration - routes to unit or e2e conftest based on AUTOQA_MODE."""

import os
import sys
from pathlib import Path

# Ensure the tests directory is importable regardless of how pytest invokes conftest
sys.path.insert(0, str(Path(__file__).parent))

mode = os.environ.get("AUTOQA_MODE", "unit")
if mode == "e2e":
    from conftest_e2e import *  # noqa: F401, F403
else:
    from conftest_unit import *  # noqa: F401, F403
