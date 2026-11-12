# Copyright (C) 2026 Idea To Fact LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""
Test License Guardrails for ReqTrace.
Guarantees compliance with open-core dual-licensing:
- Core Project: GNU AGPLv3 (SPDX: AGPL-3.0-only) stewarded by Idea To Fact LLC
- Direct Dependencies: Strictly Permissive (Apache-2.0, MIT, BSD, PSF) to avoid upstream copyleft entanglements
- Legal Artifacts: LICENSE, NOTICE, DISCLAIMER.md, PRIVACY.md, THIRD_PARTY_NOTICES.md, EDITIONS.md, TRADEMARKS.md, COMMERCIAL_TERMS_FRAMEWORK.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, CHANGELOG.md
"""

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

PROHIBITED_DEPENDENCY_PATTERNS = [
    "pymupdf",
    "fitz",
    "pytesseract",
]

ALLOWED_KNOWN_DEPENDENCIES = {
    "pydantic": "MIT",
    "pydantic-settings": "MIT",
    "typer": "MIT",
    "rich": "MIT",
    "defusedxml": "PSF-2.0",
    "pypdfium2": "Apache-2.0 / BSD-3-Clause",
    "python-docx": "MIT",
    "rapidfuzz": "MIT",
    "rank-bm25": "Apache-2.0",
    "fastembed": "Apache-2.0",
    "httpx": "BSD-3-Clause",
    "fastapi": "MIT",
    "python-multipart": "Apache-2.0",
    "uvicorn": "BSD-3-Clause",
    "filelock": "MIT (v4.x) / The Unlicense (prior)",
    "pytest": "MIT",
    "pytest-cov": "MIT",
    "pip-licenses": "MIT",
}


def test_no_prohibited_packages_in_pyproject() -> None:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml must exist"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    all_deps = deps + dev_deps

    for dep_spec in all_deps:
        dep_name = dep_spec.split(">=")[0].split("==")[0].split("<")[0].strip().lower()

        # Assert no prohibited copyleft packages in direct dependencies
        for prohibited in PROHIBITED_DEPENDENCY_PATTERNS:
            assert (
                prohibited not in dep_name
            ), f"Prohibited package '{dep_name}' found in pyproject.toml!"

        # Assert package is recognized in our permissive audit registry
        assert (
            dep_name in ALLOWED_KNOWN_DEPENDENCIES
        ), f"Dependency '{dep_name}' must be reviewed and added to ALLOWED_KNOWN_DEPENDENCIES."


def test_license_declared_is_agpl_3_0() -> None:
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    license_info = data.get("project", {}).get("license", {})
    assert license_info.get("text") == "AGPL-3.0-only", "Core project license must be AGPL-3.0-only"


def test_license_and_governance_files_exist() -> None:
    root = Path(__file__).parent.parent

    # LICENSE must be AGPLv3 full text
    license_file = root / "LICENSE"
    assert license_file.exists() and license_file.stat().st_size > 30000
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_file.read_text(encoding="utf-8")

    # NOTICE
    notice_file = root / "NOTICE"
    assert notice_file.exists()
    notice_text = notice_file.read_text(encoding="utf-8")
    assert "ReqTrace Community Edition" in notice_text
    assert "AGPL-3.0-only" in notice_text
    assert "Idea To Fact LLC" in notice_text

    # DISCLAIMER.md
    disclaimer_file = root / "DISCLAIMER.md"
    assert disclaimer_file.exists()
    disclaimer_text = disclaimer_file.read_text(encoding="utf-8")
    assert "No Safety Certification" in disclaimer_text
    assert "GNU Affero General Public License" in disclaimer_text
    assert ".reqtrace/reviews.jsonl" in disclaimer_text

    # THIRD_PARTY_NOTICES.md
    third_party_file = root / "THIRD_PARTY_NOTICES.md"
    assert third_party_file.exists()
    tp_text = third_party_file.read_text(encoding="utf-8")
    assert "Pydantic" in tp_text
    assert "Permissive Clean-Room Dependency Policy" in tp_text

    # docs/EDITIONS.md
    editions_file = root / "docs" / "EDITIONS.md"
    assert editions_file.exists()
    editions_text = editions_file.read_text(encoding="utf-8")
    assert "AGPLv3 Community Edition" in editions_text
    assert "Commercial Pro Edition" in editions_text
    assert "Commercial Enterprise Edition" in editions_text
    assert ".reqtrace/reviews.jsonl" in editions_text

    # docs/TRADEMARKS.md
    trademarks_file = root / "docs" / "TRADEMARKS.md"
    assert trademarks_file.exists()
    tm_text = trademarks_file.read_text(encoding="utf-8")
    assert "ReqTrace" in tm_text
    assert "AirGap Axis" in tm_text
    assert "Idea To Fact LLC" in tm_text

    # CONTRIBUTING.md
    contributing_file = root / "CONTRIBUTING.md"
    assert contributing_file.exists()
    contrib_text = contributing_file.read_text(encoding="utf-8")
    assert "Contributor License Agreement (CLA v1.0)" in contrib_text
    assert "Corporate CLA" in contrib_text

    # SECURITY.md
    security_file = root / "SECURITY.md"
    assert security_file.exists()
    sec_text = security_file.read_text(encoding="utf-8")
    assert "Zero-Egress Air-Gap Architecture" in sec_text
    assert ".reqtrace/reviews.jsonl" in sec_text

    # CODE_OF_CONDUCT.md
    coc_file = root / "CODE_OF_CONDUCT.md"
    assert coc_file.exists()
    assert "Contributor Covenant" in coc_file.read_text(encoding="utf-8")

    # CHANGELOG.md
    changelog_file = root / "CHANGELOG.md"
    assert changelog_file.exists()
    assert "Keep a Changelog" in changelog_file.read_text(encoding="utf-8")

    # PRIVACY.md
    privacy_file = root / "PRIVACY.md"
    assert privacy_file.exists()
    privacy_text = privacy_file.read_text(encoding="utf-8")
    assert ".reqtrace/" in privacy_text
    assert "reqtrace_session_<port>" in privacy_text
    assert "FASTEMBED_CACHE_PATH" in privacy_text

    # docs/commercial/COMMERCIAL_TERMS_FRAMEWORK.md
    commercial_terms_file = root / "docs" / "commercial" / "COMMERCIAL_TERMS_FRAMEWORK.md"
    assert commercial_terms_file.exists()
    ct_text = commercial_terms_file.read_text(encoding="utf-8")
    assert "AGPLv3" in ct_text
    assert "DO-330" in ct_text
    assert "twelve (12) months" in ct_text
