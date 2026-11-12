# ==============================================================================
# ReqTrace v0.2.0: Air-Gapped Verification Cockpit
# Multi-stage hardened container image for DO-178C / ISO 26262 compliance
# ==============================================================================

# --- Stage 1: Build Wheel ---
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY reqtrace/ reqtrace/

RUN pip install --no-cache-dir hatchling build && \
    python -m build --wheel --no-isolation

# --- Stage 2: Hardened Runtime ---
FROM python:3.12-slim AS runtime

LABEL maintainer="Idea To Fact LLC <contact@ideatofact.com>" \
      description="ReqTrace Community Edition v0.2.0 - Air-Gapped Requirements Traceability & Audit Verification Cockpit" \
      version="0.2.0" \
      license="GNU AGPLv3" \
      org.opencontainers.image.title="ReqTrace Community Edition" \
      org.opencontainers.image.description="Air-Gapped Requirements Traceability & Audit Verification Cockpit" \
      org.opencontainers.image.version="0.2.0" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/ideatofact/reqtrace" \
      org.opencontainers.image.vendor="Idea To Fact LLC"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/reqtrace

# Create unprivileged service user and group (UID/GID 10001)
RUN groupadd -g 10001 reqtrace && \
    useradd -u 10001 -g reqtrace -m -s /bin/bash reqtrace

# Include license, copyright, and third-party notices inside the image
COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md /usr/local/share/licenses/reqtrace/

# Copy built wheel from builder stage
COPY --from=builder /build/dist/*.whl /tmp/

# Install ReqTrace package and dependencies
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -rf /tmp/*.whl

# Create workspace directory with non-root ownership
RUN mkdir -p /workspace && \
    chown -R reqtrace:reqtrace /workspace

# Switch to non-root user
USER reqtrace
WORKDIR /workspace

# Expose default ReqTrace loopback port
EXPOSE 8765

# Local healthcheck probing the workspaces API
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/').read()" || exit 1

# Default command: launch the interactive UI cockpit bound to 0.0.0.0
ENTRYPOINT ["reqtrace"]
CMD ["ui", "--workspace", "/workspace", "--host", "0.0.0.0", "--port", "8765", "--no-browser", "--ticket-timeout", "1800"]

