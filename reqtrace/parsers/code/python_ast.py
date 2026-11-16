# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Python and PyTest AST Parser.
Extracts test functions, assertion statements, line spans, and requirement tags
without executing test code.
"""

import ast
import re
from pathlib import Path
from typing import List, Set
from reqtrace.models.test_artifact import TestArtifact, TestExecutionStatus


class PythonASTParser:
    # Regex to capture requirement references in comments or docstrings:
    # Requires standard requirement prefix (REQ-, SYS-, SRS-, HLR-, LLR-) or at least one digit (e.g. NAV-01, SRS-42)
    # Avoids false positives on hyphenated English words like 'dead-reckoning' or 'safety-critical'.
    _REQ_ID_RE = re.compile(
        r"\b((?:REQ|SYS|SRS|HLR|LLR|SPEC|SOW|HW|SW|TR|TC|TEST)-[A-Z0-9_-]+|[A-Z]{2,10}-[A-Z0-9]*\d[A-Z0-9]*)\b",
        re.IGNORECASE,
    )

    def parse_file(self, file_path: Path | str) -> List[TestArtifact]:
        """
        Parses a single Python test file and extracts TestArtifact instances.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Python test file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            tree = ast.parse(source, filename=str(path))
        except Exception:
            return []

        artifacts: List[TestArtifact] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                if not self._is_test_function(node):
                    continue

                test_id = f"{path.name}::{node.name}"
                declared_refs = self._extract_requirement_references(node, source)
                assertions = self._extract_assertions(node)

                line_start = node.lineno
                line_end = getattr(node, "end_lineno", node.lineno)

                artifact = TestArtifact(
                    id=test_id,
                    file_path=str(path).replace("\\", "/"),
                    line_start=line_start,
                    line_end=line_end,
                    framework="pytest",
                    declared_req_refs=sorted(list(declared_refs)),
                    assertion_statements=assertions,
                    execution_status=TestExecutionStatus.UNEXECUTED,
                )
                artifacts.append(artifact)

        return artifacts

    def parse_directory(self, dir_path: Path | str) -> List[TestArtifact]:
        """
        Recursively scans directory for test_*.py and *_test.py files.
        """
        path = Path(dir_path)
        if not path.is_dir():
            return self.parse_file(path)

        all_artifacts: List[TestArtifact] = []
        for p in path.rglob("*.py"):
            if p.name.startswith("test_") or p.name.endswith("_test.py"):
                all_artifacts.extend(self.parse_file(p))

        return all_artifacts

    def _is_test_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Determines if a function definition is a test case."""
        if node.name.startswith("test_") or node.name.endswith("_test"):
            return True
        for decorator in node.decorator_list:
            dec_id = ""
            if isinstance(decorator, ast.Name):
                dec_id = decorator.id
            elif isinstance(decorator, ast.Attribute):
                dec_id = decorator.attr
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    dec_id = decorator.func.id
                elif isinstance(decorator.func, ast.Attribute):
                    dec_id = decorator.func.attr
            if "test" in dec_id.lower() or "req" in dec_id.lower():
                return True
        return False

    def _extract_requirement_references(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, source: str
    ) -> Set[str]:
        """Extracts requirement IDs from decorators, docstrings, and function body comments."""
        refs: Set[str] = set()

        # 1. Check decorators like @pytest.mark.req("REQ-001")
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                for arg in decorator.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        for match in self._REQ_ID_RE.findall(arg.value):
                            refs.add(match.upper())

        # 2. Check docstring
        docstring = ast.get_docstring(node)
        if docstring:
            for match in self._REQ_ID_RE.findall(docstring):
                refs.add(match.upper())

        # 3. Check line comments inside function body
        lines = source.splitlines()
        start = node.lineno - 1
        end = getattr(node, "end_lineno", node.lineno)
        body_lines = lines[start:end]
        for line in body_lines:
            if "#" in line:
                comment = line.split("#", 1)[1]
                if any(k in comment.lower() for k in ["req", "covers", "traces", "verifies"]):
                    for match in self._REQ_ID_RE.findall(comment):
                        refs.add(match.upper())

        return refs

    def _extract_assertions(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """Extracts readable affirmative assertion statements."""
        assertions: List[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                try:
                    stmt = ast.unparse(child.test).strip()
                    assertions.append(f"assert {stmt}")
                except Exception:
                    assertions.append("assert <expression>")
            elif isinstance(child, ast.Call):
                # unittest style: self.assertEqual, self.assertTrue
                func_name = ""
                if isinstance(child.func, ast.Attribute):
                    func_name = child.func.attr
                if func_name.startswith("assert"):
                    try:
                        stmt = ast.unparse(child).strip()
                        assertions.append(stmt)
                    except Exception:
                        assertions.append(f"{func_name}(...)")
        return assertions
