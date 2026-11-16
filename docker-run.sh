#!/usr/bin/env bash
# ==============================================================================
# ReqTrace v0.2.0: Docker Launch Helper Script (Linux / macOS)
# Builds and launches the air-gapped container with host folder bind mount.
# ==============================================================================

set -euo pipefail

IMAGE_NAME="airgapaxis/reqtrace:0.2.0-community"
LOCAL_IMAGE="reqtrace:0.2.0"
PORT="${REQTRACE_PORT:-8765}"
WORKSPACE_DIR=""
DETACH=false
BUILD_ONLY=false
REBUILD=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--detach)
            DETACH=true
            shift
            ;;
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --rebuild)
            REBUILD=true
            shift
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        *)
            if [ -z "$WORKSPACE_DIR" ]; then
                WORKSPACE_DIR="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "$WORKSPACE_DIR" ]; then
    WORKSPACE_DIR="$(pwd)"
fi

# 1. Verify Docker CLI Availability
if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Error: Docker is not installed or not available in PATH."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker daemon is not running."
    exit 1
fi

# 2. Ensure target workspace exists (Option B Policy)
if [ ! -d "$WORKSPACE_DIR" ]; then
    echo "❌ Error: Target workspace directory does not exist: $WORKSPACE_DIR"
    echo "ReqTrace enforces Option B: directories must exist prior to launch."
    exit 1
fi

WORKSPACE_ABS="$(cd "$WORKSPACE_DIR" && pwd)"

echo "======================================================================"
echo "🎯 ReqTrace Docker Cockpit (v0.2.0)"
echo "  Image:     $IMAGE_NAME"
echo "  Workspace: $WORKSPACE_ABS"
echo "  Port:      http://localhost:$PORT"
echo "======================================================================"

# 3. Check Docker image (Use local if present, try pull, or build)
IMAGE_EXISTS=false
if docker image inspect "$IMAGE_NAME" >/dev/null 2>&1 || docker image inspect "$LOCAL_IMAGE" >/dev/null 2>&1; then
    IMAGE_EXISTS=true
fi

if [ "$REBUILD" = true ] || [ "$IMAGE_EXISTS" = false ]; then
    if [ "$REBUILD" = false ]; then
        echo "🔍 Checking Docker Hub for '$IMAGE_NAME'..."
        if docker pull "$IMAGE_NAME" >/dev/null 2>&1; then
            IMAGE_EXISTS=true
        fi
    fi
    if [ "$REBUILD" = true ] || [ "$IMAGE_EXISTS" = false ]; then
        echo "🔨 Building Docker image '$IMAGE_NAME' from source..."
        docker build -t "$IMAGE_NAME" -t "$LOCAL_IMAGE" .
    fi
fi

if [ "$BUILD_ONLY" = true ]; then
    echo "Build complete (--build-only specified). Exiting."
    exit 0
fi

# 4. Remove any stale container instance
docker rm -f reqtrace-cockpit >/dev/null 2>&1 || true

# 5. Run the container
USER_OPTS=()
if [ "$(uname -s)" = "Linux" ]; then
    USER_OPTS=(--user "$(id -u):$(id -g)")
fi

if [ "$DETACH" = true ]; then
    echo "🚀 Starting ReqTrace container in the background..."
    CONTAINER_ID=$(docker run -d \
        --name reqtrace-cockpit \
        "${USER_OPTS[@]}" \
        -p "127.0.0.1:$PORT:$PORT" \
        -v "$WORKSPACE_ABS:/workspace" \
        "$IMAGE_NAME" \
        ui --workspace /workspace --host 0.0.0.0 --port "$PORT" --ticket-timeout 1800 --no-browser)

    sleep 2
    echo "✅ Container 'reqtrace-cockpit' is running!"
    echo "   Container ID: $CONTAINER_ID"
    echo "   Stop Command: docker stop reqtrace-cockpit"
    echo "   View Logs:    docker logs -f reqtrace-cockpit"
    echo "   New Ticket:   docker exec reqtrace-cockpit reqtrace ticket -p $PORT"
    echo ""
    # Extract launch URL from logs
    docker logs reqtrace-cockpit 2>&1 | grep -E "Launch URL:|Ticket:" || echo "Access URL: http://localhost:$PORT"
else
    echo "🚀 Starting container (Press Ctrl+C to stop)..."
    docker run --rm -it \
        --name reqtrace-cockpit \
        "${USER_OPTS[@]}" \
        -p "127.0.0.1:$PORT:$PORT" \
        -v "$WORKSPACE_ABS:/workspace" \
        "$IMAGE_NAME" \
        ui --workspace /workspace --host 0.0.0.0 --port "$PORT" --ticket-timeout 1800 --no-browser
fi
