# Privacy & Local Data Handling Policy (`PRIVACY.md`)

**ReqTrace — AGPLv3 Community Edition**  
**Stewarded by Idea To Fact LLC**

---

## 1. Zero-Collection & Zero-Telemetry Guarantee

ReqTrace Community Edition is architected to operate **100% locally** on user-controlled hardware or private infrastructure:
- **No Vendor Data Collection**: Idea To Fact LLC does **not** collect, transmit, store, or receive telemetry, crash reports, usage analytics, requirements text, test source code, or audit artifacts from ReqTrace Community Edition.
- **No Vendor Cloud Accounts**: Running the CLI (`reqtrace`) or Local Web Cockpit (`reqtrace ui`) requires no user account, license phone-home, or internet access in standard deterministic operation.

---

## 2. Local Workspace & Runtime Artifacts

All data processed by ReqTrace remains on the host filesystem under the user's control:
- **Workspace Store (`.reqtrace/`)**:
  - `.reqtrace/workspace.json` and `.reqtrace/project.json` store workspace configuration and project metadata (project name, target standard, specification version, baseline ID).
  - `.reqtrace/reviews.jsonl` stores human review decisions (`approved`, `rejected`, `waived_analysis`), user-entered reviewer identity strings, timestamps, comments, and reference documents.
  - `requirements.json`, `tests.json`, `links.json`, and generated exports (CSV, ReqIF XML, HTML, JSON) may contain sensitive engineering specifications, source code paths, or test assertions.
- **Operator Runtime State**:
  - `reqtrace ui` writes an ephemeral operator runtime file (`operator_<port>.json` in `~/.reqtrace/` or the OS temp `reqtrace_operator/` directory) containing the loopback port, PID, and a random `operator_secret` (with `0o600` POSIX permissions where supported) to authorize `reqtrace ticket`.
- **Optional Semantic Embedding Cache (`FASTEMBED_CACHE_PATH`)**:
  - When optional semantic extensions (`reqtrace.extensions`) are invoked without pre-staged local model weights, `FastEmbed` downloads `BAAI/bge-small-en-v1.5` weights to its local cache directory. For air-gapped or sovereign enclaves, pre-stage model weights locally and set `FASTEMBED_CACHE_PATH` before execution.

---

## 3. Loopback Browser Cookies (`reqtrace ui`)

When using the Local Web Cockpit (`reqtrace ui`):
- Exchanging a single-use launch ticket sets an **`HttpOnly`, `SameSite=Strict`** port-scoped session cookie named `reqtrace_session_<port>` (default lifetime: 24 hours in memory).
- This cookie is used strictly for local loopback session authentication against the running `reqtrace ui` process and is never transmitted to Idea To Fact LLC or any external domain.

---

## 4. User Responsibilities (FDE, Access Controls & Sanitization)

Because ReqTrace processes engineering specifications, test suites, and compliance logs locally—which may include proprietary IP, personal reviewer names in `.reqtrace/reviews.jsonl`, or export-controlled (ITAR/EAR) technical data—the user and their organization are solely responsible for:
- **Full-Disk Encryption (FDE) & Access Controls**: Protecting local workstations, Docker volumes, and `.reqtrace/` directories with OS access controls and full-disk encryption.
- **Git & Backup Hygiene**: Controlling access to Git repositories and backups containing `.reqtrace/reviews.jsonl` or exported RTMs.
- **Media & SSD Sanitization**: Properly wiping or sanitizing temporary files, browser caches, Docker volumes, and solid-state drives (e.g., per NIST SP 800-88) when decommissioning hardware or rotating classified/regulated workspaces.

---

## 5. Inquiries

For privacy or data-handling questions regarding Commercial Pro or Enterprise Editions, contact:  
**Idea To Fact LLC** — `contact@ideatofact.com` | `https://ideatofact.com`

