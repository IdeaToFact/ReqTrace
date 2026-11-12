# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for the event-sourced persistent ReviewStore.
"""

from pathlib import Path
from reqtrace.analysis.review_store import ReviewStore
from reqtrace.models.requirement import Requirement
from reqtrace.models.trace_link import (
    LinkConfidence,
    ReviewEvent,
    ReviewStatus,
    TraceLink,
)


def test_review_store_event_sourcing(tmp_path: Path) -> None:
    store_file = tmp_path / "reviews.jsonl"
    store = ReviewStore(store_path=store_file)

    # 1. Engineer A reviews and rejects link at 10:00
    event_1 = ReviewEvent(
        req_id="REQ-NAV-0104",
        test_id="test_gps_loss",
        status=ReviewStatus.REJECTED,
        reviewed_by="engineer_alice",
        comment="Assertion only checks mock flag, not dead-reckoning state",
        timestamp="2026-11-06T10:00:00Z",
        req_sha256_at_review="hash_v1",
    )
    store.append_event(event_1)

    # 2. Engineer B reviews and approves after test update at 11:30
    event_2 = ReviewEvent(
        req_id="REQ-NAV-0104",
        test_id="test_gps_loss",
        status=ReviewStatus.APPROVED,
        reviewed_by="der_bob",
        comment="Updated test assertions verified on HIL testbench",
        timestamp="2026-11-06T11:30:00Z",
        req_sha256_at_review="hash_v1",
    )
    store.append_event(event_2)

    # 3. Verify materialization (event_2 must win because it has later timestamp)
    latest = store.get_latest_reviews()
    assert len(latest) == 1
    assert latest[("REQ-NAV-0104", "test_gps_loss")].status == ReviewStatus.APPROVED
    assert latest[("REQ-NAV-0104", "test_gps_loss")].reviewed_by == "der_bob"


def test_review_store_overlay_and_staleness_detection(tmp_path: Path) -> None:
    store_file = tmp_path / "reviews.jsonl"
    store = ReviewStore(store_path=store_file)

    # Review signed off against original requirement hash
    req_orig = Requirement(
        id="REQ-NAV-0104",
        title="GPS Loss",
        description="Switch to dead-reckoning within 200ms",
        source_file="spec.reqif",
    )

    event = ReviewEvent(
        req_id=req_orig.id,
        test_id="test_gps_loss",
        status=ReviewStatus.APPROVED,
        reviewed_by="der_bob",
        timestamp="2026-11-06T12:00:00Z",
        req_sha256_at_review=req_orig.sha256,
    )
    store.append_event(event)

    # Freshly computed candidate link
    link = TraceLink(
        req_id=req_orig.id,
        test_id="test_gps_loss",
        confidence=LinkConfidence.HIGH,
        confidence_score=0.91,
        evidence_span="assert mode == DeadReckoning",
        file_offset=(100, 130),
        justification="High semantic similarity",
    )

    # Case A: Requirement has NOT changed -> link is NOT stale
    links_a = store.apply_overlay([link.model_copy()], {req_orig.id: req_orig})
    assert links_a[0].review_status == ReviewStatus.APPROVED
    assert links_a[0].is_stale is False

    # Case B: Requirement text changed in Rev 2 (tightened to 100ms)
    req_rev2 = Requirement(
        id="REQ-NAV-0104",
        title="GPS Loss",
        description="Switch to dead-reckoning within 100ms",  # Changed parameter!
        source_file="spec.reqif",
    )
    assert req_rev2.sha256 != req_orig.sha256

    links_b = store.apply_overlay([link.model_copy()], {req_rev2.id: req_rev2})
    assert links_b[0].review_status == ReviewStatus.APPROVED
    assert links_b[0].is_stale is True  # Automatically flagged STALE!

