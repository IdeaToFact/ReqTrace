# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Gherkin / Cucumber BDD Feature File Parser for ReqTrace.
Extracts test scenarios, requirement tags, and assertion steps without external dependencies.
100% offline and deterministic.
"""

import re
from pathlib import Path
from typing import List, Optional

from reqtrace.models.test_artifact import TestArtifact


TAG_PATTERN = re.compile(r"@([A-Za-z0-9_\-\.]+)")
FEATURE_PATTERN = re.compile(r"^\s*Feature:\s*(.+)$", re.IGNORECASE)
SCENARIO_PATTERN = re.compile(r"^\s*(?:Scenario|Scenario Outline):\s*(.+)$", re.IGNORECASE)
STEP_PATTERN = re.compile(r"^\s*(Given|When|Then|And|But)\s+(.+)$", re.IGNORECASE)


class GherkinFeatureParser:
    """
    Parses BDD .feature files into canonical TestArtifact objects.
    Captures scenarios, tags (e.g. @REQ-101), and verification steps (Then/And).
    """

    def parse_file(self, feature_path: Path) -> List[TestArtifact]:
        if not feature_path.exists():
            return []

        try:
            content = feature_path.read_text(encoding="utf-8")
        except Exception:
            return []

        lines = content.splitlines()
        artifacts: List[TestArtifact] = []

        seen_feature = False
        feature_tags: List[str] = []
        pending_tags: List[str] = []
        current_scenario_tags: List[str] = []
        current_scenario_name: Optional[str] = None
        current_start_line = 0
        current_assertions: List[str] = []
        in_then_block = False

        normalized_path = str(feature_path).replace("\\", "/")

        for line_no, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # 1. Tags: @REQ-01 @SAFETY (before Feature -> feature-wide; after Feature -> next scenario)
            if line.startswith("@"):
                found_tags = TAG_PATTERN.findall(line)
                if not seen_feature:
                    feature_tags.extend(found_tags)
                else:
                    pending_tags.extend(found_tags)
                continue

            # 2. Feature header boundary
            if FEATURE_PATTERN.match(line):
                seen_feature = True
                continue

            # 3. Scenario or Scenario Outline
            scen_match = SCENARIO_PATTERN.match(line)
            if scen_match:
                # Flush previous scenario
                if current_scenario_name:
                    test_id = f"{normalized_path}::{current_scenario_name}"
                    all_tags = list(dict.fromkeys(feature_tags + current_scenario_tags))
                    artifacts.append(
                        TestArtifact(
                            id=test_id,
                            file_path=normalized_path,
                            line_start=current_start_line,
                            line_end=line_no - 1,
                            assertion_statements=current_assertions,
                            declared_req_refs=all_tags,
                            framework="gherkin",
                        )
                    )

                current_scenario_name = scen_match.group(1).strip()
                current_scenario_tags = list(pending_tags)
                pending_tags = []
                current_start_line = line_no
                current_assertions = []
                in_then_block = False
                continue

            # 3. Steps (Given / When / Then / And / But)
            step_match = STEP_PATTERN.match(line)
            if step_match and current_scenario_name:
                step_type = step_match.group(1).capitalize()
                step_text = step_match.group(2).strip()

                if step_type == "Then":
                    in_then_block = True
                    current_assertions.append(f"Then {step_text}")
                elif in_then_block and step_type in ("And", "But"):
                    current_assertions.append(f"{step_type} {step_text}")
                elif step_type in ("Given", "When"):
                    in_then_block = False

        # Flush final scenario
        if current_scenario_name:
            test_id = f"{normalized_path}::{current_scenario_name}"
            all_tags = list(dict.fromkeys(feature_tags + current_scenario_tags))
            artifacts.append(
                TestArtifact(
                    id=test_id,
                    file_path=normalized_path,
                    line_start=current_start_line,
                    line_end=len(lines),
                    assertion_statements=current_assertions,
                    declared_req_refs=all_tags,
                    framework="gherkin",
                )
            )

        return artifacts

    def parse_directory(self, directory: Path) -> List[TestArtifact]:
        artifacts: List[TestArtifact] = []
        if not directory.exists() or not directory.is_dir():
            return artifacts

        for f in directory.rglob("*.feature"):
            artifacts.extend(self.parse_file(f))

        return artifacts
