# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Pytest configuration and test fixtures for ReqTrace.
"""

import sys
from pathlib import Path
import pytest

# Ensure reqtrace is importable from project root
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

