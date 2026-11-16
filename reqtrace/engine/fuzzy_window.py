# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Character-exact fuzzy window alignment for ReqTrace.
Matches requirement text snippets against test functions and code assertions.
Uses RapidFuzz when available with fallback to difflib.
"""

from typing import Tuple

try:
    from rapidfuzz import fuzz
    def fuzzy_ratio(s1: str, s2: str) -> float:
        return fuzz.ratio(s1.lower(), s2.lower()) / 100.0
except ImportError:
    from difflib import SequenceMatcher
    def fuzzy_ratio(s1: str, s2: str) -> float:
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


class FuzzyWindowAligner:
    @staticmethod
    def match_score(query: str, target: str) -> float:
        """Calculates normalized similarity ratio (0.0 to 1.0)."""
        if not query or not target:
            return 0.0
        return fuzzy_ratio(query, target)

