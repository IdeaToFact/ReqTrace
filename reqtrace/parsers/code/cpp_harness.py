# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
C / C++ GoogleTest and Custom Test Harness Parser for ReqTrace.
Extracts test macros (TEST, TEST_F, custom macros), assertion macros (ASSERT_*, EXPECT_*),
and requirement tag comments from C and C++ source files.
Configurable via reqtrace.toml for MISRA C/C++ safety-critical environments.
"""

import re
from pathlib import Path
from typing import List, Optional, Set
from reqtrace.config import CppParserConfig, load_config
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus


class CppHarnessParser:
    # Regex to capture requirement references in C/C++ comments:
    # e.g., // Covers: REQ-NAV-0104, /* Req: SYS-001 */
    _REQ_ID_RE = re.compile(
        r"\b((?:REQ|SYS|SRS|HLR|LLR|SPEC|SOW|HW|SW|TR|TC|TEST)-[A-Z0-9_-]+|[A-Z]{2,10}-[A-Z0-9]*\d[A-Z0-9]*)\b",
        re.IGNORECASE,
    )

    def __init__(self, config: Optional[CppParserConfig] = None) -> None:
        self.config = config or load_config().parsers.cpp
        # Build regex for test macros: e.g. \b(TEST|TEST_F|MY_FLIGHT_TEST)\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)
        macro_pattern = "|".join(re.escape(m) for m in self.config.test_macro_names)
        self._test_macro_re = re.compile(
            rf"\b({macro_pattern})\s*\(\s*([A-Za-z0-9_]+)\s*(?:,\s*([A-Za-z0-9_]+))?\s*\)"
        )
        # Build regex for assert macros: e.g. \b(ASSERT_EQ|EXPECT_TRUE|CHECK_BOUNDS)\s*\(
        assert_pattern = "|".join(re.escape(a) for a in self.config.assert_macro_names)
        self._assert_macro_re = re.compile(rf"\b({assert_pattern})\s*\(")

    def parse_file(self, file_path: Path | str) -> List[TestArtifact]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"C/C++ test file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return []

        artifacts: List[TestArtifact] = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]
            match = self._test_macro_re.search(line)
            if match:
                macro_name = match.group(1)
                suite_name = match.group(2)
                case_name = match.group(3) or ""
                test_name = f"{suite_name}.{case_name}" if case_name else suite_name
                test_id = f"{path.name}::{test_name}"

                line_start = i + 1

                # Look backwards for doc comments / tags (up to 10 lines)
                declared_refs: Set[str] = set()
                lookback = max(0, i - 10)
                for prev_idx in range(lookback, i):
                    prev_line = lines[prev_idx]
                    if any(c in prev_line for c in ["//", "/*", "*"]):
                        for m in self._REQ_ID_RE.findall(prev_line):
                            declared_refs.add(m.upper())

                # Find the function block { ... } and assertions
                body_lines: List[str] = []
                brace_depth = 0
                started_block = False
                j = i

                while j < n:
                    cur_line = lines[j]
                    body_lines.append(cur_line)

                    # Look for tags inside comments within test body
                    if "//" in cur_line or "/*" in cur_line:
                        for m in self._REQ_ID_RE.findall(cur_line):
                            declared_refs.add(m.upper())

                    brace_depth += cur_line.count("{") - cur_line.count("}")
                    if "{" in cur_line:
                        started_block = True

                    if started_block and brace_depth <= 0:
                        break
                    j += 1

                line_end = j + 1
                body_text = "".join(body_lines)
                assertions = self._extract_assertions(body_lines)

                artifact = TestArtifact(
                    id=test_id,
                    file_path=str(path).replace("\\", "/"),
                    line_start=line_start,
                    line_end=line_end,
                    framework="gtest",
                    declared_req_refs=sorted(list(declared_refs)),
                    assertion_statements=assertions,
                    execution_status=TestExecutionStatus.UNEXECUTED,
                )
                artifacts.append(artifact)
                i = j + 1
            else:
                i += 1

        return artifacts

    def parse_directory(self, dir_path: Path | str) -> List[TestArtifact]:
        path = Path(dir_path)
        if not path.is_dir():
            return self.parse_file(path)

        all_artifacts: List[TestArtifact] = []
        extensions = {".cpp", ".cc", ".cxx", ".c", ".h"}
        for p in path.rglob("*"):
            if p.suffix.lower() in extensions:
                if "test" in p.name.lower():
                    all_artifacts.extend(self.parse_file(p))

        return all_artifacts

    def _extract_assertions(self, lines: List[str]) -> List[str]:
        assertions: List[str] = []
        for line in lines:
            if self._assert_macro_re.search(line):
                # Clean line and remove trailing semicolons/comments
                clean = line.strip()
                if "//" in clean:
                    clean = clean.split("//")[0].strip()
                assertions.append(clean)
        return assertions

