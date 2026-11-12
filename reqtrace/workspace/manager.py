# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Workspace Manager for ReqTrace.
Manages workspace lifecycle, directory existence validation (Option B),
manifest persistence, project metadata, and recent workspaces tracking.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from filelock import FileLock

from reqtrace.models.workspace import (
    ProjectMetadata,
    WorkspaceInfo,
    WorkspaceManifest,
)


class WorkspaceManager:
    """
    Central coordinator for workspace initialization, validation, and metadata tracking.
    """

    def __init__(self, global_registry_path: Optional[Path | str] = None) -> None:
        if global_registry_path:
            self.global_registry_path = Path(global_registry_path).resolve()
        else:
            env_path = os.environ.get("REQTRACE_REGISTRY_PATH")
            if env_path:
                self.global_registry_path = Path(env_path).resolve()
            else:
                default_dir = Path.home() / ".reqtrace"
                try:
                    default_dir.mkdir(parents=True, exist_ok=True)
                    self.global_registry_path = (default_dir / "workspaces.json").resolve()
                except (PermissionError, OSError):
                    # Sandboxed or restricted home directory fallback
                    fallback_dir = Path(tempfile.gettempdir()) / "reqtrace"
                    fallback_dir.mkdir(parents=True, exist_ok=True)
                    self.global_registry_path = (fallback_dir / "workspaces.json").resolve()

        self._ensure_global_dir()
        self._lock = FileLock(str(self.global_registry_path.with_suffix(".lock")), timeout=3.0)

    def _ensure_global_dir(self) -> None:
        try:
            self.global_registry_path.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            pass

    def _load_recent_unlocked(self) -> List[WorkspaceInfo]:
        if not self.global_registry_path.exists():
            return []
        try:
            with open(self.global_registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [WorkspaceInfo.model_validate(item) for item in data]
        except Exception:
            return []
        return []

    def get_recent_workspaces(self) -> List[WorkspaceInfo]:
        """
        Retrieves list of recently accessed workspaces ordered by last_opened descending.
        """
        try:
            with self._lock:
                return self._load_recent_unlocked()
        except Exception:
            return self._load_recent_unlocked()

    def _write_recent_unlocked(
        self,
        canonical_path: str,
        name: str,
        now_str: str,
        target_standard: Optional[str] = None,
        baseline_id: Optional[str] = None,
    ) -> None:
        existing = self._load_recent_unlocked()
        filtered = [w for w in existing if Path(w.path).resolve() != Path(canonical_path)]
        new_entry = WorkspaceInfo(
            path=canonical_path,
            name=name,
            last_opened=now_str,
            target_standard=target_standard,
            baseline_id=baseline_id,
        )
        updated = [new_entry] + filtered
        updated = updated[:20]
        try:
            with open(self.global_registry_path, "w", encoding="utf-8") as f:
                json.dump([item.model_dump() for item in updated], f, indent=2)
        except Exception:
            pass

    def add_recent_workspace(
        self,
        path: Path | str,
        name: str,
        target_standard: Optional[str] = None,
        baseline_id: Optional[str] = None,
    ) -> None:
        """
        Adds or bumps a workspace in the recent workspaces registry (~/.reqtrace/workspaces.json).
        """
        self._ensure_global_dir()
        canonical_path = str(Path(path).resolve())
        now_str = datetime.now(timezone.utc).isoformat()

        try:
            with self._lock:
                self._write_recent_unlocked(canonical_path, name, now_str, target_standard, baseline_id)
        except Exception:
            self._write_recent_unlocked(canonical_path, name, now_str, target_standard, baseline_id)

    def remove_recent_workspace(self, path: Path | str) -> None:
        """
        Removes a workspace entry from the recent workspaces registry.
        """
        if not self.global_registry_path.exists():
            return

        canonical_path = str(Path(path).resolve())

        def _do_remove():
            existing = self._load_recent_unlocked()
            filtered = [w for w in existing if Path(w.path).resolve() != Path(canonical_path)]
            try:
                with open(self.global_registry_path, "w", encoding="utf-8") as f:
                    json.dump([item.model_dump() for item in filtered], f, indent=2)
            except Exception:
                pass

        try:
            with self._lock:
                _do_remove()
        except Exception:
            _do_remove()

    def init_workspace(
        self,
        path: Path | str,
        project_name: str,
        target_standard: str = "DO-178C DAL B",
        spec_version: str = "1.0",
        baseline_id: str = "BASELINE-001",
    ) -> Tuple[WorkspaceManifest, ProjectMetadata]:
        """
        Initializes a ReqTrace workspace inside an existing directory (Option B).
        Raises FileNotFoundError (HTTP 400 in API layer) if the directory does not exist.
        """
        target_dir = Path(path).resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(
                f"Target directory does not exist: '{target_dir}'. Please choose an existing directory."
            )

        dot_reqtrace = target_dir / ".reqtrace"
        dot_reqtrace.mkdir(parents=True, exist_ok=True)

        baselines_dir = dot_reqtrace / "baselines"
        baselines_dir.mkdir(parents=True, exist_ok=True)

        reviews_file = dot_reqtrace / "reviews.jsonl"
        if not reviews_file.exists():
            reviews_file.touch()

        # Initialize WorkspaceManifest (.reqtrace/workspace.json)
        manifest_path = dot_reqtrace / "workspace.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = WorkspaceManifest.model_validate_json(f.read())
        else:
            manifest = WorkspaceManifest()
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(manifest.model_dump_json(indent=2))

        # Initialize ProjectMetadata (.reqtrace/project.json)
        project_path = dot_reqtrace / "project.json"
        now_str = datetime.now(timezone.utc).isoformat()
        if project_path.exists():
            with open(project_path, "r", encoding="utf-8") as f:
                metadata = ProjectMetadata.model_validate_json(f.read())
                # Update project name or standard if provided
                metadata.project_name = project_name
                metadata.target_standard = target_standard
                metadata.updated_at = now_str
            with open(project_path, "w", encoding="utf-8") as f:
                f.write(metadata.model_dump_json(indent=2))
        else:
            metadata = ProjectMetadata(
                project_name=project_name,
                target_standard=target_standard,
                spec_version=spec_version,
                baseline_id=baseline_id,
                created_at=now_str,
                updated_at=now_str,
            )
            with open(project_path, "w", encoding="utf-8") as f:
                f.write(metadata.model_dump_json(indent=2))

        # Register in recent workspaces
        self.add_recent_workspace(
            path=target_dir,
            name=metadata.project_name,
            target_standard=metadata.target_standard,
            baseline_id=metadata.baseline_id,
        )

        return manifest, metadata

    def open_workspace(self, path: Path | str) -> Tuple[WorkspaceManifest, ProjectMetadata]:
        """
        Opens an existing workspace. Validates existence (Option B) and loads or generates manifests.
        """
        target_dir = Path(path).resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(
                f"Target directory does not exist: '{target_dir}'. Please choose an existing directory."
            )

        dot_reqtrace = target_dir / ".reqtrace"
        dot_reqtrace.mkdir(parents=True, exist_ok=True)

        baselines_dir = dot_reqtrace / "baselines"
        baselines_dir.mkdir(parents=True, exist_ok=True)

        reviews_file = dot_reqtrace / "reviews.jsonl"
        if not reviews_file.exists():
            reviews_file.touch()

        # Workspace manifest
        manifest_path = dot_reqtrace / "workspace.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = WorkspaceManifest.model_validate_json(f.read())
        else:
            manifest = WorkspaceManifest()
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(manifest.model_dump_json(indent=2))

        # Project metadata
        project_path = dot_reqtrace / "project.json"
        now_str = datetime.now(timezone.utc).isoformat()
        if project_path.exists():
            with open(project_path, "r", encoding="utf-8") as f:
                metadata = ProjectMetadata.model_validate_json(f.read())
        else:
            metadata = ProjectMetadata(
                project_name=target_dir.name,
                created_at=now_str,
                updated_at=now_str,
            )
            with open(project_path, "w", encoding="utf-8") as f:
                f.write(metadata.model_dump_json(indent=2))

        # Register in recent workspaces
        self.add_recent_workspace(
            path=target_dir,
            name=metadata.project_name,
            target_standard=metadata.target_standard,
            baseline_id=metadata.baseline_id,
        )

        return manifest, metadata

    def get_project_metadata(self, workspace_root: Path | str) -> ProjectMetadata:
        """
        Loads the ProjectMetadata for the specified workspace root.
        """
        target_dir = Path(workspace_root).resolve()
        project_path = target_dir / ".reqtrace" / "project.json"
        if project_path.exists():
            with open(project_path, "r", encoding="utf-8") as f:
                return ProjectMetadata.model_validate_json(f.read())
        # Return fallback
        now_str = datetime.now(timezone.utc).isoformat()
        return ProjectMetadata(project_name=target_dir.name, created_at=now_str, updated_at=now_str)

    def update_project_metadata(
        self, workspace_root: Path | str, updates: Dict[str, Any]
    ) -> ProjectMetadata:
        """
        Updates fields on ProjectMetadata and persists to disk.
        """
        target_dir = Path(workspace_root).resolve()
        meta = self.get_project_metadata(target_dir)

        # Apply allowed updates
        for k, v in updates.items():
            if hasattr(meta, k) and k not in {"created_at", "schema_version"}:
                setattr(meta, k, v)

        meta.updated_at = datetime.now(timezone.utc).isoformat()
        project_path = target_dir / ".reqtrace" / "project.json"
        project_path.parent.mkdir(parents=True, exist_ok=True)
        with open(project_path, "w", encoding="utf-8") as f:
            f.write(meta.model_dump_json(indent=2))

        # Update in recent workspaces registry as well
        self.add_recent_workspace(
            path=target_dir,
            name=meta.project_name,
            target_standard=meta.target_standard,
            baseline_id=meta.baseline_id,
        )

        return meta
