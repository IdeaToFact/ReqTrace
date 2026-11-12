# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for ReqTrace core Pydantic data contracts.
"""

from reqtrace.models.requirement import (
    Requirement,
    RequirementLevel,
    RequirementType,
    VerificationMethod,
)
from reqtrace.models.test_artifact import (
    TestArtifact,
    TestExecutionStatus,
)
from reqtrace.models.trace_link import (
    EvidenceStatus,
    LinkConfidence,
    ReviewEvent,
    ReviewStatus,
    TraceLink,
    VerificationStatus,
)


def test_requirement_creation_and_deterministic_sha256() -> None:
    req = Requirement(
        id="REQ-NAV-0104",
        title="GPS Loss Failsafe",
        description="The system shall switch to inertial dead-reckoning within 200ms of GPS loss.",
        is_normative=True,
        level=RequirementLevel.HIGH_LEVEL,
        source_file="specs/navigation.reqif",
        req_type=RequirementType.SAFETY,
        parent_ids=["SYS-REQ-002"],
    )

    assert req.id == "REQ-NAV-0104"
    assert req.is_normative is True
    assert req.level == RequirementLevel.HIGH_LEVEL
    assert len(req.sha256) == 64  # Valid SHA-256 hex string

    # Re-creating with same attributes must yield identical sha256
    req_duplicate = Requirement(
        id="REQ-NAV-0104",
        title="GPS Loss Failsafe",
        description="The system shall switch to inertial dead-reckoning within 200ms of GPS loss.",
        is_normative=True,
        level=RequirementLevel.HIGH_LEVEL,
        source_file="specs/navigation.reqif",
        req_type=RequirementType.SAFETY,
        parent_ids=["SYS-REQ-002"],
    )
    assert req.sha256 == req_duplicate.sha256

    # Modified description must change sha256
    req_modified = req.model_copy(update={"description": "Modified text"})
    # Recalculate hash on copy
    req_modified.sha256 = ""
    req_modified = req_modified.compute_sha256()
    assert req.sha256 != req_modified.sha256


def test_test_artifact_execution_status() -> None:
    test_art = TestArtifact(
        id="test_gps_loss_triggers_failsafe",
        file_path="tests/test_nav.py",
        line_start=45,
        line_end=62,
        framework="pytest",
        declared_req_refs=["REQ-NAV-0104"],
        assertion_statements=["assert nav.mode == NavMode.INERTIAL"],
        execution_status=TestExecutionStatus.PASSED,
        execution_time_sec=0.042,
    )

    assert test_art.execution_status == TestExecutionStatus.PASSED
    assert len(test_art.sha256) == 64


def test_trace_link_audit_hash_and_staleness() -> None:
    link = TraceLink(
        req_id="REQ-NAV-0104",
        test_id="test_gps_loss_triggers_failsafe",
        confidence=LinkConfidence.VERIFIED,
        confidence_score=0.98,
        evidence_span="assert nav.mode == NavMode.INERTIAL",
        file_offset=(1240, 1276),
        justification="Explicit @pytest.mark.req tag and affirmative assertion.",
        review_status=ReviewStatus.APPROVED,
        reviewed_by="auditor_lead",
        review_comment="DER sign-off confirmed",
        is_stale=False,
        is_verified=True,
    )

    assert link.review_status == ReviewStatus.APPROVED
    assert link.is_verified is True
    assert link.is_stale is False
    assert len(link.audit_hash) == 64
    assert link.verification_status == VerificationStatus.VERIFIED


def test_two_axis_verification_status_derivation() -> None:
    # 1. Passing test + Approved review => VERIFIED
    link_approved = TraceLink(
        req_id="REQ-01",
        test_id="test_01",
        confidence=LinkConfidence.EXPLICIT_TAG,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(0, 11),
        justification="Rule tag",
        is_verified=True,
        review_status=ReviewStatus.APPROVED,
    )
    assert link_approved.verification_status == VerificationStatus.VERIFIED

    # 2. Passing test + Unreviewed => LINKED_PASSING
    link_pending = TraceLink(
        req_id="REQ-01",
        test_id="test_01",
        confidence=LinkConfidence.EXPLICIT_TAG,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(0, 11),
        justification="Rule tag",
        is_verified=True,
        review_status=ReviewStatus.UNREVIEWED,
    )
    assert link_pending.verification_status == VerificationStatus.LINKED_PASSING

    # 3. Passing test + Rejected review => UNVERIFIED_GAP
    link_rejected = TraceLink(
        req_id="REQ-01",
        test_id="test_01",
        confidence=LinkConfidence.EXPLICIT_TAG,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(0, 11),
        justification="Rule tag",
        is_verified=True,
        review_status=ReviewStatus.REJECTED,
    )
    assert link_rejected.verification_status == VerificationStatus.UNVERIFIED_GAP

    # 4. Failing test + Approved review => UNVERIFIED_GAP (Execution failure overrides approval)
    link_failed = TraceLink(
        req_id="REQ-01",
        test_id="test_01",
        confidence=LinkConfidence.EXPLICIT_TAG,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(0, 11),
        justification="Rule tag",
        is_verified=False,
        review_status=ReviewStatus.APPROVED,
    )
    assert link_failed.verification_status == VerificationStatus.UNVERIFIED_GAP

    # 5. Passing test + Stale review => UNVERIFIED_GAP
    link_stale = TraceLink(
        req_id="REQ-01",
        test_id="test_01",
        confidence=LinkConfidence.EXPLICIT_TAG,
        confidence_score=1.0,
        evidence_span="assert True",
        file_offset=(0, 11),
        justification="Rule tag",
        is_verified=True,
        review_status=ReviewStatus.APPROVED,
        is_stale=True,
    )
    assert link_stale.verification_status == VerificationStatus.UNVERIFIED_GAP


def test_verification_method_and_waived_analysis() -> None:
    req = Requirement(
        id="REQ-ANALYSIS-01",
        title="Structural Stress Safety Margin",
        description="The fuselage wing spar shall withstand 150% limit load without permanent deformation.",
        level=RequirementLevel.HIGH_LEVEL,
        verification_method=VerificationMethod.ANALYSIS,
        source_file="specs/structures.reqif",
    )
    assert req.verification_method == VerificationMethod.ANALYSIS

    # Link with WAIVED_ANALYSIS
    link_waived = TraceLink(
        req_id=req.id,
        test_id="analysis::spar_finite_element_calc",
        confidence=LinkConfidence.HIGH,
        confidence_score=0.95,
        evidence_span="DOC-STRUCTURAL-FEA-REV-C",
        file_offset=(0, 24),
        justification="Verified by structural FEA stress simulation.",
        is_verified=True,
        review_status=ReviewStatus.WAIVED_ANALYSIS,
    )
    assert link_waived.verification_status == VerificationStatus.VERIFIED


def test_review_event_fields_and_git_merge_readiness() -> None:
    event = ReviewEvent(
        req_id="REQ-NAV-0104",
        test_id="tests/test_nav.py::test_gps_loss",
        status=ReviewStatus.APPROVED,
        reviewed_by="alice",
        comment="Confirmed by flight inspection",
        req_content_hash="abc123sha256",
        test_content_hash="def456sha256",
        canon_version=1,
        schema_version=1,
    )
    assert event.status == ReviewStatus.APPROVED
    assert event.identity_verified is False
    assert event.canon_version == 1
    assert event.schema_version == 1
    assert len(event.event_id) > 0

