# 🎯 ReqTrace (`reqtrace`)
### Grounded Requirements Traceability & Audit Gap Copilot for Regulated Engineering
**Idea To Fact LLC** | **AGPLv3 Community Edition & Commercial Dual-License**  
**Status: v0.2.0 (Local Verification Workspace)**

`reqtrace` is an open-core, air-gapped requirements traceability and audit verification copilot built specifically for regulated and safety-critical engineering domains (**DO-178C, DO-254, ISO 26262, IEC 62304**).

It ingests industry-standard specifications (ReqIF XML, Word `.docx`, CSV matrices, and DOORS/Polarion offline file exports), test suites (PyTest with `@pytest.mark.req` and docstring tags, C/C++ GoogleTest and Catch2 harnesses, and Gherkin feature files), and dynamic test execution results (JUnit XML), providing:
- **Hierarchical Traceability:** System Requirements (SRD) $\rightarrow$ High-Level Requirements (HLR) $\rightarrow$ Low-Level Requirements (LLR) $\rightarrow$ Source Code $\longleftrightarrow$ Test Cases.
- **Local Web Cockpit (`reqtrace ui`):** Air-gapped, zero-egress single-user web application with port-scoped session security, anti-DNS rebinding, CSRF protection, and strict Content-Security-Policy headers blocking inline scripts and styles.
- **Candidate Triage Queue & Human Sign-Off:** Review prospective links with provenance confidence scores and match reasons; approve, reject (with mandatory rationale), or waive links with audit-trail persistence.
- **Incremental Analysis Coordinator:** Decoupled analysis dirty flags; review submissions execute an instant sub-millisecond status recomputation fast-path without re-running $O(N \times M)$ text linkers.
- **Drag-and-Drop Ingestion Wizard:** Dual dropzones in the web UI for specifications and test suites with format validation, atomic write guarantees, and 25MB safety caps.
- **Workspace Lifecycle Management:** Option B workspace creation (target directory must exist on disk), `.reqtrace/workspace.json` manifest abstraction, `.reqtrace/project.json` metadata, and recent workspace tracking.
- **Unified Export Service & Print View:** On-demand exports for CSV, standard ReqIF XML with `<SPEC-RELATION>` elements, standalone interactive HTML, raw JSON dumps, and non-virtualized Print Views (`/print`).
- **Deterministic Assertion Grounding:** Deterministic fuzzy text windowing (`rapidfuzz`) with character-exact span citations linking requirements directly to verified assertion statements in test code.
- **Specification Delta Analysis (`reqtrace diff`):** Automatic detection of modified requirements across specification revisions and flagging of stale trace links.
- **Event-Sourced Review Persistence:** Append-only review overlay store (`.reqtrace/reviews.jsonl`) backed by atomic multi-process file locking that survives link re-computations and merges cleanly across Git branches.
- **Dynamic Verdict Linkage:** Integrates JUnit XML pass/fail/skip test execution results so unexecuted, skipped, or failing tests cannot falsely substantiate requirements. Skipped tests are explicitly flagged as `UNVERIFIED` because an unexecuted or skipped test typically cannot provide verification credit in a safety audit.
- **Zero-Egress Air-Gap Compliance:** The core deterministic engine runs 100% locally with zero cloud dependencies and zero external network transmission.

---

## ⚡ Scale Performance Benchmark

Benchmarked on an 8-core CPU workstation in an air-gapped configuration:
- **5,000 requirements** linked against **20,000 test cases** with execution verdicts in **0.66 seconds** (over 60,000 links/second).
- **Sub-millisecond review sign-off**: Incremental review overlay updates recompute canonical status in **< 1.5ms** without invoking text linkers.
- Zero outbound network calls during core deterministic execution.

---

## 🖥️ Local Web Cockpit (`reqtrace ui`)

Launch the local air-gapped workspace cockpit directly from your terminal:

```bash
# Launch on default port (8765) and automatically open local browser
reqtrace ui

# Specify a custom project directory and port
reqtrace ui --workspace ./my_project --port 8766

# Headless mode (do not automatically open browser)
reqtrace ui --no-browser
```

*(If running on Windows PowerShell without activating `.venv`, run `.\.venv\Scripts\reqtrace ui`).*

### Cockpit Capabilities:
1. **Workspace Switcher:** Select from recently opened projects, open an existing folder, or create a new ReqTrace workspace (`.reqtrace/workspace.json` manifest). Target directories must already exist on disk (Option B policy).
2. **Dual Dropzone Ingestion Wizard:** Drag-and-drop specification files (`.reqif`, `.csv`, `.docx`) and test implementations/results (`junit.xml`, PyTest, C++, Gherkin) directly into the UI with instant parsing and error diagnostics.
3. **Traceability Matrix & Candidate Triage:** Toggle between the live audit matrix and the Candidate Triage Queue. Inspect match confidence (e.g. 88%), match strategy (`tag_exact`, `rapidfuzz_window`, `heuristic`), and exact match reasons.
4. **Human Review Sign-Off:** Modal dialog supporting one-click Approve, Reject (with mandatory rejection reason), or Waive (with verification justification). All decisions append to `.reqtrace/reviews.jsonl` with multi-process `FileLock` protection.
5. **Unified Export & Print View:** Export verified deliverables as CSV, ReqIF XML (`<SPEC-RELATION>`), interactive standalone HTML, or raw JSON, or launch the clean, non-virtualized Print View (`/print`) styled with `@media print` rules.

---

## 🐳 Docker Quick Start

For air-gapped containerized environments, ReqTrace provides automated launch scripts and a hardened Dockerfile (unprivileged user `reqtrace` UID 10001, rootless, zero outbound telemetry):

```powershell
# Windows PowerShell (Recommended: runs in background and opens your browser):
.\docker-run.ps1 -Detach

# Or run in foreground with live terminal logs:
.\docker-run.ps1

# Custom workspace directory and alternate port:
.\docker-run.ps1 -Workspace "C:\Projects\FlightControls" -Port 8766 -Detach
```

```bash
# Linux / macOS:
./docker-run.sh -d      # Background mode
./docker-run.sh         # Foreground mode
```

Or using standard Docker CLI:
```bash
docker build -t reqtrace:0.2.0 .
docker run -d --name reqtrace-cockpit -p 127.0.0.1:8765:8765 -v "$(pwd)":/workspace reqtrace:0.2.0
```

Once started, the container will appear as **`reqtrace-cockpit`** under Docker Desktop's **Containers** tab, and the cockpit is reachable at `http://localhost:8765`.
- **Automated Login**: `.\docker-run.ps1 -Detach` opens your browser with a valid single-use ticket automatically.
- **Manual / Docker Desktop Login**: Visiting `http://localhost:8765` presents the Authentication Gateway where you can paste either the `Ticket` or `Launch URL` from **Containers → Logs** (`docker logs reqtrace-cockpit`).
- **Mint a Fresh Ticket Anytime**: Run `docker exec reqtrace-cockpit reqtrace ticket` (no container restart needed).

See [`docs/DOCKER.md`](docs/DOCKER.md) for the complete guide, including offline `docker save` / `docker load` workflows for classified networks, headless CLI execution, and Kubernetes deployment manifests.

---

## 🚀 CLI Quick Start

```bash
# Initialize ReqTrace workspace configuration
reqtrace init

# Ingest system requirements (ReqIF XML, Word .docx, or CSV)
reqtrace ingest demo_assets/spec.reqif

# Scan test suites (PyTest or C++ GoogleTest) and attach JUnit execution verdicts
reqtrace scan tests/ --junit test-results/junit.xml

# Compute bidirectional traceability matrix
reqtrace link --output trace_matrix.csv

# Check compliance in CI/CD (exits with code 1 on orphans, unlinked tests, or failed/skipped tests)
reqtrace check --min-coverage 95.0

# Print executive audit summary dashboard
reqtrace audit-summary

# Generate interactive standalone air-gapped HTML dashboard
reqtrace report --format html --out rtm_report.html

# Export traceability back to standard ReqIF XML with <SPEC-RELATION> elements
reqtrace export-reqif --template demo_assets/spec.reqif --matrix trace_matrix.csv --out traced_spec.reqif

# Launch the interactive local cockpit
reqtrace ui
```

---

## 🏛️ Product Editions & Governance

ReqTrace is distributed under an **open-core dual-licensing model**:
- **Community Edition (AGPLv3)**: 100% open-source local CLI and single-user web UI (`reqtrace ui`), workspace manager, drag-and-drop ingestion wizard, candidate triage queue, single-reviewer sign-off, unified export service, deterministic link engine, ReqIF/CSV/Word `.docx` ingestion, PyTest/C++/Gherkin AST scanning, orphan and unlinked test detection, delta diff analysis, and standalone HTML reports. Free for all users under the terms of the GNU AGPLv3.
- **Commercial Pro Edition**: Self-hosted team server (deployed on your private infrastructure), centralized review database with concurrent conflict resolution, requirement modification impact reports, executive PDF audit binders, and priority support.
- **Commercial Enterprise Edition**: Live IBM DOORS Classic (DXL), DOORS Next (OSLC), and Siemens Polarion ALM synchronization, multi-user cryptographic sign-offs, role-based DER workflows, and a **Tool Qualification Support Kit (TQP / TAS / TOR templates & test suite)** to assist applicant qualification under DO-330 and ISO 26262 for submission to certification authorities and independent assessors (such as the FAA, EASA, or TÜV SÜD). *(ReqTrace and Idea To Fact LLC are not affiliated with, sponsored by, or endorsed by the FAA, EASA, FDA, or TÜV SÜD.)*

A commercial license is available for organizations requiring proprietary embedding, commercial distribution, or exemption from AGPLv3 copyleft terms.

See [`docs/EDITIONS.md`](docs/EDITIONS.md) for the complete tier comparison matrix.

---

## ⚖️ Licensing & Legal

- **Core Community Edition License**: [GNU Affero General Public License v3.0](LICENSE) (SPDX: `AGPL-3.0-only`).
- **Commercial Terms Framework**: [docs/commercial/COMMERCIAL_TERMS_FRAMEWORK.md](docs/commercial/COMMERCIAL_TERMS_FRAMEWORK.md) (Commercial Pro & Enterprise dual-licensing terms).
- **Legal & Safety Disclaimer**: [DISCLAIMER.md](DISCLAIMER.md) (ReqTrace is an engineering decision-support tool; human-in-the-loop engineering sign-off is required).
- **Privacy & Local Data Handling**: [PRIVACY.md](PRIVACY.md).
- **Third-Party Notices**: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) (Declared direct dependencies in `pyproject.toml` are checked against a permissive MIT/Apache/BSD/PSF allowlist via `tests/test_license_guardrails.py`).
- **Trademark Policy**: [docs/TRADEMARKS.md](docs/TRADEMARKS.md).
- **Contributing & CLA**: [CONTRIBUTING.md](CONTRIBUTING.md).
- **Security Policy**: [SECURITY.md](SECURITY.md).
- **Code of Conduct**: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

For commercial licensing, enterprise evaluations, or DO-330 tool qualification support kits, contact **Idea To Fact LLC** at [licensing@ideatofact.com](mailto:licensing@ideatofact.com) or visit [https://ideatofact.com](https://ideatofact.com).
