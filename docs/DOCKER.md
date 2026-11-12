# 🐳 ReqTrace Docker Deployment & Operations Guide

This guide provides end-to-end instructions for running and managing **ReqTrace Community Edition v0.2.0** using Docker and Docker Desktop.

---

## 1. Prerequisites

1. **Docker Desktop**: Ensure Docker Desktop is installed and running on your machine.
   - [Download Docker Desktop for Windows / macOS / Linux](https://www.docker.com/products/docker-desktop/)
   - Verify it is running by checking for the Docker whale icon in your system tray, or by opening a terminal and running:
     ```powershell
     docker version
     ```
2. **Project Directory**: Have your engineering project directory ready (with your requirements and test files). Target directories must already exist on disk pursuant to ReqTrace's **Option B Policy**.

---

## 2. Quick Start (Using Automated Scripts)

ReqTrace provides automated launch scripts that handle image builds, Windows path sanitization, stale container cleanup, and volume bind-mounting automatically.

### On Windows (PowerShell)

#### Background / Detached Mode (Recommended):
Runs the container in the background so it remains visible under Docker Desktop's **Containers** tab, and automatically opens the cockpit in your browser:
```powershell
.\docker-run.ps1 -Detach
```

#### Foreground / Interactive Mode:
Runs in the current terminal window with live server logs (press `Ctrl+C` to stop):
```powershell
.\docker-run.ps1
```

#### Custom Workspace and Port:
Mount a specific project directory and bind to an alternate port:
```powershell
.\docker-run.ps1 -Workspace "C:\Projects\FlightControls" -Port 8766 -Detach
```

---

### On Linux / macOS (Bash)

```bash
# Make script executable:
chmod +x docker-run.sh

# Run in background (detached):
./docker-run.sh -d

# Or run in foreground with a specific project path:
./docker-run.sh /path/to/project
```

---

## 3. Viewing in Docker Desktop

Once launched, ReqTrace is fully integrated into the Docker Desktop GUI:

1. **Containers Tab**:
   - You will see a container named **`reqtrace-cockpit`** with a green dot indicating **RUNNING / HEALTHY**.
   - **Port**: `8765:8765` is mapped and clickable.
   - **Actions**: You can view live container logs, inspect file mounts, pause, restart, or stop the container with single clicks.
2. **Images Tab**:
   - The verified image **`reqtrace:0.2.0`** is listed with a size of ~136 MB (compressed) / ~560 MB (unpacked runtime).

---

## 4. Accessing the Web Cockpit & Authentication Tickets

When the container launches, ReqTrace binds to `0.0.0.0:8765` inside the container and generates a cryptographically signed, single-use launch ticket (valid for **1800 seconds / 30 minutes** in Docker by default).

### Option A: Automated Launch (`docker-run.ps1 -Detach` / `docker-run.sh -d`)
The script automatically waits for container startup, extracts the `Launch URL` and `Ticket` from logs, prints both in your terminal, and opens your default browser directly to the authenticated cockpit.

### Option B: Clicking Port `8765:8765` in Docker Desktop (or Opening `http://localhost:8765`)
1. Visiting `http://localhost:8765` without a session cookie displays the **ReqTrace Authentication Gateway** (no `401 Unauthorized` dashboard errors).
2. Retrieve your **Ticket** or **Launch URL** from **Docker Desktop → Containers → `reqtrace-cockpit` → Logs** (or run `docker logs reqtrace-cockpit`):
   ```text
   ====================================================================
     🎯 ReqTrace Local Cockpit
     Status: Zero-Egress Air-Gapped Local Web Application
     Workspace:    /workspace
     Listening on: http://0.0.0.0:8765
     Launch URL:   http://localhost:8765/login?ticket=<one-time-token>
     Ticket:       <one-time-token>
     Note: Ticket valid for 1800s. Scoped cookie: reqtrace_session_8765
     Hint: Mint another ticket anytime via: reqtrace ticket
   ====================================================================
   ```
3. Paste **either** the standalone `Ticket` **or** the entire `Launch URL` into the Authentication Gateway box and click **Unlock Cockpit** (or click the `Launch URL` link directly).
4. Once authenticated, the ticket exchanges for an `HttpOnly`, `SameSite=Strict` session cookie valid for **24 hours**.

### Option C: Generating a Fresh Ticket Without Restarting the Container
If your initial ticket expired or was already consumed (e.g., signing in from a second browser profile), generate a fresh single-use ticket immediately via Docker `exec`:
```bash
docker exec reqtrace-cockpit reqtrace ticket
```
*(In Docker Desktop GUI, you can also open the container's **Exec** tab and run `reqtrace ticket`.)*

---

## 5. Standard Docker CLI Commands (Without Scripts)

If you prefer using pure Docker CLI commands:

### 1. Build the Hardened Image
```bash
docker build -t reqtrace:0.2.0 .
```

### 2. Run in the Background
```powershell
# Windows PowerShell:
docker run -d --name reqtrace-cockpit -p 127.0.0.1:8765:8765 -v "${PWD}:/workspace" reqtrace:0.2.0

# Linux / macOS:
docker run -d --name reqtrace-cockpit -p 127.0.0.1:8765:8765 -v "$(pwd)":/workspace reqtrace:0.2.0
```

### 3. View the Launch URL
```bash
docker logs reqtrace-cockpit
```

### 4. Stop the Container
```bash
docker stop reqtrace-cockpit
docker rm reqtrace-cockpit
```

---

## 6. Air-Gapped & Classified Offline Operation

In defense labs or qualification enclaves with zero external internet connectivity:

### Step 1: Export Image on an Internet-Connected Staging Machine
```bash
docker save reqtrace:0.2.0 | gzip > reqtrace-0.2.0.tar.gz
```

### Step 2: Transfer Archive via Authorized Secure Media
Transfer `reqtrace-0.2.0.tar.gz` to the isolated workstation or enclave server.

### Step 3: Load Image on the Air-Gapped Host
```bash
docker load < reqtrace-0.2.0.tar.gz
```

### Step 4: Run with Outbound Network Disabled
```bash
docker run -d \
  --name reqtrace-cockpit \
  --network none \
  -p 127.0.0.1:8765:8765 \
  -v /path/to/project:/workspace \
  reqtrace:0.2.0
```
*Note: `--network none` completely disables outbound networking inside the container while Docker Desktop maps `localhost:8765` on the host, guaranteeing 100% compliance with **Architectural Invariant #1 (Zero Outbound Egress)**.*

---

## 7. Running Headless CLI Commands in Docker

You can execute any ReqTrace CLI tool directly against your project files by passing commands to the container:

```bash
# Ingest requirements specification (ReqIF, Word .docx, CSV)
docker run --rm -v "$(pwd)":/workspace reqtrace:0.2.0 ingest spec.reqif

# Scan test suites and attach JUnit execution verdicts
docker run --rm -v "$(pwd)":/workspace reqtrace:0.2.0 scan tests/ --junit junit.xml

# Generate bidirectional trace matrix CSV
docker run --rm -v "$(pwd)":/workspace reqtrace:0.2.0 link --output trace_matrix.csv

# Run CI/CD quality gate check
docker run --rm -v "$(pwd)":/workspace reqtrace:0.2.0 check --min-coverage 95.0

# Generate standalone interactive HTML audit report
docker run --rm -v "$(pwd)":/workspace reqtrace:0.2.0 report --format html --out report.html

# View executive audit scorecard
docker run --rm -v "$(pwd)":/workspace reqtrace:0.2.0 audit-summary
```

---

## 8. Security & Hardening Specifications

| Attribute | Specification | Standard / Benefit |
| :--- | :--- | :--- |
| **User Privileges** | Non-root service user `reqtrace` (UID 10001, GID 10001) | CIS Docker Benchmark §4.1 |
| **Rootless Execution** | No root or administrative escalation within container | NIST SP 800-190 |
| **Data Sovereignty** | Direct volume bind-mount to `/workspace`; all data persists locally | DO-178C Tool Qualification |
| **Anti-DNS Rebinding** | `LocalhostSecurityMiddleware` validates `Host` headers strictly | OWASP Top 10 API Security |
| **CSRF Defense** | Origin and Referer verified on all mutating HTTP requests | RFC 7231 / CWE-352 |
| **Single-Use Tickets** | Launch tickets are single-use (1800s TTL in Docker, 60s CLI default) and can be freshly minted via OS-operator `reqtrace ticket` | CWE-384 Session Fixation Guard |
