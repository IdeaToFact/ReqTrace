# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Incremental Reanalysis Coordinator for ReqTrace.
Decouples file loading, semantic linking, and status evaluation via granular dirty flags.
Guarantees the architectural performance invariant:
A review submission shall NEVER invoke requirement-to-test relinking (O(N*M)).
Submitting a review decision executes strictly the append-only review persistence
and the linear canonical status engine (O(N)).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from reqtrace.analysis.review_store import ReviewStore
from reqtrace.analysis.status import WorkspaceStatusReport, evaluate_workspace_status
from reqtrace.models.requirement import Requirement
from reqtrace.models.test_artifact import TestArtifact
from reqtrace.models.trace_link import ReviewEvent, ReviewStatus, TraceLink
from reqtrace.models.workspace import ProjectMetadata, WorkspaceManifest
from reqtrace.workspace.manager import WorkspaceManager


class AnalysisCoordinator:
    """
    Coordinates workspace data caching, granular dirty-flag invalidations,
    and decoupled fast-path review recomputation.
    """

    def __init__(
        self,
        workspace_root: Path | str,
        workspace_manager: Optional[WorkspaceManager] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_manager = workspace_manager or WorkspaceManager()

        self.manifest = self._load_manifest()
        self.project_meta = self.workspace_manager.get_project_metadata(self.workspace_root)
        self.review_store = ReviewStore(self.workspace_root / self.manifest.reviews_file)

        # In-memory cached artifacts
        self._cached_requirements: Optional[List[Requirement]] = None
        self._cached_tests: Optional[List[TestArtifact]] = None
        self._cached_links: Optional[List[TraceLink]] = None
        self._cached_status: Optional[WorkspaceStatusReport] = None

        # Granular dirty flags
        self.reqs_dirty: bool = True
        self.tests_dirty: bool = True
        self.reviews_dirty: bool = True

        # Observability counters for performance verification
        self.relink_count: int = 0
        self.status_recompute_count: int = 0

    def _load_manifest(self) -> WorkspaceManifest:
        manifest_file = self.workspace_root / ".reqtrace" / "workspace.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    return WorkspaceManifest.model_validate_json(f.read())
            except Exception:
                pass
        return WorkspaceManifest()

    def invalidate_requirements(self) -> None:
        """Flags requirements as modified. Requires relinking."""
        self.reqs_dirty = True
        self._cached_requirements = None
        self._cached_links = None
        self._cached_status = None

    def invalidate_tests(self) -> None:
        """Flags test implementations or verdicts as modified. Requires relinking."""
        self.tests_dirty = True
        self._cached_tests = None
        self._cached_links = None
        self._cached_status = None

    def invalidate_reviews(self) -> None:
        """
        Flags reviews as modified.
        CRITICAL: Does NOT invalidate requirements, tests, or link topology!
        """
        self.reviews_dirty = True
        self._cached_status = None

    def get_requirements(self, force_reload: bool = False) -> List[Requirement]:
        if self._cached_requirements is not None and not force_reload and not self.reqs_dirty:
            return self._cached_requirements

        reqs_path = self.workspace_root / self.manifest.requirements_file
        if not reqs_path.exists():
            self._cached_requirements = []
        else:
            try:
                with open(reqs_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cached_requirements = [Requirement.model_validate(item) for item in data]
            except Exception:
                self._cached_requirements = []

        self.reqs_dirty = False
        return self._cached_requirements

    def get_tests(self, force_reload: bool = False) -> List[TestArtifact]:
        if self._cached_tests is not None and not force_reload and not self.tests_dirty:
            return self._cached_tests

        tests_path = self.workspace_root / self.manifest.tests_file
        if not tests_path.exists():
            self._cached_tests = []
        else:
            try:
                with open(tests_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cached_tests = [TestArtifact.model_validate(item) for item in data]
            except Exception:
                self._cached_tests = []

        self.tests_dirty = False
        return self._cached_tests

    def get_links(self, force_relink: bool = False) -> List[TraceLink]:
        """
        Retrieves active trace links.
        Only invokes TraceLinker if requirements or tests changed or if cache is empty.
        Applies review overlay on the cached topology.
        """
        reqs = self.get_requirements()
        req_map = {r.id: r for r in reqs}

        # Check if we can reuse cached base links
        if (
            self._cached_links is not None
            and not force_relink
            and not self.reqs_dirty
            and not self.tests_dirty
        ):
            # Fast path: Clone or re-overlay existing links without re-running O(N*M) text linker
            return self.review_store.apply_overlay(self._cached_links, req_map)

        # Relink pass required
        self.relink_count += 1
        tests = self.get_tests()

        # Check for explicit links.json override
        links_path = self.workspace_root / "links.json"
        if links_path.exists():
            try:
                with open(links_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cached_links = [TraceLink.model_validate(item) for item in data]
            except Exception:
                self._cached_links = []
        elif reqs and tests:
            from reqtrace.engine.linker import TraceLinker
            linker = TraceLinker()
            self._cached_links = linker.link(reqs, tests)
        else:
            self._cached_links = []

        self.reqs_dirty = False
        self.tests_dirty = False

        return self.review_store.apply_overlay(self._cached_links, req_map)

    def get_status(self, force_recompute: bool = False) -> WorkspaceStatusReport:
        """
        Computes canonical status metrics.
        Reuses cached links and only evaluates the linear status engine.
        """
        if (
            self._cached_status is not None
            and not force_recompute
            and not self.reqs_dirty
            and not self.tests_dirty
            and not self.reviews_dirty
        ):
            return self._cached_status

        self.status_recompute_count += 1
        reqs = self.get_requirements()
        tests = self.get_tests()
        links = self.get_links()

        req_map = {r.id: r for r in reqs}
        links = self.review_store.apply_overlay(links, req_map)
        waivers = self.review_store.get_requirement_waivers()

        self._cached_status = evaluate_workspace_status(reqs, tests, links, waivers)
        self.reviews_dirty = False
        return self._cached_status

    def record_review(self, event: ReviewEvent) -> WorkspaceStatusReport:
        """
        Fast-path review recording.
        Appends event under FileLock and recomputes canonical status in O(N) time
        WITHOUT invoking O(N*M) TraceLinker.
        """
        self.review_store.append_event(event)
        self.invalidate_reviews()
        return self.get_status()

    def record_candidate_action(
        self,
        action: str,
        req_id: str,
        test_id: str,
        comment: Optional[str] = None,
        reviewer: str = "Local Engineer",
    ) -> WorkspaceStatusReport:
        """
        Fast-path candidate promotion or rejection.
        """
        action_clean = action.lower().strip()
        if action_clean not in {"approve", "reject"}:
            raise ValueError(f"Invalid candidate action: '{action}'. Must be 'approve' or 'reject'.")

        status = ReviewStatus.APPROVED if action_clean == "approve" else ReviewStatus.REJECTED

        # Capture requirement content hash at time of review
        reqs = self.get_requirements()
        current_req = next((r for r in reqs if r.id == req_id), None)
        req_hash = current_req.sha256 if current_req else None

        event = ReviewEvent(
            req_id=req_id,
            test_id=test_id,
            status=status,
            reviewed_by=reviewer,
            comment=comment or ("Candidate link approved by reviewer" if action_clean == "approve" else "Candidate link rejected"),
            req_content_hash=req_hash,
            req_sha256_at_review=req_hash,
        )
        return self.record_review(event)

    def switch_workspace(self, new_workspace_root: Path | str) -> None:
        """
        Switches coordinator to a different workspace root, refreshing manifests and clearing caches.
        """
        self.workspace_root = Path(new_workspace_root).resolve()
        self.manifest = self._load_manifest()
        self.project_meta = self.workspace_manager.get_project_metadata(self.workspace_root)
        self.review_store = ReviewStore(self.workspace_root / self.manifest.reviews_file)

        self._cached_requirements = None
        self._cached_tests = None
        self._cached_links = None
        self._cached_status = None

        self.reqs_dirty = True
        self.tests_dirty = True
        self.reviews_dirty = True

