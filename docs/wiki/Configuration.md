# Configuration

CodeRAG uses a `codegraph.yaml` file in your project root to control parsing behavior.

---

## Generating Configuration

```bash
# Interactive setup
coderag init

# Non-interactive with options
coderag init --languages php,javascript,typescript --name my-project
```

---

## Full Configuration Reference

```yaml
# codegraph.yaml
project:
  name: my-project          # Project name (used in reports)
  root: .                   # Project root directory

languages:
  php:
    enabled: true
    extensions: [".php"]
  javascript:
    enabled: true
    extensions: [".js", ".jsx", ".mjs", ".cjs"]
  typescript:
    enabled: true
    extensions: [".ts", ".tsx"]

storage:
  backend: sqlite           # Storage backend (currently only sqlite)
  path: .codegraph/graph.db # Database file path

output:
  default_format: markdown  # Default export format
  max_tokens: 8000          # Default token budget

ignore:                     # Glob patterns to ignore
  - node_modules/
  - vendor/
  - .git/
  - "*.min.js"
  - dist/
  - build/
```

---

## Configuration Options

### `project`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | string | directory name | Project name for reports and exports |
| `root` | string | `.` | Root directory for file scanning |

### `languages`

Each language section controls whether that language is parsed and which file extensions to include.

| Language | Extensions | What's Detected |
|----------|-----------|------------------|
| `php` | `.php` | Classes, interfaces, traits, enums, functions, namespaces |
| `javascript` | `.js`, `.jsx`, `.mjs`, `.cjs` | ES modules, CommonJS, JSX, classes, React components |
| `typescript` | `.ts`, `.tsx` | Interfaces, type aliases, enums, generics, decorators, TSX |

### `storage`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `backend` | string | `sqlite` | Storage backend |
| `path` | string | `.codegraph/graph.db` | Database file location |

### `output`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_format` | string | `markdown` | Default export format (`markdown`, `json`, `tree`) |
| `max_tokens` | int | `8000` | Default token budget for exports |

### `ignore`

List of glob patterns for files and directories to skip during parsing. Common patterns:

```yaml
ignore:
  - node_modules/
  - vendor/
  - .git/
  - "*.min.js"
  - "*.min.css"
  - dist/
  - build/
  - coverage/
  - __tests__/
  - "*.test.js"
  - "*.spec.ts"
```

---

## Database Location

By default, CodeRAG stores the knowledge graph at `.codegraph/graph.db` relative to your project root. This can be overridden:

1. **In config:** Set `storage.path` in `codegraph.yaml`
2. **Via CLI:** Use `--db /path/to/graph.db` on any command
3. **For MCP:** Pass `--db` to `coderag serve`

The database uses SQLite with WAL mode and FTS5 for full-text search.
