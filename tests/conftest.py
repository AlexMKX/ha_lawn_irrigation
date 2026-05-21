"""Pytest configuration - routes to unit or e2e conftest based on AUTOQA_MODE."""
import os
mode = os.environ.get("AUTOQA_MODE", "unit")
if mode == "e2e":
    from tests.conftest_e2e import *  # noqa: F401, F403
else:
    from tests.conftest_unit import *  # noqa: F401, F403
