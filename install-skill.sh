#!/usr/bin/env bash
# install-skill.sh — Install CodeRAG skill + knowledge graph for your project
#
# Usage:
#   ./install-skill.sh [PROJECT_DIR]    # defaults to current directory
#
# Uses only coderag CLI commands (documented in SKILL.md):
#   coderag init, parse, validate, info, embed, serve
#
# This script:
#   1. Verifies coderag is installed
#   2. Initializes config (coderag init)
#   3. Parses the codebase (coderag parse)
#   4. Validates configuration (coderag validate)
#   5. Shows graph statistics (coderag info)
#   6. Optionally generates embeddings (coderag embed)
#   7. Installs SKILL.md (OpenSkill format for Agent Zero)
#   8. Verifies MCP server (coderag serve)

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${BLUE}ℹ${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*"; }

PROJECT_DIR="${1:-.}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     CodeRAG Skill Installer              ║${NC}"
echo -e "${BLUE}║     Knowledge Graph + OpenSkill Setup    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""
info "Project: $PROJECT_NAME"
info "Path:    $PROJECT_DIR"
echo ""

# ── Step 1: Verify coderag is installed ───────────────────────
echo -e "${CYAN}── Step 1: Checking coderag installation ──${NC}"
if ! command -v coderag &>/dev/null; then
    err "coderag not found on PATH"
    echo "  Install with:"
    echo "    curl -fsSL https://raw.githubusercontent.com/dmnkhorvath/coderag/main/install.sh | sh"
    exit 1
fi
ok "coderag found: $(which coderag)"
echo ""

# ── Step 2: Initialize config (coderag init) ──────────────────
echo -e "${CYAN}── Step 2: Initializing configuration ──${NC}"
CONFIG_FILE="$PROJECT_DIR/codegraph.yaml"
if [ -f "$CONFIG_FILE" ]; then
    ok "Config already exists: $CONFIG_FILE"
else
    info "Creating default configuration..."
    cd "$PROJECT_DIR" && coderag init
    if [ -f "$CONFIG_FILE" ]; then
        ok "Created $CONFIG_FILE"
    else
        warn "Config file not created — using defaults"
    fi
fi
echo ""

# ── Step 3: Parse codebase (coderag parse) ────────────────────
echo -e "${CYAN}── Step 3: Building knowledge graph ──${NC}"
DB_PATH="$PROJECT_DIR/.codegraph/graph.db"
if [ -f "$DB_PATH" ]; then
    ok "Knowledge graph exists: $DB_PATH"
    read -rp "   Re-parse incrementally? (y/N) " REPARSE
    if [[ "$REPARSE" =~ ^[Yy]$ ]]; then
        info "Running incremental parse..."
        coderag parse "$PROJECT_DIR" --incremental
        ok "Incremental parse complete"
    fi
else
    info "Parsing codebase (this may take a moment)..."
    coderag parse "$PROJECT_DIR"
    ok "Parse complete"
fi
echo ""

# ── Step 4: Validate configuration (coderag validate) ─────────
echo -e "${CYAN}── Step 4: Validating configuration ──${NC}"
if coderag validate "$PROJECT_DIR" 2>/dev/null; then
    ok "Validation passed"
else
    warn "Validation reported issues — check output above"
fi
echo ""

# ── Step 5: Show graph statistics (coderag info) ──────────────
echo -e "${CYAN}── Step 5: Graph statistics ──${NC}"
coderag info "$PROJECT_DIR" 2>/dev/null || warn "Could not read graph stats"
echo ""

# ── Step 6: Semantic embeddings (coderag embed) ───────────────
echo -e "${CYAN}── Step 6: Semantic embeddings (optional) ──${NC}"
read -rp "   Generate semantic embeddings? (y/N) " DO_EMBED
if [[ "$DO_EMBED" =~ ^[Yy]$ ]]; then
    info "Generating embeddings (this may take a while)..."
    if coderag embed "$PROJECT_DIR" 2>/dev/null; then
        ok "Embeddings generated"
    else
        warn "Embedding generation failed — semantic search will be unavailable"
        warn "You can retry later with: coderag embed $PROJECT_DIR"
    fi
else
    info "Skipped — run later with: coderag embed $PROJECT_DIR"
fi
echo ""

# ── Step 7: Install SKILL.md (OpenSkill format) ───────────────
echo -e "${CYAN}── Step 7: Installing AI skill (OpenSkill) ──${NC}"
SKILL_DIR="$PROJECT_DIR/.coderag/skill"
SKILL_MD="$SKILL_DIR/SKILL.md"

_install_skill() {
    mkdir -p "$SKILL_DIR"

    # Find SKILL.md from the coderag installation
    local SKILL_SRC=""
    local CODERAG_ROOT=""

    # Try standard install location
    if [ -d "$HOME/.coderag/src" ]; then
        CODERAG_ROOT="$HOME/.coderag/src"
    else
        CODERAG_ROOT="$(python3 -c "import coderag; import os; print(os.path.dirname(os.path.dirname(coderag.__file__)))" 2>/dev/null || true)"
    fi

    if [ -n "$CODERAG_ROOT" ] && [ -f "$CODERAG_ROOT/skill/SKILL.md" ]; then
        SKILL_SRC="$CODERAG_ROOT/skill/SKILL.md"
    fi

    if [ -n "$SKILL_SRC" ]; then
        cp "$SKILL_SRC" "$SKILL_MD"
        ok "Installed SKILL.md (from: $SKILL_SRC)"
    else
        # Fallback: download from GitHub
        info "Local template not found, downloading from GitHub..."
        if curl -fsSL "https://raw.githubusercontent.com/dmnkhorvath/coderag/main/skill/SKILL.md" -o "$SKILL_MD" 2>/dev/null; then
            ok "Installed SKILL.md (downloaded from GitHub)"
        else
            err "Could not install SKILL.md"
            echo "  Download manually from:"
            echo "    https://github.com/dmnkhorvath/coderag/blob/main/skill/SKILL.md"
            return 1
        fi
    fi

    # Create root symlink for discoverability
    local SKILL_LINK="$PROJECT_DIR/SKILL.md"
    if [ ! -f "$SKILL_LINK" ] && [ ! -L "$SKILL_LINK" ]; then
        ln -s ".coderag/skill/SKILL.md" "$SKILL_LINK" 2>/dev/null && \
            ok "Symlink: SKILL.md → .coderag/skill/SKILL.md" || true
    fi
}

if [ -f "$SKILL_MD" ]; then
    warn "SKILL.md already exists at $SKILL_MD"
    read -rp "   Overwrite? (y/N) " OVERWRITE_SKILL
    if [[ "$OVERWRITE_SKILL" =~ ^[Yy]$ ]]; then
        _install_skill
    else
        info "Keeping existing SKILL.md"
    fi
else
    _install_skill
fi
echo ""

# ── Step 8: Verify MCP server (coderag serve) ─────────────────
echo -e "${CYAN}── Step 8: Verifying MCP server ──${NC}"
info "Testing MCP server startup..."
if timeout 3 coderag serve "$PROJECT_DIR" </dev/null >/dev/null 2>&1; then
    ok "MCP server starts successfully"
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        ok "MCP server starts successfully (stdio mode)"
    else
        warn "MCP server may have issues"
        warn "Test manually: coderag serve $PROJECT_DIR"
    fi
fi
echo ""

# ── Summary ───────────────────────────────────────────────────
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Installation Complete!                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Files:"
[ -f "$CONFIG_FILE" ]  && echo "    ✓ codegraph.yaml           (configuration)"
[ -f "$DB_PATH" ]      && echo "    ✓ .codegraph/graph.db      (knowledge graph)"
[ -f "$SKILL_MD" ]     && echo "    ✓ .coderag/skill/SKILL.md  (AI skill)"
[ -L "$PROJECT_DIR/SKILL.md" ] && echo "    ✓ SKILL.md                 (symlink)"
echo ""
echo "  CLI commands used (all from SKILL.md):"
echo "    coderag init       → created config"
echo "    coderag parse      → built knowledge graph"
echo "    coderag validate   → verified configuration"
echo "    coderag info       → displayed statistics"
echo "    coderag embed      → semantic embeddings"
echo "    coderag serve      → verified MCP server"
echo ""
echo "  Useful commands:"
echo "    coderag parse $PROJECT_DIR --incremental   # re-parse after changes"
echo "    coderag monitor $PROJECT_DIR               # TUI dashboard"
echo "    coderag watch $PROJECT_DIR                 # auto-reparse on changes"
echo "    coderag architecture $PROJECT_DIR          # architecture overview"
echo "    coderag search $PROJECT_DIR <query>         # search the graph"
echo ""
echo "  For MCP server setup (Claude Code / Cursor):"
echo "    ./setup-mcp.sh $PROJECT_DIR"
echo ""
