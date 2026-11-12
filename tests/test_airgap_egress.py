# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Test Zero-Egress Air-Gap Compliance for ReqTrace.
Guarantees that all core commands execute 100% offline with zero outbound network egress.
"""

import socket
import urllib.request
from pathlib import Path
import pytest
from typer.testing import CliRunner

from reqtrace.cli import app


class AirGapViolationError(PermissionError):
    """Raised whenever outbound network egress is attempted."""
    pass


@pytest.fixture
def airgap_socket_guard(monkeypatch):
    """Blocks any external network socket connection during test execution."""
    real_connect = socket.socket.connect

    def blocked_connect(self, address):
        host, *port = address if isinstance(address, tuple) else (str(address),)
        host_str = str(host).lower().strip("[]")
        if host_str not in {"127.0.0.1", "localhost", "::1"}:
            raise AirGapViolationError(
                f"Air-gap egress violation detected! Attempted outbound connection to: {address}"
            )
        return real_connect(self, address)

    def blocked_urlopen(url, *args, **kwargs):
        raise AirGapViolationError(f"Air-gap egress violation detected! Attempted HTTP call: {url}")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)
    return True


SAMPLE_REQIF = """<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">
  <CORE-CONTENT>
    <REQ-IF-CONTENT>
      <SPEC-TYPES>
        <SPEC-OBJECT-TYPE IDENTIFIER="type_req" LONG-NAME="Requirement Type">
          <SPEC-ATTRIBUTES>
            <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="attr_id" LONG-NAME="ReqIF.ForeignID"/>
            <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="attr_text" LONG-NAME="ReqIF.Text"/>
          </SPEC-ATTRIBUTES>
        </SPEC-OBJECT-TYPE>
      </SPEC-TYPES>
      <SPEC-OBJECTS>
        <SPEC-OBJECT IDENTIFIER="obj_001">
          <VALUES>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="The navigation system shall acquire GPS within 2.5s">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>attr_text</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
            <ATTRIBUTE-VALUE-STRING THE-VALUE="REQ-NAV-001">
              <DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>attr_id</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>
            </ATTRIBUTE-VALUE-STRING>
          </VALUES>
          <TYPE><SPEC-OBJECT-TYPE-REF>type_req</SPEC-OBJECT-TYPE-REF></TYPE>
        </SPEC-OBJECT>
      </SPEC-OBJECTS>
    </REQ-IF-CONTENT>
  </CORE-CONTENT>
</REQ-IF>
"""

SAMPLE_TEST = """
import pytest

@pytest.mark.req("REQ-NAV-001")
def test_nav_gps_acquisition():
    assert acquire_gps() < 2.5
"""

SAMPLE_JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="nav_tests" tests="1" failures="0" errors="0" skipped="0">
  <testcase classname="test_nav" name="test_nav_gps_acquisition" time="0.042"/>
</testsuite>
"""


def test_core_pipeline_zero_egress(airgap_socket_guard, tmp_path: Path):
    """Verifies that the entire pipeline runs end-to-end with zero outbound network calls."""
    runner = CliRunner()

    spec_file = tmp_path / "spec.reqif"
    spec_file.write_text(SAMPLE_REQIF, encoding="utf-8")

    test_dir = tmp_path / "test_suite"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_nav.py").write_text(SAMPLE_TEST, encoding="utf-8")

    junit_file = tmp_path / "junit.xml"
    junit_file.write_text(SAMPLE_JUNIT, encoding="utf-8")

    reqs_json = tmp_path / "requirements.json"
    tests_json = tmp_path / "tests.json"
    matrix_csv = tmp_path / "trace_matrix.csv"
    html_out = tmp_path / "rtm_report.html"
    exported_reqif = tmp_path / "exported.reqif"

    # 1. Ingest
    res_ingest = runner.invoke(app, ["ingest", str(spec_file), "--type", "reqif", "--out", str(reqs_json)])
    assert res_ingest.exit_code == 0

    # 2. Scan
    res_scan = runner.invoke(app, ["scan", str(test_dir), "--junit", str(junit_file), "--out", str(tests_json)])
    assert res_scan.exit_code == 0

    # 3. Link
    res_link = runner.invoke(app, ["link", "--reqs", str(reqs_json), "--tests", str(tests_json), "--out", str(matrix_csv)])
    assert res_link.exit_code == 0

    # 4. Check
    res_check = runner.invoke(app, ["check", "--reqs", str(reqs_json), "--tests", str(tests_json), "--min-coverage", "50.0"])
    assert res_check.exit_code == 0

    # 5. Audit Summary
    res_summary = runner.invoke(app, ["audit-summary", "--reqs", str(reqs_json), "--tests", str(tests_json)])
    assert res_summary.exit_code == 0

    # 6. Report
    res_report = runner.invoke(app, ["report", "--reqs", str(reqs_json), "--tests", str(tests_json), "--out", str(html_out)])
    assert res_report.exit_code == 0

    # 7. Export ReqIF
    res_export = runner.invoke(app, ["export-reqif", "--reqs", str(reqs_json), "--tests", str(tests_json), "--out", str(exported_reqif)])
    assert res_export.exit_code == 0

    assert html_out.exists()
    assert exported_reqif.exists()
