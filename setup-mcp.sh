#!/usr/bin/env bash
# setup-mcp.sh — Configure CodeRAG MCP server + AI skill for your project
#
# Usage:
#   coderag-setup-mcp [PROJECT_DIR]    # defaults to current directory
#
# This script:
#   1. Parses the codebase (if not already parsed)
#   2. Creates/updates .mcp.json in the project root
#   3. Creates CLAUDE.md with tool usage instructions
#   4. Installs SKILL.md (OpenSkill format) for Agent Zero / compatible agents
#   5. Verifies the setup works

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
echo -e "${BLUE}║     CodeRAG Setup                        ║${NC}"
echo -e "${BLUE}║     MCP Server + AI Skill Installer      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""
info "Project: $PROJECT_NAME"
info "Path:    $PROJECT_DIR"
echo ""

# ── Step 1: Check coderag is installed ────────────────────────
if ! command -v coderag &>/dev/null; then
    err "coderag not found on PATH"
    echo "  Install with: curl -fsSL https://raw.githubusercontent.com/dmnkhorvath/coderag/main/install.sh | sh"
    exit 1
fi
ok "coderag found: $(which coderag)"

# ── Step 2: Detect coderag binary & source paths ─────────────
CODERAG_BIN="$(which coderag)"
CODERAG_ROOT=""

# Try standard install location first
if [ -d "$HOME/.coderag/src" ]; then
    CODERAG_ROOT="$HOME/.coderag/src"
else
    # Try to find the package root from Python
    CODERAG_ROOT="$(python3 -c "import coderag; import os; print(os.path.dirname(os.path.dirname(coderag.__file__)))" 2>/dev/null || true)"
fi

if [ -n "$CODERAG_ROOT" ]; then
    ok "CodeRAG source: $CODERAG_ROOT"
else
    warn "Could not locate CodeRAG source directory"
fi

# ── Step 3: Parse codebase if needed ──────────────────────────
echo ""
echo -e "${CYAN}── Phase 1: Codebase Parsing ──${NC}"
DB_PATH="$PROJECT_DIR/.codegraph/graph.db"
if [ -f "$DB_PATH" ]; then
    ok "Knowledge graph exists: $DB_PATH"
    read -rp "   Re-parse? (y/N) " REPARSE
    if [[ "$REPARSE" =~ ^[Yy]$ ]]; then
        info "Parsing codebase (incremental)..."
        coderag parse "$PROJECT_DIR" --incremental
        ok "Parse complete"
    fi
else
    info "No knowledge graph found. Parsing codebase..."
    coderag parse "$PROJECT_DIR"
    ok "Parse complete"
fi

# ── Step 4: Show graph stats ──────────────────────────────────
echo ""
info "Graph statistics:"
coderag info "$PROJECT_DIR" 2>/dev/null || warn "Could not read graph stats"

# ── Step 5: Create .mcp.json ──────────────────────────────────
echo ""
echo -e "${CYAN}── Phase 2: MCP Server Configuration ──${NC}"
MCP_JSON="$PROJECT_DIR/.mcp.json"

_write_mcp_json() {
    cat > "$MCP_JSON" << MCPEOF
{
  "mcpServers": {
    "coderag": {
      "command": "$CODERAG_BIN",
      "args": ["serve", "."],
      "env": {}
    }
  }
}
MCPEOF
}

if [ -f "$MCP_JSON" ]; then
    warn ".mcp.json already exists"
    read -rp "   Overwrite? (y/N) " OVERWRITE
    if [[ "$OVERWRITE" =~ ^[Yy]$ ]]; then
        _write_mcp_json
        ok "Updated $MCP_JSON"
    else
        info "Keeping existing .mcp.json"
    fi
else
    _write_mcp_json
    ok "Created $MCP_JSON"
fi

# ── Step 6: Create CLAUDE.md ──────────────────────────────────
echo ""
echo -e "${CYAN}── Phase 3: Claude Code Integration ──${NC}"
CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"
if [ -f "$CLAUDE_MD" ]; then
    warn "CLAUDE.md already exists — skipping (won\'t overwrite your instructions)"
else
    if [ -n "$CODERAG_ROOT" ] && [ -f "$CODERAG_ROOT/CLAUDE.md" ]; then
        cp "$CODERAG_ROOT/CLAUDE.md" "$CLAUDE_MD"
        ok "Created $CLAUDE_MD (from template)"
    else
        # Write a minimal CLAUDE.md
        cat > "$CLAUDE_MD" << 'CLAUDEEOF'
# CodeRAG — Codebase Knowledge Graph

This project has CodeRAG configured. Use the MCP tools to understand the codebase:

- `coderag_lookup_symbol(symbol)` — Look up any symbol
- `coderag_find_usages(symbol)` — Find all usages
- `coderag_impact_analysis(symbol)` — Blast radius analysis
- `coderag_file_context(file_path)` — Understand a file
- `coderag_find_routes(pattern)` — Find API routes
- `coderag_search(query)` — Search the graph
- `coderag_architecture()` — Architecture overview
- `coderag_dependency_graph(target)` — Dependency visualization

Re-parse after changes: `coderag parse . --incremental`
CLAUDEEOF
        ok "Created $CLAUDE_MD (minimal)"
    fi
fi

# ── Step 7: Install SKILL.md (OpenSkill / Agent Zero) ─────────
echo ""
echo -e "${CYAN}── Phase 4: AI Skill Installation (OpenSkill) ──${NC}"
SKILL_DIR="$PROJECT_DIR/.coderag/skill"
SKILL_MD="$SKILL_DIR/SKILL.md"

_install_skill() {
    mkdir -p "$SKILL_DIR"

    # Try to find the SKILL.md template from the coderag installation
    local SKILL_SRC=""
    if [ -n "$CODERAG_ROOT" ] && [ -f "$CODERAG_ROOT/skill/SKILL.md" ]; then
        SKILL_SRC="$CODERAG_ROOT/skill/SKILL.md"
    fi

    if [ -n "$SKILL_SRC" ]; then
        cp "$SKILL_SRC" "$SKILL_MD"
        ok "Installed $SKILL_MD (from template: $SKILL_SRC)"
    else
        # Download from GitHub as fallback
        info "Template not found locally, downloading from GitHub..."
        if curl -fsSL "https://raw.githubusercontent.com/dmnkhorvath/coderag/main/skill/SKILL.md" -o "$SKILL_MD" 2>/dev/null; then
            ok "Installed $SKILL_MD (downloaded from GitHub)"
        else
            warn "Could not download SKILL.md — writing minimal skill file"
            cat > "$SKILL_MD" << 'SKILLEOF'
---
name: "coderag"
description: "CodeRAG MCP server skill — AST-based codebase intelligence with 8 MCP tools for symbol lookup, impact analysis, route discovery, and architecture overview."
version: "0.1.0"
author: "dmnkhorvath"
tags: ["mcp", "code-analysis", "knowledge-graph", "ast", "php", "javascript", "typescript"]
trigger_patterns:
  - "coderag"
  - "code graph"
  - "knowledge graph"
  - "symbol lookup"
  - "impact analysis"
  - "find usages"
  - "codebase architecture"
  - "mcp server"
---

# CodeRAG — Codebase Knowledge Graph for LLMs

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `coderag_lookup_symbol` | Look up any symbol (class, function, method) |
| `coderag_find_usages` | Find all usages of a symbol |
| `coderag_impact_analysis` | Blast radius / change impact analysis |
| `coderag_file_context` | Understand a file and its relationships |
| `coderag_find_routes` | Find API routes matching a pattern |
| `coderag_search` | Full-text + semantic search across the graph |
| `coderag_architecture` | Architecture overview with community detection |
| `coderag_dependency_graph` | Dependency tree visualization |

## Usage

```bash
# Parse the codebase
coderag parse /path/to/project

# Start MCP server
coderag serve /path/to/project

# Re-parse after changes
coderag parse /path/to/project --incremental
```
SKILLEOF
        fi
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

# Also create a symlink at project root for discoverability
SKILL_LINK="$PROJECT_DIR/SKILL.md"
if [ ! -f "$SKILL_LINK" ] && [ ! -L "$SKILL_LINK" ]; then
    ln -s ".coderag/skill/SKILL.md" "$SKILL_LINK" 2>/dev/null && \
        ok "Created symlink: SKILL.md → .coderag/skill/SKILL.md" || \
        info "Symlink not created (optional)"
fi

# ── Step 8: Verify MCP server starts ──────────────────────────
echo ""
echo -e "${CYAN}── Phase 5: Verification ──${NC}"
info "Verifying MCP server..."
if timeout 3 coderag serve "$PROJECT_DIR" </dev/null >/dev/null 2>&1; then
    ok "MCP server starts successfully"
else
    # timeout returns 124 if it timed out (which means server started and was running)
    if [ $? -eq 124 ]; then
        ok "MCP server starts successfully (stdio mode)"
    else
        warn "MCP server may have issues — try running: coderag serve $PROJECT_DIR"
    fi
fi

# Verify skill file
if [ -f "$SKILL_MD" ]; then
    SKILL_LINES=$(wc -l < "$SKILL_MD")
    ok "SKILL.md installed ($SKILL_LINES lines)"
else
    warn "SKILL.md not found"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Setup Complete!                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Files created/updated:"
[ -f "$MCP_JSON" ]   && echo "    ✓ .mcp.json          (MCP server config)"
[ -f "$CLAUDE_MD" ]  && echo "    ✓ CLAUDE.md          (Claude Code instructions)"
[ -f "$SKILL_MD" ]   && echo "    ✓ .coderag/skill/SKILL.md  (OpenSkill for Agent Zero)"
[ -L "$SKILL_LINK" ] && echo "    ✓ SKILL.md           (symlink → .coderag/skill/)"
echo ""
echo "  Supported AI agents:"
echo "    🤖 Claude Code / Cursor  → reads .mcp.json + CLAUDE.md"
echo "    🤖 Agent Zero            → reads SKILL.md (OpenSkill format)"
echo "    🤖 Any MCP client        → connects via .mcp.json"
echo ""
echo "  Next steps:"
echo "    1. Open this project in your AI coding tool"
echo "    2. The MCP server will start automatically"
echo "    3. Use coderag_* tools to explore your codebase"
echo ""
echo "  Manual server test:"
echo "    coderag serve $PROJECT_DIR"
echo ""
