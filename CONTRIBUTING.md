# Contributing to ReqTrace (`CONTRIBUTING.md`)

Thank you for your interest in contributing to **ReqTrace Community Edition**, an open-core project stewarded by **Idea To Fact LLC**!

---

## 1. Contributor License Agreement (CLA v1.0) & Dual-Licensing Policy

ReqTrace is distributed under an **open-core dual-licensing model**:
- The open-source Community Edition is licensed under the **GNU Affero General Public License Version 3 (AGPLv3)**.
- Commercial Pro and Enterprise Editions are licensed under proprietary commercial terms by **Idea To Fact LLC**.

To ensure that Idea To Fact LLC can continue to offer ReqTrace under both the AGPLv3 and commercial or alternative license terms, all external contributors must agree to the Contributor License Agreement (CLA v1.0) below prior to having a pull request merged.

### Individual Contributor Grant of Rights (CLA Version 1.0)
By submitting a pull request, patch, code, or documentation ("Contribution") to this repository, you agree to the following terms:
1. **Retention of Ownership**: Subject to the non-exclusive licenses granted herein, you retain full copyright and patent ownership of your original Contribution.
2. **Grant of Copyright License**: You hereby grant to **Idea To Fact LLC**, its affiliates, successors, and assigns a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable, transferable, and sublicensable copyright license to reproduce, prepare derivative works of, publicly display, publicly perform, sublicense, and distribute your Contribution and such derivative works under open-source licenses (including GNU AGPLv3), commercial or proprietary licenses (including Commercial Pro and Enterprise Editions), or any other license terms Idea To Fact LLC chooses.
3. **Grant of Patent License**: You hereby grant to **Idea To Fact LLC**, its affiliates, successors, and assigns a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable, transferable, and sublicensable patent license (including the right to sublicense to direct and indirect customers, distributors, and end users) to make, have made, use, offer to sell, sell, import, and otherwise transfer or exploit the Contribution, alone or in combination with ReqTrace or any commercial or other derivative work.
4. **Original Authorship & Clean-Room Warranty**: You represent and warrant that you are the sole author of the Contribution (or otherwise hold full legal authority to grant the rights above), that your Contribution does not violate any employment, consulting, or academic IP agreement, and that your Contribution does not incorporate or derive from any third-party code, incompatible copyleft material (such as GPL, AGPL, or LGPL third-party code), or unverified/restricted AI-generated code that would encumber Idea To Fact LLC's ability to distribute the Contribution under both AGPLv3 and proprietary commercial or other licenses.
5. **Waiver of Moral Rights**: To the maximum extent permitted by applicable law, you waive and agree not to assert any moral rights (*droit moral*) in your Contribution against Idea To Fact LLC, its affiliates, successors, assigns, or licensees, and agree that Idea To Fact LLC may modify, refactor, or omit your Contribution in any open-source, commercial, or other distribution.
6. **Voluntary, Non-Confidential & No Revenue Share**: Contributions are submitted voluntarily without expectation of financial compensation, royalties, or revenue sharing from Commercial Editions, are non-confidential, and Idea To Fact LLC is under no obligation to accept, merge, maintain, or commercialize any Contribution.
7. **Governing Law & Venue**: This CLA is governed by and construed in accordance with the laws of the jurisdiction of formation of **Idea To Fact LLC**, without regard to conflict-of-law principles, and any dispute arising hereunder shall be brought exclusively in the state or federal courts located in that jurisdiction (unless otherwise required by applicable mandatory law).
8. **Developer Certificate of Origin (DCO)**: You certify that every commit in your pull request includes a signed-off-by line (`git commit -s`), certifying compliance with the Developer Certificate of Origin (https://developercertificate.org/).

### Interaction Between DCO and CLA
- The **DCO** confirms the developer's chain of origin and certification that the code is submitted under open-source terms.
- The **CLA** grants Idea To Fact LLC the broad, sublicensable rights necessary to maintain the dual-licensing structure, defend the codebase in litigation, and distribute proprietary Commercial Pro and Enterprise builds.
- **Pledge to Contributors**: Idea To Fact LLC pledges that published releases of ReqTrace Community Edition incorporating accepted Contributions will remain available under an OSI-approved open-source license (currently `AGPL-3.0-only`), while Idea To Fact LLC retains unrestricted rights to distribute derivative works under commercial/proprietary licenses and to evolve or refactor future versions.

### Corporate CLA (CCLA)
If you are an employee contributing work created within the scope of your employment, or if your employer owns or claims rights in the intellectual property you produce, your organization must execute a **Corporate CLA (CCLA)** before contributions can be accepted.
- Please email `cla@ideatofact.com` with your organization's legal contact to request and execute the Corporate CLA.

### Pull Request CLA Acceptance
> [!IMPORTANT]
> **No external pull request will be merged without recorded CLA acceptance (and a signed CCLA where applicable) plus DCO `Signed-off-by` commit trailers.**
> First-time contributors must record acceptance of CLA v1.0 via the repository's CLA signing mechanism (once enabled on GitHub PRs) or by emailing signed confirmation to `cla@ideatofact.com`.

---

## 2. Core Architectural Principles

Every contribution to ReqTrace must uphold three non-negotiable guarantees:

1. **Local-First & Air-Gapped**: Zero unauthorized external API calls, zero remote telemetry, and zero unverified cloud dependencies. All trace operations, parsing, and report generation must function completely offline.
2. **Evidence-First Grounding**: Every trace link must ground in explicit, verifiable source artifacts (file paths, line numbers, test IDs, commit hashes, or requirement IDs).
3. **Deterministic Core Scoring**: Static tag extractors, AST token analyzers, and fuzzy window algorithms must produce bit-for-bit identical results on identical input sets across runs.

---

## 3. Developer Environment Setup & Standards

### Python Environment
ReqTrace requires Python 3.11 or 3.12:
```bash
# Clone the repository
git clone https://github.com/ideatofact/reqtrace.git
cd reqtrace

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Code Style & Static Typing
- Code formatting follows PEP 8 standards (max line length: 120 characters).
- Type annotations are required for all function signatures and public APIs.
- Type checking is validated with `pyright` (see [`pyrightconfig.json`](pyrightconfig.json)).

### Pre-Commit & Verification Checklist
Before submitting a pull request, run the complete local verification suite:
```bash
# 1. Run all unit and integration tests
pytest tests -v

# 2. Run scale performance benchmark
python tests/benchmark_scale.py

# 3. Verify clean-room license guardrails
pytest tests/test_license_guardrails.py -v
```

---

## 4. Open-Core Boundary & Product Editions

To maintain a clean boundary between the AGPLv3 Community Edition and commercial tiers, please review the canonical editions matrix in **[`docs/EDITIONS.md`](docs/EDITIONS.md)** before designing new features.

- Published releases of the Community Edition remain available under the GNU AGPLv3; Idea To Fact LLC retains full discretion to make different licensing or product decisions for future versions.
- Features planned for Commercial Pro and Enterprise tiers (such as live DOORS DXL/OSLC sync, team review servers, and DO-330 qualification kits) are maintained in separate commercial packages.

---

## 5. Community & Safety

- Please review our [Code of Conduct](CODE_OF_CONDUCT.md).
- To report security vulnerabilities or air-gap defects, please follow the coordinated disclosure policy in [SECURITY.md](SECURITY.md).
