# CodeRAG — UX & Session Intelligence Roadmap

> **Inspired by:** [Dual-Graph (Codex-CLI-Compact)](https://github.com/kunal12203/Codex-CLI-Compact)
> **Created:** 2026-03-21
> **Updated:** 2026-03-21
> **Status:** Planning
> **Goal:** Close the UX gap between CodeRAG's deep analysis engine and Dual-Graph's developer experience

---

## ⚠️ Lessons Learned: TUI Dead End

The TUI monitoring dashboard (Phase P2 of original roadmap) was implemented with 2,885 lines,
22 files, and 271 tests — all passing. **However, it could never be validated end-to-end**
because the Textual TUI requires an interactive terminal that our development environment
cannot provide. Tests pass in isolation but the actual user experience was never verified.

### Key Takeaways
1. **Tests passing ≠ feature working** — unit tests mock the environment; real validation requires real usage
2. **Prefer headless-first UX** — CLI output, file output, web dashboards over terminal UIs
3. **Every feature must have a validation path** — if you can't demo it, don't build it
4. **Rich terminal output ≠ TUI** — `rich` library tables/progress bars work everywhere; full TUI apps don't

### Applied to This Roadmap
Every feature below includes a **Validation** section describing exactly how to prove it works
in a headless/CI environment. No feature requires an interactive terminal.

---

## Executive Summary

CodeRAG has superior technical depth (41 node types, 50 edge types, 11 framework detectors,
6 languages, 3,100+ tests). However, Dual-Graph demonstrates that **developer experience and
measurable cost savings** drive adoption more than raw capability. This roadmap addresses four
key gaps:

| # | Gap | Dual-Graph Has | CodeRAG Needs |
|---|-----|---------------|---------------|
| 1 | **Launcher UX** | `dgc /path` → instant Claude session | Multi-step setup, no launcher |
| 2 | **Cost Benchmarking** | 80+ prompt benchmarks with $ savings | Parse accuracy benchmarks only |
| 3 | **Session Memory** | Cross-session context persistence | Stateless per-parse |
| 4 | **Auto-Update** | Self-updating on every launch | Manual `git pull` + `pip install` |

---

## Phase 1: Smart Launcher (Priority: CRITICAL)

> **This is the highest-priority phase.** Without a frictionless entry point,
> none of the other features matter. Dual-Graph's entire value proposition
> is `dgc /path` — one command, done.

**Goal:** One command to scan a project and launch an AI coding session with pre-loaded context.

**Timeline:** 5-6 days (extra time allocated for thorough validation)

### 1.1 — Design Principles

1. **Zero-config by default** — `coderag launch .` must work without any setup
2. **Progressive disclosure** — simple by default, powerful with flags
3. **Fail gracefully** — if AI tool not found, still output useful context to stdout
4. **Headless-friendly** — all output via `rich` console, no interactive prompts
5. **Validatable** — every step produces verifiable file/stdout output

### 1.2 — `coderag launch` Command

New CLI command that orchestrates the full workflow:

```bash
# Basic usage — parse + launch Claude Code with MCP
coderag launch /path/to/project

# With initial prompt
coderag launch /path/to/project "fix the login bug"

# Choose AI tool
coderag launch /path/to/project --tool claude-code
coderag launch /path/to/project --tool cursor
coderag launch /path/to/project --tool codex

# Dry run — do everything except launch the AI tool
coderag launch /path/to/project --dry-run

# Output pre-loaded context to stdout (for piping)
coderag launch /path/to/project --context-only

# Short alias
cr /path/to/project
```

### 1.3 — What `launch` Does Internally

```
User runs: coderag launch /path/to/project "fix login bug"
                    ↓
Step 1: DETECT PROJECT
  ├── Check if .codegraph/graph.db exists
  ├── If not → run `coderag parse` with rich progress bar
  ├── If yes → check staleness (mtime of source files vs db)
  └── If stale → run incremental update

Step 2: BUILD CONTEXT PRE-LOAD
  ├── Run PageRank → get top-20 most important files
  ├── If prompt given → run semantic search for relevant symbols
  ├── Run framework detection summary
  ├── Build token-budgeted markdown context (default: 8000 tokens)
  └── Write to .codegraph/preload-context.md

Step 3: CONFIGURE AI TOOL
  ├── Auto-detect installed tools (claude, cursor, codex)
  ├── Write MCP configuration file:
  │   ├── Claude Code: .claude/settings.local.json
  │   ├── Cursor: .cursor/mcp.json
  │   └── Codex: codex.json
  └── Write CLAUDE.md / .cursorrules with project context

Step 4: GENERATE SYSTEM PROMPT ENHANCEMENT
  ├── Project overview (languages, frameworks, size)
  ├── Architecture summary (key modules, entry points)
  ├── Hot files (most connected, most changed)
  ├── Cross-language connections summary
  └── Write to .codegraph/system-prompt.md

Step 5: LAUNCH (or dry-run)
  ├── If --dry-run: print summary, exit
  ├── If --context-only: print context to stdout, exit
  ├── Start MCP server in background
  └── Launch AI tool with pre-loaded context
```

### 1.4 — AI Tool Configuration Templates

**Claude Code** (`.claude/settings.local.json`):
```json
{
  "mcpServers": {
    "coderag": {
      "command": "coderag",
      "args": ["serve", "--project", "/path/to/project"],
      "env": {}
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "coderag": {
      "command": "coderag",
      "args": ["serve", "--project", "/path/to/project"]
    }
  }
}
```

**CLAUDE.md** (auto-generated project context):
```markdown
# Project: my-app

## Architecture
- PHP Laravel backend (src/app/) — 342 files
- React TypeScript frontend (src/resources/js/) — 128 files
- 15 API routes connecting backend ↔ frontend

## Key Entry Points
- src/app/Http/Controllers/AuthController.php (PageRank: 0.034)
- src/resources/js/pages/Dashboard.tsx (PageRank: 0.028)

## MCP Tools Available
Use `coderag_query`, `coderag_blast_radius`, `coderag_find_references`,
`coderag_cross_language` for deep codebase exploration.
```

### 1.5 — `--dry-run` and `--context-only` Modes

These are **critical for validation**. They let us verify the entire pipeline
without needing an actual AI tool installed:

```bash
# Dry run — shows what would happen
$ coderag launch /path/to/project --dry-run

✓ Project parsed: 470 files, 3,241 nodes, 8,102 edges
✓ Frameworks detected: Laravel, React, Tailwind CSS
✓ Context pre-load: 7,842 tokens (20 files, 12 symbols)
✓ MCP config would be written to: .claude/settings.local.json
✓ CLAUDE.md would be written with project context
✓ Would launch: claude (detected at /usr/local/bin/claude)

# Context only — outputs the pre-loaded context
$ coderag launch /path/to/project "fix login" --context-only > context.md
$ wc -l context.md
247 context.md
$ head -20 context.md
# CodeRAG Context Pre-load
## Query: "fix login"
## Relevant Symbols
- AuthController::login() (confidence: 0.94)
- LoginRequest (confidence: 0.87)
...
```

### 1.6 — Implementation Tasks

| Task | File | Lines (est.) | Description |
|------|------|-------------|-------------|
| 1.6.1 | `src/coderag/launcher/__init__.py` | ~10 | Module init |
| 1.6.2 | `src/coderag/launcher/detector.py` | ~150 | Project state detection (fresh/stale/ready) |
| 1.6.3 | `src/coderag/launcher/preloader.py` | ~250 | Context pre-loading: PageRank top files, semantic search |
| 1.6.4 | `src/coderag/launcher/tool_config.py` | ~200 | AI tool config writers (Claude Code, Cursor, Codex) |
| 1.6.5 | `src/coderag/launcher/prompt_gen.py` | ~200 | CLAUDE.md / .cursorrules generator |
| 1.6.6 | `src/coderag/launcher/runner.py` | ~150 | Tool launcher with subprocess management |
| 1.6.7 | `src/coderag/cli/launch.py` | ~200 | Click command with all flags |
| 1.6.8 | `bin/cr` | ~20 | Short alias launcher script (POSIX shell) |
| 1.6.9 | `tests/test_launcher_detector.py` | ~150 | Tests for project detection |
| 1.6.10 | `tests/test_launcher_preloader.py` | ~200 | Tests for context pre-loading |
| 1.6.11 | `tests/test_launcher_tool_config.py` | ~150 | Tests for config file generation |
| 1.6.12 | `tests/test_launcher_prompt_gen.py` | ~150 | Tests for CLAUDE.md generation |
| 1.6.13 | `tests/test_launcher_integration.py` | ~200 | Integration tests using --dry-run |

**Total: ~2,030 lines** (1,180 source + 850 tests)

### 1.7 — Validation Plan

Every step can be validated without an interactive terminal:

| Step | Validation Method | Command |
|------|------------------|---------|
| Parse | Check db exists + node count | `coderag info /path` |
| Context pre-load | Check file content | `cat .codegraph/preload-context.md` |
| MCP config | Check JSON validity | `python -m json.tool .claude/settings.local.json` |
| CLAUDE.md | Check file content | `cat CLAUDE.md` |
| Dry run | Check stdout output | `coderag launch . --dry-run` |
| Context only | Check stdout | `coderag launch . --context-only \| wc -l` |
| Full E2E | Parse + dry-run on real repo | Clone Flask, run launch --dry-run |

### 1.8 — E2E Validation Script

```bash
#!/bin/bash
# validate_launcher.sh — Run after implementation to prove it works
set -e

# Clone a real project
git clone --depth 1 https://github.com/laravel/framework /tmp/test-laravel

# Test 1: Launch with dry-run
coderag launch /tmp/test-laravel --dry-run
echo "✓ Dry run completed"

# Test 2: Context-only mode
coderag launch /tmp/test-laravel "fix auth" --context-only > /tmp/context.md
[ $(wc -l < /tmp/context.md) -gt 10 ] && echo "✓ Context generated ($(wc -l < /tmp/context.md) lines)"

# Test 3: Config files generated
coderag launch /tmp/test-laravel --dry-run --tool claude-code
[ -f /tmp/test-laravel/.claude/settings.local.json ] && echo "✓ Claude config written"
[ -f /tmp/test-laravel/CLAUDE.md ] && echo "✓ CLAUDE.md written"

# Test 4: Config files are valid JSON
python -m json.tool /tmp/test-laravel/.claude/settings.local.json > /dev/null && echo "✓ Valid JSON"

# Test 5: Pre-load context is meaningful
grep -q "PageRank" /tmp/context.md && echo "✓ Contains PageRank data"
grep -q "auth" /tmp/context.md && echo "✓ Contains query-relevant symbols"

echo "
=== All launcher validations passed ==="
```

### 1.9 — Acceptance Criteria

- [ ] `coderag launch .` works from any project directory
- [ ] `coderag launch . --dry-run` completes without errors on 5+ real repos
- [ ] `coderag launch . --context-only` outputs valid markdown with relevant symbols
- [ ] Auto-detects installed AI tools (claude, cursor, codex)
- [ ] First run: parses project, configures MCP, generates context in <30s for small projects
- [ ] Subsequent runs: skips parse if graph is fresh, completes in <3s
- [ ] `cr` alias works after install
- [ ] Pre-loaded context includes top-20 most important files by PageRank
- [ ] CLAUDE.md contains accurate project summary
- [ ] MCP config JSON is valid and points to correct coderag serve command
- [ ] All tests pass in CI (headless, no interactive terminal)
- [ ] E2E validation script passes on Laravel, Flask, and Express repos

---

## Phase 2: Session Memory & Context Persistence (Priority: HIGH)

**Goal:** Remember what was read, edited, and queried across sessions so context compounds over time.

**Timeline:** 4-5 days

### 2.1 — Session Data Model

```python
@dataclass
class SessionEvent:
    """A single event in a coding session."""
    timestamp: datetime
    event_type: str  # "read", "edit", "query", "decision", "task"
    target: str      # file path, symbol name, or query text
    metadata: dict   # extra context (e.g., line range, query results)
    session_id: str  # groups events into sessions

@dataclass
class SessionMemory:
    """Persistent memory across coding sessions."""
    project_root: str
    sessions: list[SessionEvent]
    decisions: list[dict]     # architectural decisions made
    tasks: list[dict]         # tasks identified/completed
    facts: list[dict]         # facts learned about the codebase
    hot_files: dict[str, int] # file → access count (for prioritization)
```

### 2.2 — Storage

New SQLite tables in the existing `.codegraph/graph.db`:

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    tool TEXT,           -- "claude-code", "cursor", "codex"
    prompt TEXT,         -- initial prompt if any
    total_events INTEGER DEFAULT 0
);

CREATE TABLE session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- read, edit, query, decision, task, fact
    target TEXT NOT NULL,
    metadata TEXT,             -- JSON
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE context_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,    -- "decision", "task", "fact"
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    session_id TEXT,
    active INTEGER DEFAULT 1
);

CREATE INDEX idx_events_session ON session_events(session_id);
CREATE INDEX idx_events_type ON session_events(event_type);
CREATE INDEX idx_events_target ON session_events(target);
CREATE INDEX idx_context_category ON context_store(category);
```

### 2.3 — MCP Tools for Session Tracking

New MCP tools that AI coding assistants can call:

| Tool | Description |
|------|-------------|
| `session_log_read` | Log that a file was read |
| `session_log_edit` | Log that a file was edited |
| `session_log_decision` | Record an architectural decision |
| `session_log_task` | Record a task (identified or completed) |
| `session_log_fact` | Record a fact about the codebase |
| `session_get_history` | Get recent session history for context |
| `session_get_hot_files` | Get most frequently accessed files |
| `session_get_context` | Get persisted decisions/tasks/facts |

### 2.4 — Context Injection on Session Start

On session start, automatically inject into the AI's context:

```markdown
## Session Context (from previous sessions)

### Recent Activity (last 3 sessions)
- Edited: src/auth/login.py (3 sessions ago, 12 edits total)
- Edited: src/models/user.py (2 sessions ago, 8 edits total)
- Queried: "authentication flow" (last session)

### Hot Files (most accessed)
1. src/auth/login.py — 23 reads, 12 edits
2. src/models/user.py — 18 reads, 8 edits
3. src/api/routes.py — 15 reads, 3 edits

### Decisions
- [2026-03-20] Use JWT tokens instead of session cookies for API auth
- [2026-03-19] Migrate from SQLite to PostgreSQL for production

### Open Tasks
- [ ] Add rate limiting to login endpoint
- [ ] Write tests for password reset flow
```

### 2.5 — Implementation Tasks

| Task | File | Lines (est.) | Description |
|------|------|-------------|-------------|
| 2.5.1 | `src/coderag/session/__init__.py` | ~10 | Module init |
| 2.5.2 | `src/coderag/session/models.py` | ~80 | Data models for sessions, events, context |
| 2.5.3 | `src/coderag/session/store.py` | ~250 | SQLite storage for session data |
| 2.5.4 | `src/coderag/session/tracker.py` | ~150 | Event tracking and hot file computation |
| 2.5.5 | `src/coderag/session/injector.py` | ~200 | Context injection markdown generator |
| 2.5.6 | `src/coderag/mcp/session_tools.py` | ~300 | 8 new MCP tools for session tracking |
| 2.5.7 | `tests/test_session_store.py` | ~200 | Storage tests |
| 2.5.8 | `tests/test_session_tracker.py` | ~200 | Tracker tests |
| 2.5.9 | `tests/test_session_injector.py` | ~150 | Injection tests |
| 2.5.10 | `tests/test_session_mcp.py` | ~200 | MCP tool tests |

**Total: ~1,740 lines** (990 source + 750 tests)

### 2.6 — Validation Plan

| Step | Validation Method |
|------|------------------|
| Session creation | Create session via Python API, verify in SQLite |
| Event logging | Log 10 events, query back, verify count and order |
| Hot files | Log reads for 5 files, verify ranking |
| Context injection | Generate markdown, verify contains decisions/tasks |
| MCP tools | Call each tool via MCP test client, verify responses |
| Cross-session | Create 2 sessions, verify second sees first's data |
| Token budget | Verify injected context respects token limit |

### 2.7 — Acceptance Criteria

- [ ] Session events persisted to SQLite and queryable
- [ ] Hot files computed correctly from access history
- [ ] Decisions/tasks/facts survive across sessions
- [ ] Context injection produces token-budgeted markdown
- [ ] MCP tools allow AI to log reads/edits/decisions
- [ ] `coderag launch` injects session context automatically
- [ ] All tests pass in CI

---

## Phase 3: Token Cost Benchmarking (Priority: MEDIUM)

**Goal:** Measure and prove that CodeRAG reduces AI coding costs.

**Timeline:** 3-4 days

### 3.1 — Token Tracking System

```python
class TokenTracker:
    """Track token usage across a coding session."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self.events: list[TokenEvent] = []

    def log_context_injection(self, text: str) -> TokenEvent:
        """Log tokens used for pre-loaded context."""

    def log_tool_call(self, tool: str, input_text: str, output_text: str) -> TokenEvent:
        """Log tokens used for an MCP tool call."""

    def get_session_stats(self) -> SessionStats:
        """Get running session statistics."""
        # Returns: total_tokens, total_cost, avg_tokens_per_turn,
        #          tokens_saved_by_preload, estimated_savings_pct
```

### 3.2 — Benchmark CLI Command

```bash
# Run cost benchmark against a project
coderag benchmark /path/to/project --prompts prompts.json --model claude-sonnet

# Output (to stdout + JSON file):
# ┌─────────────────────────────────────────────────────┐
# │ CodeRAG Cost Benchmark — my-project                 │
# ├─────────────────┬──────────────┬───────────────────┤
# │ Metric          │ Without      │ With CodeRAG      │
# ├─────────────────┼──────────────┼───────────────────┤
# │ Avg tokens/turn │ 12,400       │ 7,800 (-37%)      │
# │ Avg turns/task  │ 8.2          │ 5.1 (-38%)        │
# │ Avg cost/task   │ $0.42        │ $0.24 (-43%)      │
# │ Context hits    │ N/A          │ 89% (pre-loaded)  │
# └─────────────────┴──────────────┴───────────────────┘
```

### 3.3 — Cost Models

```python
PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cached": 0.30},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0, "cached": 1.50},
    "gpt-4o": {"input": 2.50, "output": 10.0, "cached": 1.25},
    "gpt-4.1": {"input": 2.0, "output": 8.0, "cached": 0.50},
}  # per 1M tokens
```

### 3.4 — Implementation Tasks

| Task | File | Lines (est.) | Description |
|------|------|-------------|-------------|
| 3.4.1 | `src/coderag/session/token_tracker.py` | ~200 | Token counting and cost estimation |
| 3.4.2 | `src/coderag/session/cost_models.py` | ~100 | Pricing models for Claude, GPT-4, etc. |
| 3.4.3 | `src/coderag/cli/benchmark_cost.py` | ~300 | CLI command for cost benchmarking |
| 3.4.4 | `src/coderag/mcp/token_tools.py` | ~150 | MCP tools: count_tokens, get_session_stats |
| 3.4.5 | `benchmark/cost_prompts.json` | ~100 | Standard benchmark prompts |
| 3.4.6 | `tests/test_token_tracker.py` | ~200 | Tests |
| 3.4.7 | `tests/test_cost_models.py` | ~100 | Tests |

**Total: ~1,150 lines** (850 source + 300 tests)

### 3.5 — Validation Plan

| Step | Validation Method |
|------|------------------|
| Token counting | Count tokens for known strings, verify against tiktoken |
| Cost estimation | Calculate cost for known token counts, verify math |
| Benchmark output | Run on Flask repo, verify JSON + stdout output |
| MCP tools | Call count_tokens and get_session_stats via test client |

### 3.6 — Acceptance Criteria

- [ ] Token tracker counts input/output/cached tokens per turn
- [ ] Cost estimation supports Claude, GPT-4, Gemini pricing
- [ ] `coderag benchmark` produces JSON + rich table output
- [ ] Benchmark results reproducible across runs
- [ ] All tests pass in CI

---

## Phase 4: Auto-Update System (Priority: MEDIUM)

**Goal:** CodeRAG self-updates on launch, no manual intervention needed.

**Timeline:** 2-3 days

### 4.1 — Update Check on Launch

```
1. Check current version (from __version__)
2. Fetch latest version from GitHub API (cached for 1 hour in ~/.coderag/update-cache.json)
3. If newer version available:
   a. Print: "CodeRAG v2.1.0 available (current: v2.0.3). Run: coderag update"
   b. If --auto-update enabled: pull + reinstall automatically
4. Continue with launch (never blocks)
```

### 4.2 — Update Strategies

| Strategy | When | How |
|----------|------|-----|
| **PyPI** (preferred) | After PyPI publishing | `pip install --upgrade coderag` |
| **Git** (development) | Before PyPI | `git pull && pip install -e .` |

### 4.3 — Configuration

```yaml
# In ~/.coderag/config.yaml
update:
  auto_check: true          # Check for updates on launch
  auto_install: false       # Auto-install updates (opt-in)
  channel: stable           # stable | beta | dev
  check_interval: 3600      # Seconds between checks
```

### 4.4 — Implementation Tasks

| Task | File | Lines (est.) | Description |
|------|------|-------------|-------------|
| 4.4.1 | `src/coderag/updater/__init__.py` | ~10 | Module init |
| 4.4.2 | `src/coderag/updater/checker.py` | ~150 | Version check against GitHub/PyPI |
| 4.4.3 | `src/coderag/updater/installer.py` | ~100 | Auto-update execution (pip/git) |
| 4.4.4 | `src/coderag/updater/config.py` | ~50 | Update configuration |
| 4.4.5 | `install.sh` (update) | ~30 | Add auto-update hook to launcher |
| 4.4.6 | `tests/test_updater.py` | ~200 | Tests with mocked HTTP responses |

**Total: ~540 lines** (340 source + 200 tests)

### 4.5 — Validation Plan

| Step | Validation Method |
|------|------------------|
| Version check | Mock GitHub API response, verify comparison logic |
| Cache | Check cache file written, verify TTL respected |
| Update command | Mock pip install, verify correct command constructed |
| No-block | Verify launch continues even if update check fails |

### 4.6 — Acceptance Criteria

- [ ] Version check runs on every `coderag launch` (cached 1hr)
- [ ] Update notification shown when newer version exists
- [ ] `coderag update` command for manual updates
- [ ] Auto-update opt-in via config
- [ ] Update check never blocks launch (async or timeout)
- [ ] All tests pass in CI

---

## Phase 5: Integration Testing & Documentation (Priority: LOW)

**Goal:** End-to-end validation and comprehensive docs.

**Timeline:** 2-3 days

### 5.1 — E2E Test Suite

```bash
# tests/e2e/test_full_workflow.sh
# Runs against real repos, validates entire pipeline

REPOS=("laravel/framework" "pallets/flask" "expressjs/express")

for repo in "${REPOS[@]}"; do
    git clone --depth 1 "https://github.com/$repo" "/tmp/e2e-$repo"

    # Test launch --dry-run
    coderag launch "/tmp/e2e-$repo" --dry-run

    # Test context-only
    coderag launch "/tmp/e2e-$repo" "fix auth" --context-only > /tmp/ctx.md
    [ $(wc -l < /tmp/ctx.md) -gt 10 ]

    # Test config generation
    [ -f "/tmp/e2e-$repo/.claude/settings.local.json" ]
    [ -f "/tmp/e2e-$repo/CLAUDE.md" ]

    # Test session memory
    coderag session-info "/tmp/e2e-$repo"
done
```

### 5.2 — Documentation

| Document | Description |
|----------|-------------|
| `docs/quickstart.md` | 5-minute getting started guide |
| `docs/launcher.md` | Full launcher documentation |
| `docs/session-memory.md` | How session memory works |
| `docs/cost-savings.md` | Benchmark methodology and results |
| `docs/ai-tool-setup.md` | Setup guides for Claude Code, Cursor, Codex |
| `README.md` (update) | Add launcher usage, cost savings section |

### 5.3 — Implementation Tasks

| Task | File | Lines (est.) | Description |
|------|------|-------------|-------------|
| 5.3.1 | `tests/e2e/test_full_workflow.sh` | ~100 | E2E validation script |
| 5.3.2 | `docs/quickstart.md` | ~150 | Getting started guide |
| 5.3.3 | `docs/launcher.md` | ~200 | Launcher documentation |
| 5.3.4 | `docs/session-memory.md` | ~150 | Session memory docs |
| 5.3.5 | `docs/cost-savings.md` | ~100 | Cost benchmark docs |
| 5.3.6 | `docs/ai-tool-setup.md` | ~200 | AI tool setup guides |
| 5.3.7 | `README.md` (update) | ~100 | Updated README |

**Total: ~1,000 lines**

### 5.4 — Acceptance Criteria

- [ ] E2E script passes on 3+ real repos
- [ ] All documentation reviewed and accurate
- [ ] README updated with new workflow
- [ ] No feature requires interactive terminal to validate

---

## Summary

### Timeline

```
Week 1:  Phase 1 (Smart Launcher)         — 5-6 days  ← CRITICAL
Week 2:  Phase 2 (Session Memory)          — 4-5 days
Week 3:  Phase 3 (Cost Benchmarking)       — 3-4 days
Week 3:  Phase 4 (Auto-Update)             — 2-3 days
Week 4:  Phase 5 (Integration & Docs)      — 2-3 days
                                           ─────────
                                Total:     ~17-21 days
```

### Estimated Line Counts

| Phase | Source | Tests | Docs | Total |
|-------|--------|-------|------|-------|
| Phase 1: Smart Launcher | 1,180 | 850 | — | 2,030 |
| Phase 2: Session Memory | 990 | 750 | — | 1,740 |
| Phase 3: Cost Benchmarking | 850 | 300 | — | 1,150 |
| Phase 4: Auto-Update | 340 | 200 | — | 540 |
| Phase 5: Integration & Docs | 100 | 100 | 800 | 1,000 |
| **Total** | **3,460** | **2,200** | **800** | **6,460** |

This would bring CodeRAG from ~38,000 lines to ~44,500 lines.

### Key Design Decisions

#### Why `--dry-run` and `--context-only` are non-negotiable
The TUI taught us: **if you can't validate it, it doesn't exist.** Every feature
in this roadmap can be tested headlessly:
- `--dry-run` proves the pipeline works without launching an AI tool
- `--context-only` proves the context generation works by outputting to stdout
- Session memory is pure SQLite — queryable and testable
- Token tracking is math — deterministic and testable
- Auto-update is HTTP + pip — mockable and testable

#### Why not copy Dual-Graph's approach?
Dual-Graph is a thin wrapper (~51KB bash) that does simple file ranking.
CodeRAG's advantage is **deep structural understanding**. The launcher should leverage this:
- Pre-load context based on **PageRank importance**, not just file recency
- Session memory tracks **symbol-level** interactions, not just file reads
- Cost savings come from **precise context** (fewer tokens, higher relevance)

#### Session memory vs. Dual-Graph's approach
Dual-Graph stores flat JSON files. CodeRAG uses its existing SQLite infrastructure:
- Queryable session history ("what files did I edit last week?")
- Symbol-level tracking ("how many times was UserController queried?")
- Integration with graph analysis (hot files × PageRank = smart prioritization)

#### Auto-update safety
- Never auto-update during an active session
- Always show changelog before updating
- Respect `--no-update` flag for CI/CD environments
- Update check is non-blocking (timeout after 2s)
