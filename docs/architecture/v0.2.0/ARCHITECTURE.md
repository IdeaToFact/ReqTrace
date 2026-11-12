# ReqTrace v0.2.0: Canonical Architecture Package

This document defines the canonical architecture specification for **ReqTrace v0.2.0 (Local Verification Workspace)**. It serves as the authoritative blueprint for engineering teams, safety certification auditors (DO-178C, DO-254, ISO 26262, IEC 62304), open-core contributors, and system operators.

---

## 1. High-Level Product Architecture

ReqTrace operates as a local-first, air-gapped verification cockpit. It ingests requirements specifications and test artifacts, deterministically establishes trace links, orchestrates human review sign-offs, and exports defensible audit deliverables.

```mermaid
flowchart TD
    subgraph Personas["Auditors & Engineering Leads"]
        E["Safety Engineer / Developer"]
        A["Certification Auditor (FAA / EASA / TÜV)"]
        V["Verification & Validation (V&V) Lead"]
    end

    subgraph ClientLayer["Local Client Presentation (localhost:8765)"]
        UI["ReqTrace Web UI (SPA)"]
        UI_WS["Workspace Switcher"]
        UI_MAT["Live Traceability Matrix"]
        UI_EVD["Evidence Drawer"]
        UI_QUEUE["Candidate Review Queue"]
        UI_REV["Sign-Off Modal"]
        UI_EXP["Export Center & Print View"]
        
        UI --- UI_WS
        UI --- UI_MAT
        UI --- UI_EVD
        UI --- UI_QUEUE
        UI --- UI_REV
        UI --- UI_EXP
    end

    subgraph AppLayer["FastAPI Application Layer (In-Process Loopback)"]
        SEC["Hardened Security Middleware\n(Anti-DNS Rebinding | CSRF Guard | Port-Scoped Cookie)"]
        API_WS["Workspace API (/api/v1/workspaces)"]
        API_ING["Ingestion API (/api/v1/ingest)"]
        API_REV["Review & Candidate API (/api/v1/reviews)"]
        API_EXP["Export API (/api/v1/export)"]
        API_STAT["Status & Matrix API (/api/v1/matrix)"]
    end

    subgraph DomainLayer["Core Domain Services Layer"]
        WM["WorkspaceManager (Option B Policy)"]
        AC["AnalysisCoordinator (Dirty-Flag Caching)"]
        TL["TraceLinker (Deterministic Tag & RapidFuzz)"]
        CSE["CanonicalStatusEngine (Precedence Model)"]
        RS["ReviewStore (Append-Only Event Ledger)"]
        EM["ExportManager (Multi-Format Service)"]
    end

    subgraph ParserLayer["Multi-Language Parser & Scanner Layer"]
        P_REQIF["ReqIFParser (1.0/1.2 XML)"]
        P_CSV["CSVParser (Tabular Spec)"]
        P_DOCX["DocxParser (Word Tables/Headings)"]
        P_JUNIT["JUnitParser (Dynamic Execution)"]
        P_PY["PythonASTParser (PyTest AST)"]
        P_CPP["CppHarnessParser (GTest / Catch2)"]
        P_GHERK["GherkinParser (BDD Scenarios)"]
    end

    subgraph StorageLayer["Local Workspace Storage (Data Sovereignty)"]
        F_REQS[("requirements.json")]
        F_TESTS[("tests.json")]
        F_REV[(".reqtrace/reviews.jsonl")]
        F_MAN[(".reqtrace/workspace.json")]
        F_PROJ[(".reqtrace/project.json")]
        F_BASE[(".reqtrace/baselines/*")]
    end

    E --> UI
    A --> UI
    V --> UI

    UI --> SEC
    SEC --> API_WS
    SEC --> API_ING
    SEC --> API_REV
    SEC --> API_EXP
    SEC --> API_STAT

    API_WS --> WM
    API_ING --> AC
    API_REV --> RS
    API_REV --> AC
    API_EXP --> EM
    API_STAT --> AC

    AC --> TL
    AC --> CSE
    TL --> ParserLayer
    CSE --> RS

    WM --> StorageLayer
    RS --> F_REV
    AC --> StorageLayer
    EM --> StorageLayer
```

---

## 2. Runtime Component Architecture

The runtime architecture decouples HTTP transport controllers from core domain services and delegates all heavy computational analysis to an incremental `AnalysisCoordinator`.

```mermaid
flowchart TD
    subgraph UI_Tier["Browser UI Tier"]
        DOM["CSP-Compliant DOM Interface"]
        FETCH["Asynchronous Fetch Client"]
        DOM --> FETCH
    end

    subgraph Server_Tier["FastAPI Host Process (uvicorn)"]
        MW["Security Middleware\n(127.0.0.1 Binding | SameSite=Strict Cookie)"]
        
        subgraph Controllers["API Controllers"]
            C_WS["WorkspaceController"]
            C_ING["IngestionController"]
            C_REV["ReviewController"]
            C_EXP["ExportController"]
            C_MAT["MatrixController"]
        end

        subgraph Service_Instances["Domain Service Singletons"]
            WM_INST["WorkspaceManager"]
            RS_INST["ReviewStore\n(FileLock Concurrency Guard)"]
            EM_INST["ExportManager"]
            PARSERS["Parser Registry\n(ReqIF, CSV, DOCX, JUnit, AST, Harness)"]
        end
    end

    subgraph Coordinator_Tier["Analysis & Cache Coordinator"]
        COORD["AnalysisCoordinator"]
        
        subgraph Cache_State["In-Memory State & Dirty Flags"]
            CACHE_REQ["Cached Requirements Index"]
            CACHE_TEST["Cached Test Index"]
            CACHE_CAND["Candidate Link Cache"]
            CACHE_PROV["Provenance Metadata Cache"]
            CACHE_REV["Review Overlay Cache"]
            
            FLAG_REQ{"reqs_dirty?"}
            FLAG_TEST{"tests_dirty?"}
            FLAG_REV{"reviews_dirty?"}
        end
        
        LINKER_EXEC["TraceLinker Engine\n(O(N*M) - Skipped on review changes)"]
        STATUS_EXEC["Status Engine\n(O(N) - Fast-Path <1.5ms)"]
    end

    FETCH --> MW
    MW --> C_WS
    MW --> C_ING
    MW --> C_REV
    MW --> C_EXP
    MW --> C_MAT

    C_WS --> WM_INST
    C_ING --> PARSERS
    PARSERS --> COORD
    C_REV --> RS_INST
    RS_INST --> COORD
    C_EXP --> EM_INST
    C_MAT --> COORD

    COORD --> Cache_State
    FLAG_REQ -- "True" --> LINKER_EXEC
    FLAG_TEST -- "True" --> LINKER_EXEC
    FLAG_REV -- "True" --> STATUS_EXEC
    LINKER_EXEC --> STATUS_EXEC
```

---

## 3. Workspace Storage & Manifest Architecture

ReqTrace workspaces follow strict data sovereignty: all specifications, tests, reviews, and project baselines are stored on the local file system. Target directories must exist prior to workspace creation (**Option B Policy**).

```mermaid
flowchart TD
    subgraph GlobalConfig["Global User Profile (~/.reqtrace/)"]
        G_REG[("workspaces.json\n(Recent Workspaces Registry)")]
    end

    subgraph WorkspaceDir["Active Workspace Root (/path/to/project/)"]
        W_REQ[("requirements.json\n(Canonical Ingested Specs)")]
        W_TEST[("tests.json\n(Extracted Test Artifacts & Verdicts)")]
        
        subgraph DotReqTrace[".reqtrace/ Directory (Metadata & Ledger)"]
            M_WS[("workspace.json\n(Storage Schema Manifest)")]
            M_PRJ[("project.json\n(Project & Baseline Metadata)")]
            M_REV[("reviews.jsonl\n(Append-Only Review Event Ledger)")]
            
            subgraph TmpDir["tmp/"]
                T_UPL["upload-*.tmp (25MB Buffer)"]
            end
            
            subgraph BaselinesDir["baselines/ (Audited Revision Snapshots)"]
                B1["NAV-001/\n(requirements.json, tests.json, reviews.jsonl)"]
                B2["NAV-002/\n(...)"]
                B3["NAV-003/\n(...)"]
            end
        end
    end

    G_REG -. "Tracks" .-> WorkspaceDir
    M_WS --> W_REQ
    M_WS --> W_TEST
    M_WS --> M_PRJ
    M_WS --> M_REV
    M_WS --> BaselinesDir
```

### Directory Tree Layout

```text
workspace-root/
├── requirements.json              # Primary ingested requirements repository
├── tests.json                     # Primary test cases with dynamic execution verdicts
└── .reqtrace/
    ├── workspace.json             # Manifest declaring active schema version and file paths
    ├── project.json               # Project name, spec revision, baseline ID, and timestamps
    ├── reviews.jsonl              # Cryptographically content-bound append-only review ledger
    ├── tmp/                       # Temporary atomic upload buffer
    └── baselines/
        ├── NAV-001/               # Immutable historical audit snapshot Rev A
        │   ├── project.json
        │   ├── requirements.json
        │   ├── tests.json
        │   ├── reviews.jsonl
        │   └── trace_matrix.csv
        ├── NAV-002/               # Historical audit snapshot Rev B
        └── NAV-003/               # Current baseline Rev C
```

---

## 4. Processing Pipeline & Fast-Path Triage Flow

This sequence models the end-to-end lifecycle from specification upload to candidate triage, human sign-off, and status calculation. It visualizes the **Architectural Performance Invariant**: human review sign-offs bypass the $O(N \times M)$ text linker.

```mermaid
flowchart TD
    START([Specification Upload / File Ingest]) --> PARSE["Parse Spec (ReqIF / CSV / Word)"]
    PARSE --> REQ_OBJS["Instantiate Requirement Domain Objects"]
    
    REQ_OBJS --> MARK_REQ["AnalysisCoordinator: Set reqs_dirty = True"]
    MARK_REQ --> RUN_LINK["Invoke TraceLinker Engine"]
    
    subgraph LinkerStrategies["Deterministic Matching Strategies"]
        M_EXACT["Regex & Exact Tag Matcher\n(100% confidence)"]
        M_FUZZY["RapidFuzz Token Windowing\n(Confidence >= 0.70)"]
        M_HEUR["Heuristic Keyword Proximity\n(Structural Context)"]
    end
    
    RUN_LINK --> M_EXACT
    RUN_LINK --> M_FUZZY
    RUN_LINK --> M_HEUR
    
    M_EXACT --> CAND_GEN["Generate Candidate TraceLinks"]
    M_FUZZY --> CAND_GEN
    M_HEUR --> CAND_GEN
    
    CAND_GEN --> PROV["Attach Provenance:\n• Confidence Score (e.g. 0.88)\n• Match Strategy\n• Match Reason Span"]
    
    PROV --> QUEUE["Candidate Review Queue UI"]
    
    subgraph HumanSignOff["Human-in-the-Loop Sign-Off (Engineer / Auditor)"]
        QUEUE --> ACTION{"Reviewer Action"}
        ACTION -- "Approve" --> REV_APP["Create APPROVED ReviewEvent"]
        ACTION -- "Reject" --> REV_REJ["Require Rejection Reason\nCreate REJECTED ReviewEvent"]
        ACTION -- "Waive" --> REV_WAIVE["Require Waiver Rationale\nCreate WAIVED ReviewEvent"]
    end
    
    REV_APP --> ATOMIC_WRITE["Atomic Append to .reqtrace/reviews.jsonl\n(Acquires 10s FileLock)"]
    REV_REJ --> ATOMIC_WRITE
    REV_WAIVE --> ATOMIC_WRITE
    
    ATOMIC_WRITE --> FAST_PATH["AnalysisCoordinator: Set reviews_dirty = True\n(reqs_dirty = False, tests_dirty = False)"]
    
    FAST_PATH --> SKIP_LINKER["Bypass TraceLinker!\nSkip O(N*M) Comparison"]
    SKIP_LINKER --> STATUS_CALC["CanonicalStatusEngine Recompute\nO(N) Execution in < 1.5ms"]
    
    STATUS_CALC --> METRICS["Update Executive Scorecard & Matrix KPIs"]
    METRICS --> END([Audit Readiness Achieved])
```

---

## 5. Unified Export Architecture

The `ExportManager` decouples export formats from web controllers, assembling a consistent point-in-time workspace snapshot before calculating SHA-256 verification hashes for compliance defensibility.

```mermaid
flowchart TD
    REQ_CALL["Client Request: POST /api/v1/export\n{ 'format': 'csv' | 'reqif' | 'html' | 'json' }"] --> EXP_MGR["ExportManager Service"]
    
    EXP_MGR --> SNAPSHOT["Capture Point-in-Time Workspace Snapshot\n(Requirements + Tests + Reviews + Canonical Matrix)"]
    
    SNAPSHOT --> ROUTE_FMT{"Selected Format"}
    
    subgraph Exporters["Format-Specific Exporters"]
        E_CSV["CSVRTMExporter\nBidirectional Trace Matrix"]
        E_REQIF["ReqIFExporter\nInject <SPEC-RELATION> Elements"]
        E_HTML["HTMLReportGenerator\nStandalone Air-Gapped Interactive Report"]
        E_JSON["JSONExporter\nRaw Structured Audit Dump"]
        E_PRINT["Print View Controller\nNon-Virtualized HTML with @media print"]
    end
    
    ROUTE_FMT -- "csv" --> E_CSV
    ROUTE_FMT -- "reqif" --> E_REQIF
    ROUTE_FMT -- "html" --> E_HTML
    ROUTE_FMT -- "json" --> E_JSON
    ROUTE_FMT -- "print" --> E_PRINT
    
    E_CSV --> FILE_GEN["Generate Output File / Stream"]
    E_REQIF --> FILE_GEN
    E_HTML --> FILE_GEN
    E_JSON --> FILE_GEN
    E_PRINT --> FILE_GEN
    
    FILE_GEN --> HASH_CALC["Compute SHA-256 Digest for Export Integrity"]
    HASH_CALC --> RESULT["Construct ExportResult\n{ path, filename, media_type, sha256, record_count }"]
    RESULT --> CLIENT_DL([Stream Deliverable to Auditor])
```

---

## 6. Deployment Architectures

### 6.1 Local Air-Gapped Workstation Deployment

Designed for individual safety engineers working on isolated, classified, or air-gapped workstations without external network connectivity.

```mermaid
flowchart TD
    subgraph Host["Engineer Workstation (Air-Gapped OS: Windows 11 / Linux / macOS)"]
        subgraph Browser["Local User Browser"]
            CLIENT["Web Cockpit UI\nhttp://127.0.0.1:8765/"]
        end

        subgraph Process["ReqTrace In-Process Runtime"]
            SRV["FastAPI / Uvicorn Server\n(IPv4 Loopback 127.0.0.1:8765)"]
            
            subgraph SecurityGuards["Localhost Defense-in-Depth"]
                G_BIND["Strict Loopback Socket (127.0.0.1)"]
                G_TICK["Single-Use Cryptographic Launch Ticket"]
                G_HOST["Host Header Anti-DNS Rebinding Guard"]
                G_CSRF["Origin / Referer Mutating Guard"]
                G_COOKIE["Port-Scoped HttpOnly Cookie"]
                G_CSP["Strict CSP (No Inline Scripts/Styles)"]
            end
            
            ENGINE["ReqTrace Core Engine\n(Linker, Coordinator, Exporter)"]
        end

        subgraph Storage["Local Workspace Filesystem"]
            DISK[("Project Folder\n• requirements.json\n• tests.json\n• .reqtrace/reviews.jsonl")]
        end
    end

    subgraph Untrusted["External World"]
        INTERNET["External Networks / Internet / Telemetry"]
    end

    CLIENT <-->|HTTP Loopback| SRV
    SRV --- SecurityGuards
    SRV <-->|Direct File I/O| DISK
    
    SRV -.-x|BLOCKED BY DESIGN\nArchitectural Invariant #1: Zero Egress| INTERNET
```

---

### 6.2 Docker Desktop / Local Container Deployment

Used in containerized developer environments where developers mount local project folders into a verified, reproducible container image. Helper scripts and container instructions are provided in [`docs/DOCKER.md`](../../DOCKER.md), [`docker-run.sh`](../../../docker-run.sh), and [`docker-run.ps1`](../../../docker-run.ps1).

```mermaid
flowchart TD
    subgraph HostOS["Host Workstation"]
        H_BROWSER["Local Browser (localhost:8765)"]
        H_DIR[("Host Project Directory\nC:\\Projects\\FlightControls\n(requirements.json, tests.json, .reqtrace/)")]
        
        subgraph DockerEngine["Docker Engine (Local Desktop)"]
            subgraph Container["Container: reqtrace:0.2.0\n(Hardened, Unprivileged UID 10001)"]
                C_ENTRY["Entrypoint: reqtrace ui --workspace /workspace --host 0.0.0.0 --port 8765"]
                C_SRV["FastAPI Server"]
                C_FS["/workspace (Bind Mount Target)"]
            end
        end
    end

    H_BROWSER <-->|Port Forward: 8765:8765| C_SRV
    H_DIR <==>|Volume Bind Mount: -v ...:/workspace| C_FS
    C_SRV <--> C_FS
```

---

### 6.3 Air-Gapped Private Kubernetes (K8s) Cluster Deployment

For private defense labs, avionics enclaves, and qualification testing clusters operating behind secure air-gap perimeters.

```mermaid
flowchart TD
    subgraph K8s_Cluster["Secure Air-Gapped Kubernetes Cluster"]
        subgraph Ingress_Tier["Perimeter Ingress & Routing"]
            ING["Internal TLS Ingress Controller\n(e.g., Traefik / NGINX Ingress)"]
            SVC["Kubernetes ClusterIP Service\n(name: reqtrace-svc, port: 8765)"]
        end

        subgraph NetPol["Zero-Egress Network Policy"]
            NP["NetworkPolicy: reqtrace-egress-deny\negress:\n  - to: (empty - DENY ALL OUTBOUND)"]
        end

        subgraph Pod_Workload["Pod: reqtrace-app-deployment"]
            subgraph PodSecurity["Hardened Security Context"]
                SC1["runAsNonRoot: true"]
                SC2["readOnlyRootFilesystem: true"]
                SC3["capabilities: drop: [ALL]"]
            end
            
            subgraph Containers["Application Containers"]
                APP["Container: reqtrace:0.2.0\nCommand: reqtrace ui -w /workspace -p 8765"]
                TMP_VOL[("emptyDir Volume\nMounted at: /tmp\n(SizeLimit: 256Mi)")]
            end
        end

        subgraph PersistentStorage["Cluster Persistent Storage"]
            PV["PersistentVolume (Local SSD / NetApp Trident / CEPH)"]
            PVC[("PersistentVolumeClaim: reqtrace-workspace-pvc\nAccessMode: ReadWriteOnce\nMounted at: /workspace")]
        end

        subgraph Registry["Private Container Registry"]
            HARBOR[("Internal Harbor Registry\nreqtrace:0.2.0 (Signed Image)")]
        end
    end

    subgraph InternalUsers["Enclave Engineers (Internal VPN / LAN)"]
        USER["Auditor / Engineer Browser"]
    end

    USER -->|HTTPS / Internal mTLS| ING
    ING --> SVC
    SVC --> APP
    APP --- PodSecurity
    APP --- NetPol
    APP --> TMP_VOL
    APP <-->|Read / Write| PVC
    PVC --- PV
    HARBOR -. "Image Pull (Offline)" .-> Pod_Workload
```

---

### 6.4 Deployment Security Boundary Model

```mermaid
flowchart LR
    subgraph Zone1["ZONE 1: Presentation Tier"]
        Z1_NAME["User Browser"]
        Z1_TRUST["Trust Level: MEDIUM"]
        Z1_CAP["Capabilities:\n• Renders DOM UI\n• Holds session cookie"]
        Z1_REST["Restrictions:\n• No direct filesystem access\n• Sandboxed execution"]
    end

    subgraph Zone2["ZONE 2: Application Process"]
        Z2_NAME["ReqTrace FastAPI Process"]
        Z2_TRUST["Trust Level: HIGH"]
        Z2_CAP["Capabilities:\n• Ingests specs\n• Links requirements\n• Generates deliverables"]
        Z2_REST["Guards:\n• Anti-DNS rebinding\n• CSRF verification\n• Ticket exchange auth"]
    end

    subgraph Zone3["ZONE 3: Storage Tier"]
        Z3_NAME["Workspace Storage"]
        Z3_TRUST["Trust Level: HIGHEST"]
        Z3_CAP["Data Entities:\n• requirements.json\n• tests.json\n• reviews.jsonl (ledger)\n• baselines/"]
        Z3_REST["Guards:\n• Append-only reviews\n• Multi-process FileLock\n• Atomic temp file writes"]
    end

    subgraph Zone4["ZONE 4: External World"]
        Z4_NAME["External Networks / Cloud"]
        Z4_TRUST["Trust Level: UNTRUSTED"]
        Z4_POL["Policy: STRICT DENY ALL\nZero telemetry, zero remote APIs"]
    end

    Zone1 <-->|HTTP Loopback Only| Zone2
    Zone2 <-->|POSIX / Win32 File Locking| Zone3
    Zone2 -.-x|FIREWALL / POLICY BLOCKED| Zone4
```

---

## 7. Backup and Disaster Recovery Architecture

In regulated environments, traceability data constitutes formal safety records. ReqTrace supports atomic point-in-time snapshots, cryptographic validation manifests, and deterministic rehydration.

### 7.1 Atomic Backup Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Engineer / Automated Job
    participant WM as WorkspaceManager
    participant FL as FileLock System
    participant FS as Local Filesystem
    participant HASH as SHA-256 Engine
    participant ARCH as Tar / Gzip Packager

    Admin->>WM: Trigger Backup Request (CLI or Workspace Snapshot)
    WM->>FL: Acquire Exclusive Lock (.reqtrace/reviews.jsonl.lock)
    Note over FL: Ensures no in-flight human reviews write during snapshot
    
    WM->>FS: Stage Files for Snapshot
    Note over FS: • requirements.json<br/>• tests.json<br/>• .reqtrace/workspace.json<br/>• .reqtrace/project.json<br/>• .reqtrace/reviews.jsonl<br/>• .reqtrace/baselines/*
    
    WM->>HASH: Compute SHA-256 for Each Staged Artifact
    HASH-->>WM: Generate backup-manifest.json with File Checksums
    
    WM->>ARCH: Package Files + Manifest into Archive
    ARCH-->>FS: Write backup_YYYYMMDD_HHMMSS.tar.gz
    
    WM->>FL: Release Lock
    WM-->>Admin: Backup Complete: { ArchivePath, SHA256, Timestamp }
```

---

### 7.2 Restoration, Integrity Validation & Rehydration Workflow

```mermaid
flowchart TD
    START([Restoration Initiated]) --> INPUT["Provide Backup Archive\n(backup_YYYYMMDD_HHMMSS.tar.gz)"]
    INPUT --> UNPACK["Extract to Clean Target Directory"]
    
    UNPACK --> MAN_CHECK{"Is backup-manifest.json Present?"}
    MAN_CHECK -- "No" --> ERR_CORRUPT["FAIL: Corrupt Backup Package\nMissing cryptographic manifest"]
    MAN_CHECK -- "Yes" --> HASH_VERIFY["Verify SHA-256 Checksum of Every Extracted File"]
    
    HASH_VERIFY --> HASH_MATCH{"All Checksums Match Manifest?"}
    HASH_MATCH -- "No" --> ERR_TAMPER["FAIL: Tamper Detected or Bit Rot\nFile hash discrepancy detected"]
    HASH_MATCH -- "Yes" --> SCHEMA_CHECK["Validate Workspace Manifest (.reqtrace/workspace.json)"]
    
    SCHEMA_CHECK --> REV_AUDIT["Audit Review Overlay (.reqtrace/reviews.jsonl)"]
    REV_AUDIT --> HASH_BIND{"Validate Content Hashes:\nDo review hashes match current requirement text?"}
    
    HASH_BIND -- "Mismatch" --> WARN_DRIFT["Flag Stale Reviews:\nSpecification drift detected between backup and spec"]
    HASH_BIND -- "Valid" --> HYDRATE["AnalysisCoordinator Hydration"]
    WARN_DRIFT --> HYDRATE
    
    HYDRATE --> REINDEX["Mark Dirty Flags:\nspecs_dirty = True, tests_dirty = True, reviews_dirty = True"]
    REINDEX --> EXEC_RECON["Execute Full Deterministic Trace & Canonical Status Engine"]
    EXEC_RECON --> VERIFY_KPIS["Verify Rehydrated Scorecard against Original Baseline"]
    
    VERIFY_KPIS --> DONE([Restoration Verified & Workspace Active])
```

---

## 8. Summary of Architectural Invariants

| # | Architectural Invariant | Enforcement Mechanism |
| :--- | :--- | :--- |
| **1** | **Zero Outbound Egress** | Loopback binding (`127.0.0.1`), offline token generation, zero network telemetry dependencies. |
| **2** | **Data Sovereignty** | Local file storage (`requirements.json`, `tests.json`, `.reqtrace/`), no remote DB requirement. |
| **3** | **Append-Only Ledger** | `ReviewStore` appends immutable event tuples; previous review history is preserved forever. |
| **4** | **Content-Hash Binding** | Review events bind directly to `sha256(requirement_text)`; specification drift marks links stale. |
| **5** | **Reproducible Deliverables** | Deterministic linking and canonical status engine produce identical outputs from identical inputs. |
| **6** | **Review Fast-Path** | Human review sign-offs bypass $O(N \times M)$ text linkers, executing only $O(N)$ status updates in < 1.5ms. |
| **7** | **Option B Workspace Creation** | Directories must exist prior to workspace creation; ReqTrace never silently creates target paths. |

