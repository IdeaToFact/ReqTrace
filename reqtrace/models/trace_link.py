# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Trace link and review models for ReqTrace.
Provides tamper-evident linking and event-sourced human review tracking.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, Field, model_validator


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    STALE_REVIEW = "stale_review"
    WAIVED_ANALYSIS = "waived_analysis"
    # Backward compatibility aliases
    PENDING = "pending"
    MANUALLY_LINKED = "manually_linked"


class EvidenceStatus(str, Enum):
    PASSING = "passing"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNEXECUTED = "unexecuted"
    ORPHAN = "orphan"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    LINKED_PASSING = "linked_passing"
    UNVERIFIED_GAP = "unverified_gap"


class LinkConfidence(str, Enum):
    EXPLICIT_TAG = "explicit_tag"   # Explicit code annotation + confirmed assertion
    HIGH = "high"                   # Strong semantic match + assertion (>= 0.85)
    MEDIUM = "medium"               # Plausible match, human confirmation needed (0.60 - 0.85)
    LOW = "low"                     # Speculative match (< 0.60)
    # Backward compatibility alias
    VERIFIED = "explicit_tag"


class ReviewEvent(BaseModel):
    """
    Discrete, per-event record in .reqtrace/reviews.jsonl.
    Enables Git 3-way conflict-free mergeability across distributed engineering labs.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    req_id: str
    test_id: Optional[str] = None   # None for requirement-level waivers (e.g. analysis/inspection)
    status: ReviewStatus
    reviewed_by: str
    identity_verified: bool = False
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    comment: Optional[str] = None
    reference_doc: Optional[str] = None  # e.g. "DOC-STRUCTURAL-FEA-01"
    req_sha256_at_review: Optional[str] = None
    req_content_hash: Optional[str] = None
    test_content_hash: Optional[str] = None
    canon_version: int = 1
    schema_version: int = 1


class TraceLink(BaseModel):
    req_id: str
    test_id: str
    confidence: LinkConfidence
    confidence_score: float
    evidence_span: str              # Exact snippet of code/assertion grounding the link
    file_offset: Tuple[int, int]    # (start_char, end_char) in target test file
    justification: str              # Model rationale or deterministic rule citation

    # Audit & Review Persistence Overlay
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewed_by: Optional[str] = None
    review_comment: Optional[str] = None
    review_timestamp: Optional[str] = None

    # Delta & Execution Validation
    is_candidate: bool = False      # True if fuzzy match and not human approved
    is_stale: bool = False          # True if requirement text/hash changed since review
    is_execution_stale: bool = False # True if test file modified after JUnit report
    is_verified: bool = False       # True if linked test passed execution
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED_GAP
    audit_hash: str = ""

    # Match Provenance (for Candidate Review Queue)
    match_strategy: Optional[str] = None  # "explicit_tag", "rapidfuzz", "bm25", "fastembed", "hybrid"
    match_reason: Optional[str] = None

    @model_validator(mode="after")
    def compute_derived_fields(self) -> "TraceLink":
        # Determine candidate status (fuzzy matches without human approval/waiver earn 0 credit)
        is_fuzzy = self.confidence in (LinkConfidence.HIGH, LinkConfidence.MEDIUM, LinkConfidence.LOW)
        self.is_candidate = is_fuzzy and (self.review_status not in (ReviewStatus.APPROVED, ReviewStatus.WAIVED_ANALYSIS))

        # Derive link verification status
        if self.review_status == ReviewStatus.REJECTED or self.is_candidate:
            self.verification_status = VerificationStatus.UNVERIFIED_GAP
        elif self.is_verified and self.review_status in (ReviewStatus.APPROVED, ReviewStatus.WAIVED_ANALYSIS) and not self.is_stale and not self.is_execution_stale:
            self.verification_status = VerificationStatus.VERIFIED
        elif self.is_verified and self.review_status in (ReviewStatus.UNREVIEWED, ReviewStatus.PENDING) and not self.is_stale and not self.is_execution_stale:
            self.verification_status = VerificationStatus.LINKED_PASSING
        else:
            self.verification_status = VerificationStatus.UNVERIFIED_GAP

        if not self.audit_hash:
            content = f"{self.req_id}|{self.test_id}|{self.confidence.value}|{self.confidence_score:.4f}|{self.evidence_span}|{self.review_status.value}|{self.is_stale}|{self.is_verified}"
            self.audit_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return self
