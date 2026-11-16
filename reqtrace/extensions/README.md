# ReqTrace Extensions (MVP+ AI & Semantic Enhancements)

This package houses optional, non-core semantic AI modules that enhance the deterministic engine post-v0.1:

1. **`hybrid_retriever.py` (MVP+)**:
   * Combines BM25 sparse lexical indexing with FastEmbed / ONNX dense vector embeddings (`BAAI/bge-small-en-v1.5`).
   * Used when specification requirements do not share explicit tags or token overlap with test fixtures.

2. **`assertion_verifier.py` (MVP+)**:
   * Connects to local air-gapped LLM endpoints (Ollama / vLLM, e.g. Qwen 2.5 14B/32B).
   * Generates natural-language rationalizations explaining *why* an assertion verifies a given requirement clause.

> [!NOTE]
> The core `reqtrace` engine (`reqtrace/engine/`) operates **100% deterministically** with zero vector or neural dependencies to ensure instant verification, reproducible DER audits, and zero air-gap egress risks.

