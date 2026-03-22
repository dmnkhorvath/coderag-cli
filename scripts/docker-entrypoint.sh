#!/bin/sh
set -e

# ============================================================
# CodeRAG Docker Entrypoint
# ============================================================
# Handles volume permissions and delegates to coderag CLI
# ============================================================

# If /code is mounted and has files, ensure we can read them
if [ -d "/code" ] && [ "$(ls -A /code 2>/dev/null)" ]; then
    # Check if we can read the mounted directory
    if ! ls /code >/dev/null 2>&1; then
        echo "ERROR: Cannot read /code directory. Check volume mount permissions." >&2
        echo "Try running with: docker run --user $(id -u):$(id -g) ..." >&2
        exit 1
    fi
fi

# If no arguments provided, show help
if [ $# -eq 0 ]; then
    echo "CodeRAG - Build knowledge graphs from your codebase"
    echo ""
    echo "Usage:"
    echo "  docker run -v \$(pwd):/code coderag parse ."
    echo "  docker run -v \$(pwd):/code coderag info"
    echo "  docker run -v \$(pwd):/code coderag query "find controllers""
    echo "  docker run -v \$(pwd):/code coderag serve . --watch"
    echo ""
    exec coderag --help
fi

# Delegate to coderag CLI
exec coderag "$@"
