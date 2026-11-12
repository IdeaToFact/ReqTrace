# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Baseline Specification Diff Engine for ReqTrace.
Ported from DocuAgent AI's diffing primitives (diff-engine.ts & navigation-drift.ts).
Compares requirement specifications across revisions to detect:
- Added requirements
- Removed / Deprecated requirements
- Modified requirements (reworded, modified parameters)
- Associated stale trace links
"""

from typing import Dict, List, Optional, Tuple
# pyrefly: ignore[missing-import]
from pydantic import BaseModel, Field
from reqtrace.models.requirement import Requirement


class ModifiedRequirementDelta(BaseModel):
    req_id: str
    old_title: str
    new_title: str
    old_description: str
    new_description: str
    changes: List[str]


class SpecDiffResult(BaseModel):
    old_spec_name: str
    new_spec_name: str
    total_old: int
    total_new: int
    added: List[Requirement] = Field(default_factory=list)
    removed: List[Requirement] = Field(default_factory=list)
    modified: List[ModifiedRequirementDelta] = Field(default_factory=list)
    unchanged_count: int = 0
    stale_req_ids: List[str] = Field(default_factory=list)


class SpecDiffEngine:
    def compare(
        self,
        old_reqs: List[Requirement],
        new_reqs: List[Requirement],
        old_name: str = "v1",
        new_name: str = "v2",
    ) -> SpecDiffResult:
        old_map: Dict[str, Requirement] = {r.id: r for r in old_reqs}
        new_map: Dict[str, Requirement] = {r.id: r for r in new_reqs}

        added: List[Requirement] = []
        removed: List[Requirement] = []
        modified: List[ModifiedRequirementDelta] = []
        unchanged_count = 0
        stale_ids: List[str] = []

        # Check for added and modified
        for req_id, new_req in new_map.items():
            if req_id not in old_map:
                added.append(new_req)
            else:
                old_req = old_map[req_id]
                if old_req.sha256 == new_req.sha256:
                    unchanged_count += 1
                else:
                    changes: List[str] = []
                    if old_req.description.strip() != new_req.description.strip():
                        changes.append("description modified")
                    if old_req.title.strip() != new_req.title.strip():
                        changes.append("title modified")
                    if old_req.level != new_req.level:
                        changes.append(f"level changed: {old_req.level.value} ➔ {new_req.level.value}")
                    if old_req.parent_ids != new_req.parent_ids:
                        changes.append(f"parents changed: {old_req.parent_ids} ➔ {new_req.parent_ids}")
                    if not changes:
                        changes.append("attributes/revision modified")

                    modified.append(
                        ModifiedRequirementDelta(
                            req_id=req_id,
                            old_title=old_req.title,
                            new_title=new_req.title,
                            old_description=old_req.description,
                            new_description=new_req.description,
                            changes=changes,
                        )
                    )
                    stale_ids.append(req_id)

        # Check for removed
        for req_id, old_req in old_map.items():
            if req_id not in new_map:
                removed.append(old_req)
                stale_ids.append(req_id)

        return SpecDiffResult(
            old_spec_name=old_name,
            new_spec_name=new_name,
            total_old=len(old_reqs),
            total_new=len(new_reqs),
            added=added,
            removed=removed,
            modified=modified,
            unchanged_count=unchanged_count,
            stale_req_ids=stale_ids,
        )

