"""Shared setup for the backend test suite.

The validators read repository files (compose configs, OAI .conf files) relative
to ``DASHBOARD_REPO_ROOT``. Default it to the actual repository root so
``pytest`` works from any working directory without extra environment setup.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("DASHBOARD_REPO_ROOT", str(REPO_ROOT))
