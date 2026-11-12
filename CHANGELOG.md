# Changelog (`CHANGELOG.md`)

All notable changes to **ReqTrace Community Edition (AGPLv3)** will be documented in this file. Commercial Pro and Enterprise releases are tracked separately under proprietary commercial release notes.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- **Governance, Legal & Security Hardening**:
  - Updated `NOTICE`, `CONTRIBUTING.md` (CLA v1.0), `DISCLAIMER.md` (Schema `1.2`, informational non-conditional notice), `THIRD_PARTY_NOTICES.md`, `SECURITY.md`, `docs/EDITIONS.md`, `docs/TRADEMARKS.md`, and `README.md` to align with `v0.2.0` (`reqtrace ui`, `.reqtrace/reviews.jsonl`, `ExportManager`), soften unverified claims, and clarify dual-licensing and regulatory non-affiliation boundaries.
  - Corrected `SECURITY.md` technical disclosures (declared-only `pypdfium2` status, Community Edition `.reqtrace/reviews.jsonl` lack of PKI/WORM immutability, `.docx` ingestion scope, best-effort security/disclosure targets, and removed unverified PGP fingerprint placeholder).
  - Bound Docker examples and launcher scripts (`docker-run.ps1`, `docker-run.sh`, `docs/DOCKER.md`, `README.md`) to loopback (`127.0.0.1:8765:8765`), and added `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, and OCI labels to `Dockerfile`.
  - Added `PRIVACY.md` and `docs/commercial/COMMERCIAL_TERMS_FRAMEWORK.md`, linked in `README.md`, added per-file `SPDX-License-Identifier: AGPL-3.0-only` copyright headers across source and UI files, and extended `tests/test_license_guardrails.py`.

---

## [0.2.0] - 2026-11-11

### Added
- **Local Web Cockpit (`reqtrace ui`)**: Air-gapped, zero-egress single-user web application with port-scoped session security, anti-DNS rebinding, CSRF protection, and zero inline scripts/styles (100% CSP compliant).
- **Workspace Lifecycle Management (`WorkspaceManager`)**:
  - Enforced Option B directory policy (target directory must exist on disk; returns HTTP 400 otherwise).
  - Introduced `.reqtrace/workspace.json` manifest abstraction for future storage engine decouple.
  - Introduced project metadata schema (`.reqtrace/project.json`) supporting baseline IDs, spec revisions, and audit timestamps.
  - Multi-workspace tracking with sandboxed fallback support.
- **Candidate Triage Queue & Provenance Tracking**:
  - Added provenance tracking to `TraceLink`: `confidence` score (e.g. 0.88), `match_strategy` (`tag_exact`, `rapidfuzz_window`, `heuristic`), and `match_reason`.
  - Dedicated Candidate Queue UI tab with candidate triage cards and instant approve/reject actions.
  - Human review sign-off modal with mandatory rejection comments and waiver justification documentation.
  - Multi-process atomic persistence with `FileLock` (10s acquisition timeout) on `.reqtrace/reviews.jsonl`.
- **Incremental Analysis Coordinator (`AnalysisCoordinator`)**:
  - Decoupled dirty-flag cache tracker (`specs_dirty`, `tests_dirty`, `reviews_dirty`).
  - Enforced architectural performance invariant: review sign-offs bypass $O(N \times M)$ text linkers, executing only $O(N)$ canonical status recomputation in < 1.5ms.
- **Drag-and-Drop Ingestion Wizard**:
  - Dual dropzone UI modal for specifications and test implementations with format detection and error feedback.
  - REST endpoints (`POST /api/v1/ingest/spec` and `POST /api/v1/ingest/tests`) with 25MB safety caps and atomic persistence.
- **Unified Export Service & Non-Virtualized Print View (`ExportManager`)**:
  - Service layer supporting CSV, standard ReqIF XML (`<SPEC-RELATION>`), standalone HTML reports, and JSON dumps with SHA-256 integrity calculation.
  - Non-virtualized Print View route (`GET /print`) with `@media print` styling for high-resolution physical and PDF audit printouts.
- **Port Conflict UX Guard**:
  - Pre-flight socket binding probe in `reqtrace ui` preventing browser launch when port is occupied and providing actionable remediation hints.
- **Authentication Gateway & On-Demand Ticket CLI (`reqtrace ticket`)**:
  - Unauthenticated requests to `/` now render a hardened, CSP-compliant Authentication Gateway (linking external `/app.css`) accepting either raw launch tickets or pasted `Launch URL` strings, eliminating 401 SPA load banners on Docker Desktop port clicks.
  - Added OS-operator authenticated `reqtrace ticket` CLI command (`POST /internal/ticket` guarded by `0600` runtime secret) enabling `docker exec reqtrace-cockpit reqtrace ticket` to mint fresh tickets on demand without restarting running containers.
  - Extended Docker container default `--ticket-timeout` to `1800` seconds (30 minutes) and added `-Rebuild` / `--rebuild` options to Docker launcher scripts.
- **Docker Deployment Architecture & Helper Scripts**:
  - Hardened multi-stage `Dockerfile` (Python 3.12, unprivileged user UID 10001, rootless, zero telemetry).
  - Automated launch scripts `docker-run.ps1` (PowerShell) and `docker-run.sh` (Bash) supporting interactive (`-it`) and background (`-Detach`/`-d`) modes, `-Rebuild`/`--rebuild`, `-BuildOnly`/`--build-only`, automatic volume bind-mounting, and automatic browser opening.
  - Comprehensive operations, Docker Desktop setup, and air-gapped `docker save` / `docker load` guide in `docs/DOCKER.md`.
  - Added `--host` / `-h` parameter to `reqtrace ui` for container network binding (`0.0.0.0`) with `LocalhostSecurityMiddleware` loopback/bridge support.
- **Canonical Architecture Documentation**:
  - Added `docs/architecture/v0.2.0/ARCHITECTURE.md` with Mermaid diagrams covering Product, Runtime, Storage, Fast-Path Triage, Export Service, Local/Docker/Air-Gapped Kubernetes deployment topologies, security boundaries, and atomic backup/recovery flows.
- **Multi-Format Sample Datasets (`demo_assets/`)**:
  - Added organized avionics sample suites across all supported input formats: specifications (`specs/reqif/`, `specs/csv/`, `specs/docx/`), multi-language test sources (`test_sources/python/`, `test_sources/cpp/`, `test_sources/gherkin/`), and JUnit execution reports (`test_results/junit/`) documented in `demo_assets/README.md`.

### Fixed
- **Web UI Dropzone Validation & JUnit Verdict Ingestion (`routes.py`, `app.js`)**:
  - Fixed JUnit `.xml` verdict attachment and standalone JUnit parsing in `POST /api/v1/ingest/tests`, preserved original uploaded filenames, and hardened client JSON/error handling in `app.js`.
  - Added XML root tag validation (`<testsuites>`/`<testsuite>` vs `<REQ-IF>`) and empty-parse preservation guards on both dropzones so dropping a file in the wrong box returns HTTP 400 without clearing existing requirements or tests.
- **Gherkin Multi-Scenario Tag Isolation**: Fixed tag bleed between scenarios in `GherkinFeatureParser` (`reqtrace/parsers/code/gherkin.py`) by tracking `Feature:` header boundaries explicitly.
- **FastAPI Form Data Upload Dependency**: Added `python-multipart>=0.0.9` to `pyproject.toml` dependencies (and updated `THIRD_PARTY_NOTICES.md` and `tests/test_license_guardrails.py`) to resolve `RuntimeError: Form data requires 'python-multipart'` during specification uploads.
- **Docker Multi-Stage Wheel Build**: Explicitly installed `hatchling` alongside `build` under `--no-isolation` in `Dockerfile` Stage 1 (`builder`) to resolve `ModuleNotFoundError: No module named 'hatchling'`.
- **PowerShell & Bash Docker Launcher Scripts**: Fixed PowerShell argument splatting, native `stderr` capturing (`$ErrorActionPreference`), and PowerShell 5.1 pure-ASCII console formatting in `docker-run.ps1`, plus symmetric `-d`/`--rebuild` handling in `docker-run.sh`.
- **Expired Launch Ticket CSP Styling**: Removed inline `<style>` from `/login` 401 error HTML in `reqtrace/ui/routes.py` so error pages render properly under strict `style-src 'self'` CSP, and dynamically report the configured ticket timeout.
- **PyPI Trove Classifier Validation**: Replaced non-standard `(AGPLv3)` suffix with official PyPI classifier `"License :: OSI Approved :: GNU Affero General Public License v3"`.
- **ReqIF Parser XML Element Import**: Explicitly imported `Element` from `xml.etree.ElementTree` to prevent `AttributeError: module 'defusedxml.ElementTree' has no attribute 'Element'`.
- **CLI ANSI Terminal Output in Tests**: Stripped ANSI escape styling before verifying CLI `--help` output in test runners.

---

## [0.1.0] - 2026-11-06

### Added
- **ReqIF Ingestion Engine (`reqtrace ingest`):** Ingests DOORS and Polarion ReqIF 1.0/1.2 XML specifications with XML entity bomb protection (`defusedxml`), XHTML text tag scrubbing, multi-tier parent-child hierarchy extraction, and deterministic SHA-256 requirement hashing.
- **CSV Matrix Ingestion:** Ingests tabular CSV requirements matrices with configurable column mapping for requirement ID, title, text, level, and parent references.
- **Word (.docx) Specification Parser (`DocxSpecificationParser`):** Extracts requirements and hierarchy from structured tables and heading-tagged paragraphs in Microsoft Word documents using `python-docx`.
- **PyTest AST Test Scanner (`reqtrace scan`):** Parses Python test files via native AST, extracting `@pytest.mark.req("REQ-ID")` decorator tags, docstring tags, affirmative assertion expressions, and line span coordinates.
- **C/C++ Test Harness Parser (`CppHarnessParser`):** Scans C/C++ GoogleTest (`TEST`, `TEST_F`) and Catch2 test files, extracting requirement tags, assertion macros (`ASSERT_EQ`, `EXPECT_TRUE`), and file line coordinates.
- **JUnit Execution Verdict Linker (`--junit`):** Parses JUnit XML execution reports and attaches dynamic verdicts (`PASSED`, `FAILED`, `SKIPPED`) to test artifacts, enforcing the live traceability paradigm (*a failed or skipped test = an unverified requirement*).
- **Deterministic Trace Linker (`reqtrace link`):** Generates bidirectional Requirements Traceability Matrices (RTM) using 100% deterministic tag matching and RapidFuzz character-exact offset windowing.
- **Bidirectional Gap & Orphan Auditor (`reqtrace check`):** Flags orphan requirements (untested specs), unlinked rogue tests, and failed-test verification gaps with configurable CI/CD quality gate thresholds.
- **Executive Audit Summary Dashboard (`reqtrace audit-summary`):** Terminal dashboard showing total requirements, verified links, unverified gaps, orphans, and coverage percentages.
- **Specification Delta & Drift Engine (`reqtrace diff`):** Compares specification revisions, detects added, modified, and removed requirements, and flags stale trace links.
- **Persistent Human Review Store (`ReviewStore`):** Event-sourced, append-only review overlay store (`.reqtrace/reviews.jsonl`) supporting Git 3-way conflict-free merges and CLI sign-offs (`reqtrace review approve/reject/list`).
- **Standalone Air-Gapped HTML Report (`reqtrace report`):** Generates single-file, zero-dependency interactive HTML traceability matrices with inlined SVG status badges, filterable tables, and gap summaries.
- **ReqIF Traceability Roundtrip Exporter (`reqtrace export-reqif`):** Injects verified trace links back into standard ReqIF XML as `<SPEC-RELATION>` elements for DOORS/Polarion re-import.
- **Open-Core Governance & Dual-Licensing Architecture:** Configured GNU AGPLv3 Community Edition with full companion governance suite (`NOTICE`, `DISCLAIMER.md`, `THIRD_PARTY_NOTICES.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/EDITIONS.md`, `docs/TRADEMARKS.md`).
- **Scale Performance Benchmark (`tests/benchmark_scale.py`):** Benchmarked linking 5,000 requirements to 20,000 test artifacts with execution verdicts in 0.66 seconds.
