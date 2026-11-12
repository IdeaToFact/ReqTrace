# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
JUnit XML and xUnit Execution Report Parser.
Extracts test verdicts (PASSED, FAILED, SKIPPED) and execution durations
to power Live Traceability.
"""

from pathlib import Path
from typing import Dict, List, Optional
try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
from pydantic import BaseModel

from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus


class JUnitTestCaseResult(BaseModel):
    classname: str
    name: str
    status: TestExecutionStatus
    time_sec: float = 0.0
    failure_message: Optional[str] = None


class JUnitParser:
    def parse(self, file_path: Path | str) -> Dict[str, JUnitTestCaseResult]:
        """
        Parses a JUnit XML file and returns a dictionary of test case results.
        Keyed by both simple test name and classname::name for robust lookup.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"JUnit report not found: {path}")

        tree = ET.parse(str(path))
        root = tree.getroot()

        results: Dict[str, JUnitTestCaseResult] = {}

        for tc in root.iter("testcase"):
            name = tc.attrib.get("name", "").strip()
            classname = tc.attrib.get("classname", "").strip()
            time_str = tc.attrib.get("time", "0.0")
            try:
                time_sec = float(time_str)
            except ValueError:
                time_sec = 0.0

            # Determine verdict
            status = TestExecutionStatus.PASSED
            failure_msg = None

            failure_node = tc.find("failure")
            error_node = tc.find("error")
            skipped_node = tc.find("skipped")

            if failure_node is not None:
                status = TestExecutionStatus.FAILED
                failure_msg = failure_node.attrib.get("message") or (failure_node.text or "").strip()
            elif error_node is not None:
                status = TestExecutionStatus.FAILED
                failure_msg = error_node.attrib.get("message") or (error_node.text or "").strip()
            elif skipped_node is not None:
                status = TestExecutionStatus.SKIPPED
                failure_msg = skipped_node.attrib.get("message") or "Skipped"

            res = JUnitTestCaseResult(
                classname=classname,
                name=name,
                status=status,
                time_sec=time_sec,
                failure_message=failure_msg,
            )

            # Store under multiple keys to facilitate lookup
            # 1. Exact name: "test_gps_loss"
            if name:
                results[name] = res
            # 2. Classname::name: "tests.test_nav::test_gps_loss"
            if classname and name:
                results[f"{classname}::{name}"] = res
                # 3. File path style if classname looks like a module path: "test_nav.py::test_gps_loss"
                file_candidate = classname.split(".")[-1] + ".py"
                results[f"{file_candidate}::{name}"] = res

        return results

    def attach_verdicts(
        self, artifacts: List[TestArtifact], junit_file_path: Path | str
    ) -> List[TestArtifact]:
        """
        Attaches execution verdicts to an existing list of TestArtifacts.
        """
        results = self.parse(junit_file_path)

        for art in artifacts:
            # Try matching art.id (e.g. "test_nav.py::test_gps_loss")
            res = results.get(art.id)
            if not res:
                # Try matching by function name alone
                func_name = art.id.split("::")[-1]
                res = results.get(func_name)

            if res:
                art.execution_status = res.status
                art.execution_time_sec = res.time_sec

        return artifacts
