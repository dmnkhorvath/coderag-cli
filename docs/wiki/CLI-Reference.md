# CLI Reference

Complete command-line interface documentation for CodeRAG.

---

## Global Options

```bash
coderag [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | Path to `codegraph.yaml` config file |
| `--db PATH` | Override database path |
| `-v, --verbose` | Increase verbosity (repeat for more: `-vv`, `-vvv`) |
| `--help` | Show help message |

---

## Commands

### `coderag init`

Initialize a `codegraph.yaml` configuration file in the current directory.

```bash
coderag init                                    # Interactive setup
coderag init --languages php,typescript         # Specify languages
coderag init --name "my-project"                # Set project name
```

| Option | Description |
|--------|-------------|
| `--languages` | Comma-separated list of languages (php, javascript, typescript) |
| `--name` | Project name (defaults to directory name) |

---

### `coderag parse`

Parse a codebase and build the knowledge graph.

```bash
coderag parse .                                 # Parse current directory
coderag parse /path/to/project                  # Parse specific project
coderag parse . --incremental                   # Only re-parse changed files
coderag parse . --parallel                      # Use parallel extraction
```

| Option | Description |
|--------|-------------|
| `--incremental` | Only re-parse files that changed since last parse |
| `--parallel` | Use parallel file extraction (ThreadPoolExecutor) |

---

### `coderag info`

Display knowledge graph statistics.

```bash
coderag info .                                  # Show graph summary
coderag info . --json                           # Output as JSON
```

---

### `coderag query`

Query the knowledge graph for symbols and relationships.

```bash
coderag query --name "User" .                   # Search by name
coderag query --name "UserController" --kind class .  # Filter by kind
coderag query --name "App\Models\User" --depth 2 .    # Traverse neighbors
```

| Option | Default | Description |
|--------|---------|-------------|
| `--name, -s` | required | Symbol name to search |
| `--kind` | all | Filter by node kind (class, function, etc.) |
| `--depth` | `1` | Neighbor traversal depth |
| `--format` | `rich` | Output format (`rich` or `json`) |
| `--limit` | `20` | Max results |

---

### `coderag export`

Export knowledge graph data in various formats.

```bash
coderag export                                  # Architecture overview (markdown)
coderag export -f json -s full                  # Full graph as JSON
coderag export -s symbol --symbol User          # Symbol context
coderag export -s file --file app/User.php      # File context
coderag export -f tree -s full                  # Repository map tree view
coderag export --tokens 16000 -o out.md         # Custom token budget
```

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `-f, --format` | `markdown`, `json`, `tree` | `markdown` | Output format |
| `-s, --scope` | `full`, `architecture`, `file`, `symbol` | `architecture` | Export scope |
| `--symbol` | string | — | Symbol name (for symbol scope) |
| `--file` | path | — | File path (for file scope) |
| `--tokens` | int | `8000` | Token budget |
| `--top` | int | `20` | Top N items for architecture |
| `--depth` | int | `2` | Traversal depth for symbol scope |
| `-o, --output` | path | stdout | Output file path |

---

### `coderag analyze`

Run graph analysis algorithms (PageRank, community detection, blast radius).

```bash
coderag analyze .                               # Full analysis
coderag analyze . --top 20                      # Show top 20 results
```

---

### `coderag architecture`

Generate architecture overview with community detection.

```bash
coderag architecture .                          # Architecture report
```

---

### `coderag frameworks`

Detect and report framework usage.

```bash
coderag frameworks .                            # Detect all frameworks
```

---

### `coderag cross-language`

Analyze cross-language connections (PHP routes ↔ JS API calls).

```bash
coderag cross-language .                        # Find cross-language matches
coderag cross-language . --min-confidence 0.8   # Higher confidence threshold
```

---

### `coderag enrich`

Enrich the knowledge graph with additional metadata.

```bash
coderag enrich --phpstan                        # Run PHPStan enrichment
coderag enrich --phpstan --level 8              # Custom analysis level (0-9)
coderag enrich --phpstan --phpstan-path vendor/bin/phpstan  # Custom binary
```

---

### `coderag serve`

Start the MCP server for AI agent integration.

```bash
coderag serve .                                 # Start with stdio transport
coderag serve . --db custom/graph.db            # Custom database path
coderag serve . --no-reload                     # Disable hot-reload
```

See the **[MCP Server Setup](MCP-Server-Setup)** page for detailed configuration.
