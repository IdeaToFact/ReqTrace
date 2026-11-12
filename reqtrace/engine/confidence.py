# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Confidence scoring and calibration rules for ReqTrace.
Assigns deterministic confidence levels:
- VERIFIED: Explicit tag in docstring/decorator + confirmed assertion (1.0)
- HIGH: Fuzzy match >= 0.85
- MEDIUM: Fuzzy match >= 0.60
- LOW: Sub-threshold candidate (< 0.60)
"""

from reqtrace.models.trace_link import LinkConfidence


class ConfidenceCalibrator:
    def __init__(self, high_threshold: float = 0.85, medium_threshold: float = 0.60) -> None:
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold

    def calibrate(self, score: float, is_explicit_tag: bool = False) -> LinkConfidence:
        if is_explicit_tag:
            return LinkConfidence.VERIFIED
        if score >= self.high_threshold:
            return LinkConfidence.HIGH
        if score >= self.medium_threshold:
            return LinkConfidence.MEDIUM
        return LinkConfidence.LOW

