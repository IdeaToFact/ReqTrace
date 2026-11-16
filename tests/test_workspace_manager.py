# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Unit Tests for WorkspaceManager (Option B directory validation, manifests, and registry).
"""

from pathlib import Path
import pytest

from reqtrace.models.workspace import ProjectMetadata, WorkspaceManifest
from reqtrace.workspace.manager import WorkspaceManager


def test_workspace_manager_option_b_rejects_missing_directory(tmp_path: Path) -> None:
    registry_file = tmp_path / "global_registry.json"
    manager = WorkspaceManager(global_registry_path=registry_file)

    missing_dir = tmp_path / "non_existent_folder"
    assert not missing_dir.exists()

    with pytest.raises(FileNotFoundError, match="Target directory does not exist"):
        manager.init_workspace(missing_dir, project_name="Flight Controls")

    with pytest.raises(FileNotFoundError, match="Target directory does not exist"):
        manager.open_workspace(missing_dir)


def test_workspace_manager_init_existing_directory(tmp_path: Path) -> None:
    registry_file = tmp_path / "global_registry.json"
    manager = WorkspaceManager(global_registry_path=registry_file)

    project_dir = tmp_path / "my_project"
    project_dir.mkdir()

    manifest, metadata = manager.init_workspace(
        project_dir,
        project_name="GPS Nav Subsystem",
        target_standard="DO-178C DAL B",
        baseline_id="BASELINE-NAV-001",
    )

    assert isinstance(manifest, WorkspaceManifest)
    assert isinstance(metadata, ProjectMetadata)
    assert metadata.project_name == "GPS Nav Subsystem"
    assert metadata.target_standard == "DO-178C DAL B"
    assert metadata.baseline_id == "BASELINE-NAV-001"

    # Verify directory structure
    dot_reqtrace = project_dir / ".reqtrace"
    assert dot_reqtrace.is_dir()
    assert (dot_reqtrace / "workspace.json").is_file()
    assert (dot_reqtrace / "project.json").is_file()
    assert (dot_reqtrace / "reviews.jsonl").is_file()
    assert (dot_reqtrace / "baselines").is_dir()

    # Verify global registry was updated
    recent = manager.get_recent_workspaces()
    assert len(recent) == 1
    assert recent[0].name == "GPS Nav Subsystem"
    assert Path(recent[0].path).resolve() == project_dir.resolve()


def test_workspace_manager_open_existing_workspace(tmp_path: Path) -> None:
    registry_file = tmp_path / "global_registry.json"
    manager = WorkspaceManager(global_registry_path=registry_file)

    project_dir = tmp_path / "existing_project"
    project_dir.mkdir()

    # First init
    manager.init_workspace(project_dir, project_name="Battery Management", target_standard="ISO 26262 ASIL D")

    # Now open with another manager instance
    manager2 = WorkspaceManager(global_registry_path=registry_file)
    manifest, metadata = manager2.open_workspace(project_dir)

    assert metadata.project_name == "Battery Management"
    assert metadata.target_standard == "ISO 26262 ASIL D"
    assert manifest.requirements_file == "requirements.json"


def test_workspace_manager_update_metadata_and_remove(tmp_path: Path) -> None:
    registry_file = tmp_path / "global_registry.json"
    manager = WorkspaceManager(global_registry_path=registry_file)

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    manager.init_workspace(project_dir, project_name="Old Name")

    updated = manager.update_project_metadata(project_dir, {"project_name": "New Name", "spec_version": "2.0"})
    assert updated.project_name == "New Name"
    assert updated.spec_version == "2.0"

    recent = manager.get_recent_workspaces()
    assert recent[0].name == "New Name"

    # Test removal
    manager.remove_recent_workspace(project_dir)
    recent_after = manager.get_recent_workspaces()
    assert len(recent_after) == 0

