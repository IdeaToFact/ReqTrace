# ReqTrace Product Editions & Tier Strategy (`docs/EDITIONS.md`)

This document defines the canonical feature boundary across **ReqTrace Community Edition (AGPLv3)** and **Commercial Editions (Pro & Enterprise)** stewarded by **Idea To Fact LLC**.

---

## 1. Feature Comparison Matrix

| Capability Category | AGPLv3 Community Edition<br>*(Open-Core / Self-Hosted CLI)* | Commercial Pro Edition<br>*(Engineering Teams & Verification Leads)* | Commercial Enterprise Edition<br>*(Regulated Primes, Avionics & Defense Enclaves)* |
| :--- | :---: | :---: | :---: |
| **Licensing** | GNU AGPLv3 (Strict Copyleft) | Commercial EULA / Per-Seat Subscription | Commercial Master Services Agreement (MSA) |
| **Pricing / Access** | Free (Open Source) | Annual Per-Seat Subscription (Contact Sales) | Annual Enclave / Department License (Contact Sales) |
| **Deployment Model** | Local Host OS / GitHub Actions Runner | Customer-Owned Infrastructure (On-Premises Team Server / Private VM) | Air-Gapped High-Security Enclave / Defense Lab Dedicated Appliance |
| **Telemetry & Networking** | 100% Local / Zero Remote Telemetry | Zero Vendor Telemetry / Offline Token Activation | Zero Vendor Telemetry / Hardware-Locked Offline Token |
| **Requirements Ingestion** | ReqIF XML (`.reqif`), CSV, Word (`.docx`), PDF text extraction (`pypdfium2`), DOORS/Polarion file exports | Scanned PDF OCR & Bates Stamping, Advanced Visual Table Extraction, Batch Ingestion Queues | Live IBM DOORS Classic (DXL), IBM DOORS Next (OSLC), and Siemens Polarion ALM Sync |
| **Test Scanning & AST** | PyTest (Python AST), C/C++ GoogleTest & Catch2 harnesses, Gherkin feature files, JUnit XML | Rust (`cargo test`), Go (`go test`), Robot Framework, CUnit | Custom Proprietary Test Harness Adapters, Hardware-in-the-Loop (HIL) Telemetry Connectors |
| **User Interface** | Local Single-User Web UI (`reqtrace ui`): Top-level audit dashboard, matrix grid, evidence drawer, candidate triage queue, single-reviewer sign-off with content-hash binding, workspace lifecycle manager, drag-and-drop ingestion wizard, and unified export service | Self-Hosted Multi-User Team UI: Collaborative review workspace, team dashboard, live ALM viewer | Enterprise Enclave Portal: Air-gapped appliance UI, SAML/SSO role gating, audit log viewer |
| **Traceability & Allocation** | Deterministic Tag Matching, RapidFuzz Windowing, Parent-Child Hierarchy Parsing from ReqIF `<SPEC-RELATIONS>` & CSV `parent_id` | Interactive Multi-Level Allocation Matrix (Visual editor with downstream code AST tracing) | Bi-Directional Multi-Project Allocation Sync (Cross-project enterprise requirement allocation & change propagation) |
| **Review & Sign-Off Store** | Local Git-backed Event Log (`.reqtrace/reviews.jsonl`) with cryptographic content-hash binding | Centralized Multi-Engineer Review DB with Automated Concurrent Conflict Resolution | Multi-User Cryptographic Sign-Offs, Role-Based DER / Lead Reviewer Workflows, Audit Log Immutability |
| **Gap & Orphan Auditing** | CLI & UI Orphan Detection, Unlinked Test Detection, Execution Gap Gating (`reqtrace check`) | Team Gap Resolution Workflows, Automated Test Suggestion Prompts | Certification Readiness Gatekeeper & Formal Audit Packager |
| **Baseline Delta & Diff** | Spec Structural Diff Engine (`reqtrace diff`), Stale-Link Flagger, CLI Terminal Diff & Static HTML Report | Visual Side-by-Side Spec Diff Viewer, Requirement Modification Impact Reports | Automated Re-Verification Impact Planning, Engineering Change Order (ECO) Audits |
| **Reports & Deliverables** | Standalone Single-File HTML Dashboard, CSV RTM, Standard ReqIF XML Export (`<SPEC-RELATION>`), JSON Dump, Non-Virtualized Print View (`/print`) | Executive PDF Audit Binders, JIRA / Azure DevOps Trace Export | **Tool Qualification Support Kit (TQP / TAS / TOR templates & test suite)** |
| **Administration & Security** | Open-source CLI, Standard Permissive Dependencies | Priority Engineering Support, Automated Security Patch Advisories | Single Sign-On (SAML/SSO), Role-Based Access Control (RBAC), Audit Log Immutability for DO-178C & FDA Part 11 |

---

## 2. Open-Core Governance & Relicensing Guarantee

1. **Permanence of Community Code**: We will not remove or paywall any capability present in a tagged Community release. Features released under the GNU AGPLv3 in this repository remain permanently open source under the AGPLv3 for those published Community Edition versions.
2. **Direction of Code Movement**: Features may be moved from Commercial editions *down* into the Community Edition over time, but features in the Community Edition will never be moved *up* to paywall existing open-source capabilities.
3. **Interoperability & Copyleft Boundary**:
   - **Arm's-Length Interchange (Separate Works)**: Independent proprietary test harnesses, CAD tools, or ALM connectors that remain separate programs and exchange data with unmodified ReqTrace solely via arm's-length CLI invocations or standard serialization files (e.g., ReqIF XML, CSV, JUnit XML, JSON) are treated as separate works, provided they do not modify, link into, or form a combined derivative work with ReqTrace.
   - **Distributed Derivatives & Network Interaction (AGPLv3 §13)**: Creating or distributing derivative works of ReqTrace, embedding ReqTrace inside proprietary software, or operating a modified ReqTrace instance as a hosted network service accessible to users triggers GNU AGPLv3 copyleft and §13 source-availability obligations unless a separate Commercial License is obtained from Idea To Fact LLC.
   - *Note on Internal Modules:* The internal `reqtrace/extensions/` package is reserved for optional local semantic runtimes (e.g., BM25 and ONNX embeddings) and is governed by the AGPLv3 terms of this repository.
4. **Commercial Code Repository**: Commercial Pro and Enterprise components are developed, packaged, and distributed from a separate, private repository (`reqtrace-commercial`) under proprietary commercial terms.

---

## 3. Tool Qualification Support Statement (DO-330 / ISO 26262)

In regulated systems engineering (DO-178C, DO-254, ISO 26262, IEC 62304), **a software tool cannot be certified in isolation.** Qualification is conducted on a per-project basis by the applicant and accepted by the certification authority or independent assessment body (such as the FAA, EASA, or TÜV SÜD) pursuant to RTCA DO-330 / ISO 26262-8 Clause 11. *(ReqTrace and Idea To Fact LLC are not affiliated with, sponsored by, or endorsed by the FAA, EASA, FDA, or TÜV SÜD.)*

The **Commercial Enterprise Edition** provides a **Tool Qualification Support Kit** designed to assist applicant qualification:
- Tool Qualification Plan (TQP) templates
- Tool Operational Requirements (TOR) matrices
- Tool Accomplishment Summary (TAS) documentation
- Automated Tool Qualification Test Suite with structural statement and branch coverage reports
- Audit trail and electronic signature controls supporting FDA 21 CFR Part 11 compliance

These qualification artifacts support enterprise engineering teams in completing DO-330 / ISO 26262 tool qualification without authoring operational test cases from scratch.

---

## 4. Commercial Licensing Inquiries

For commercial pricing, team evaluations, or tool qualification support kits:
- **Idea To Fact LLC**
- Website: `https://ideatofact.com`
- Email: `licensing@ideatofact.com`
