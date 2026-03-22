# ============================================================
# CodeRAG - Multi-stage Docker Build
# ============================================================
# Build knowledge graphs from your codebase for LLM context retrieval
# https://github.com/dmnkhorvath/coderag
# ============================================================

# ── Builder Stage ────────────────────────────────────────────
FROM python:3.12-slim AS builder

LABEL maintainer="Dominik Horváth"
LABEL org.opencontainers.image.source="https://github.com/dmnkhorvath/coderag"
LABEL org.opencontainers.image.description="CodeRAG - Build knowledge graphs from your codebase for LLM context retrieval"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.licenses="MIT"

# Install build dependencies for tree-sitter C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up build directory
WORKDIR /build

# Copy only dependency files first for better layer caching
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install package with all extras into a virtual environment
RUN python -m venv /opt/coderag-venv && \
    /opt/coderag-venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/coderag-venv/bin/pip install --no-cache-dir -e ".[full]"

# ── Runtime Stage ────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="Dominik Horváth"
LABEL org.opencontainers.image.source="https://github.com/dmnkhorvath/coderag"
LABEL org.opencontainers.image.description="CodeRAG - Build knowledge graphs from your codebase for LLM context retrieval"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.licenses="MIT"

# Install minimal runtime dependencies
# git is needed for git enrichment features
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/coderag-venv /opt/coderag-venv

# Copy source code (needed for editable install)
COPY --from=builder /build /opt/coderag-src

# Ensure venv binaries are on PATH
ENV PATH="/opt/coderag-venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy entrypoint script
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Working directory where users mount their codebase
WORKDIR /code

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["--help"]
