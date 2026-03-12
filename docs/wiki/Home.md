# 🧠 CodeRAG Wiki

**Build knowledge graphs from your codebase for LLM context retrieval**

CodeRAG parses PHP, JavaScript, and TypeScript codebases into rich knowledge graphs with framework detection, cross-language analysis, and MCP server integration for AI-powered code understanding.

---

## 📖 Wiki Pages

| Page | Description |
|------|-------------|
| **[Installation](Installation)** | How to install CodeRAG on your system |
| **[MCP Server Setup](MCP-Server-Setup)** | Configure CodeRAG as an MCP server for Claude, Cursor, and other AI tools |
| **[CLI Reference](CLI-Reference)** | Complete command-line interface documentation |
| **[Configuration](Configuration)** | `codegraph.yaml` options and project setup |

---

## ✨ Key Features

- **Multi-language** — PHP, JavaScript, TypeScript with Tree-sitter AST parsing
- **25 node types & 30 edge types** for comprehensive code modeling
- **5 framework detectors** — Laravel, React, Express.js, Next.js, Vue
- **8 MCP tools** for AI agents to query the knowledge graph
- **Cross-language analysis** — PHP routes ↔ JavaScript API calls
- **Git metadata enrichment** — change frequency, co-change, ownership
- **Token-budgeted exports** — sized to fit LLM context windows

## 🔗 Links

- [GitHub Repository](https://github.com/dmnkhorvath/coderag)
- [Planning Documents (Gists)](https://gist.github.com/dmnkhorvth/9e69354c87310a2ae39edaf814e3e39e)
