# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit tests for CLI review subcommands.
"""

from pathlib import Path
from typer.testing import CliRunner
from reqtrace.cli import app
from reqtrace.analysis.review_store import ReviewStore
from reqtrace.models.trace_link import ReviewStatus

runner = CliRunner()


def test_cli_review_approve_and_reject(tmp_path: Path, monkeypatch) -> None:
    # Use temporary reviews file
    temp_reviews = tmp_path / "reviews.jsonl"
    monkeypatch.setattr("reqtrace.analysis.review_store.ReviewStore.__init__", lambda self: setattr(self, "store_path", temp_reviews))

    # 1. Approve
    res_approve = runner.invoke(app, [
        "review", "approve", "REQ-NAV-0104", "test_nav.py::test_gps_loss",
        "--by", "alice_der", "--comment", "Hardware-in-the-loop verified",
    ])
    assert res_approve.exit_code == 0
    assert "APPROVED" in res_approve.output
    assert "alice_der" in res_approve.output

    # Verify written to store
    store = ReviewStore()
    latest = store.get_latest_reviews()
    assert ("REQ-NAV-0104", "test_nav.py::test_gps_loss") in latest
    assert latest[("REQ-NAV-0104", "test_nav.py::test_gps_loss")].status == ReviewStatus.APPROVED

    # 2. Reject another
    res_reject = runner.invoke(app, [
        "review", "reject", "REQ-PWR-001", "test_pwr.py::test_mock",
        "--by", "bob_qa", "--comment", "Assertion only tests mocked flag",
    ])
    assert res_reject.exit_code == 0
    assert "REJECTED" in res_reject.output

    # 3. List reviews
    res_list = runner.invoke(app, ["review", "list"])
    assert res_list.exit_code == 0
    assert "REQ-NAV-0104" in res_list.output
    assert "REQ-PWR-001" in res_list.output
    assert "APPROVED" in res_list.output
    assert "REJECTED" in res_list.output
