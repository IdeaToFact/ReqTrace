# Third-Party Software & Model Notices (`THIRD_PARTY_NOTICES.md`)

ReqTrace incorporates or depends upon third-party open-source libraries and machine learning runtimes. This document lists the primary dependencies, their respective licenses, and commercial licensing considerations.

---

## 1. Direct Python Dependencies

| Package | License | Purpose in ReqTrace | Commercial Dual-Licensing Consideration |
| :--- | :--- | :--- | :--- |
| **Pydantic** | MIT | Core data models, schema serialization, and validation | Permissive |
| **Pydantic-Settings** | MIT | TOML/environment configuration management | Permissive |
| **Typer** | MIT | Modern CLI command structure and argument handling | Permissive |
| **Rich** | MIT | Terminal formatting, interactive tables, trees, and progress indicators | Permissive |
| **defusedxml** | PSF-2.0 | Safe, hardened XML/ReqIF parsing with XML entity expansion / bomb prevention | Permissive |
| **pypdfium2** | Apache-2.0 / BSD-3-Clause | PDF text extraction (declared clean-room permissive PDF adapter alternative to AGPL `PyMuPDF`) | Permissive |
| **python-docx** | MIT | Word (.docx) requirements and spec parsing | Permissive |
| **RapidFuzz** | MIT | High-performance C/C++ accelerated fuzzy string matching for token windowing | Permissive |
| **rank-bm25** | Apache-2.0 | BM25 sparse lexical ranking (optional semantic extension) | Permissive |
| **FastEmbed** | Apache-2.0 | Offline local ONNX runtime for embedding (optional semantic extension) | Permissive |
| **HTTPx** | BSD-3-Clause | Offline transport abstraction for local in-enclave LLM inference endpoints (e.g. local Ollama at `http://127.0.0.1:11434`); zero external WAN egress | Permissive (To be decoupled to optional extra `[ollama]`) |
| **FastAPI** | MIT | Core HTTP ASGI framework for local UI server (`reqtrace ui`) | Permissive |
| **python-multipart** | Apache-2.0 | Multipart form data and file upload parsing for web UI Ingestion Wizard | Permissive |
| **Uvicorn** | BSD-3-Clause | Lightweight ASGI loopback web server (`reqtrace ui`) | Permissive |
| **filelock** | MIT (v4.x) / The Unlicense (prior) | Cross-platform atomic file locking for review overlay store | Permissive |
| **pytest** | MIT | Unit and integration testing | Test-only |
| **pytest-cov** | MIT | Code coverage auditing | Test-only |
| **pip-licenses** | MIT | Dependency license compliance verification | Test-only |

---

## 2. Permissive Clean-Room Dependency Policy

To allow Idea To Fact LLC to offer both the **AGPLv3 Community Edition** and **Proprietary Commercial Pro / Enterprise Editions**, all direct runtime dependencies of ReqTrace are strictly restricted to permissive licenses:
- `MIT`
- `Apache-2.0`
- `BSD-2-Clause` / `BSD-3-Clause`
- `PSF-2.0` (Python Software Foundation License)
- `ISC`
- `The Unlicense` (Public Domain dedication)

No third-party GPL, LGPL, or AGPL libraries are bundled, imported, or linked as direct dependencies (`PyMuPDF`/`fitz` and `pytesseract` are explicitly prohibited by `tests/test_license_guardrails.py`).

### Transitive Dependencies Audit
The primary transitive runtime dependencies pulled by ReqTrace's declared dependencies in `pyproject.toml` include:
- Permissive packages: `numpy` (BSD-3-Clause), `onnxruntime` (MIT), `tokenizers` (Apache-2.0), `huggingface-hub` (Apache-2.0), `click` (BSD-3-Clause), `markdown-it-py` (MIT), `shellingham` (MIT), `starlette` (BSD-3-Clause), `anyio` (MIT), `lxml` (BSD-3-Clause), `h11` (MIT).
- Weak file-level copyleft / dual-licensed transitive utilities: `certifi` (`MPL-2.0`, pulled by `httpx`), and dual-licensed `tqdm` (`MPL-2.0 AND MIT`, pulled by `fastembed` / `huggingface-hub`). Under the Mozilla Public License 2.0 (`MPL-2.0`), unmodified third-party library files remain compatible with proprietary Commercial Editions without triggering whole-work copyleft obligations.

Zero GPL, LGPL, or AGPL transitive runtime dependencies are included in ReqTrace's declared dependency tree. Before cutting commercial release builds, run `pip-licenses` in a clean virtual environment built strictly from `pyproject.toml` alongside `pytest tests/test_license_guardrails.py`.

---

## 3. Container Base Image & AGPLv3 §6 Source Availability

- **Container Runtime (`Dockerfile`)**: Built on `python:3.12-slim` (Debian Linux base). Base OS packages in Debian images remain governed by their respective upstream open-source licenses (GPL, LGPL, BSD, MIT, etc.).
- In accordance with Section 6 of the GNU AGPLv3, complete build scripts and container recipes are provided in [`Dockerfile`](Dockerfile), [`docker-run.ps1`](docker-run.ps1), and [`docker-run.sh`](docker-run.sh).

---

## 4. Machine Learning Models & Air-Gapped Weight Provisioning

When optional semantic extensions (`reqtrace.extensions`) are enabled:

| Model / Weight Identifier | Provider / Author | Stated License | Source Repository & Hash | Air-Gap Provisioning |
| :--- | :--- | :--- | :--- | :--- |
| **`BAAI/bge-small-en-v1.5`** | Beijing Academy of AI (BAAI) | **MIT** | `https://huggingface.co/BAAI/bge-small-en-v1.5`<br>Git Commit: `5c38ec7` | FastEmbed downloads weights on first use by default. In true air-gapped enclaves, weights must be pre-staged via `FASTEMBED_CACHE_PATH` or a local directory without network egress. |
| **Host LLM Models (Ollama)** | Meta, Mistral AI, Qwen, etc. | **Vendor-Specific** | Brought by customer via local Ollama daemon (`http://127.0.0.1:11434`) | ReqTrace does not bundle, download, or redistribute proprietary model weights. |

---

## 5. Inquiries

For questions regarding third-party licensing or commercial compliance packages, contact:
**Idea To Fact LLC**  
Website: `https://ideatofact.com`  
Email: `licensing@ideatofact.com`
