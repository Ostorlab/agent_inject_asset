"""Pytest bootstrap.

Put the `agent/` directory on `sys.path` so tests import `agent` and
`providers` exactly as they resolve at runtime (`python /app/agent/agent.py`).
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "agent"))
