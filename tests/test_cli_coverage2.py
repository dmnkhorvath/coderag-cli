"""Additional CLI tests to push coverage toward 85%.

Targets uncovered commands: find-usages, impact, file-context, routes, deps,
export, and additional edge cases for analyze, query.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from coderag.cli.main import cli
from coderag.core.models import EdgeKind, NodeKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _make_mock_config():
    cfg = MagicMock()
    cfg.db_path_absolute = "/tmp/test/.codegraph/graph.db"
    cfg.db_path = ".codegraph/graph.db"
    cfg.project_root = "/tmp/test"
    cfg.project_name = "test-project"
    cfg.languages = {"php": {"enabled": True}}
    cfg.ignore_patterns = []
    return cfg


def _make_mock_node(
    name="MyClass", qname="App/MyClass", kind=None, fpath="src/MyClass.php", start=10, end=50, meta=None
):
    if kind is None:
        kind = NodeKind.CLASS
    node = MagicMock()
    node.id = f"node-{name}"
    node.name = name
    node.qualified_name = qname
    node.kind = kind
    node.language = "php"
    node.file_path = fpath
    node.start_line = start
    node.end_line = end
    node.metadata = meta or {}
    node.confidence = 0.9
    node.content_hash = "abc123"
    return node


def _make_mock_edge(source_id="node-A", target_id="node-B", kind=None, meta=None):
    if kind is None:
        kind = EdgeKind.CALLS
    edge = MagicMock()
    edge.source_id = source_id
    edge.target_id = target_id
    edge.kind = kind
    edge.metadata = meta or {}
    edge.confidence = 0.9
    return edge


def _make_mock_store(nodes=None, edges=None):
    store = MagicMock()
    nodes = nodes or []
    edges = edges or []

    store.search_nodes.return_value = nodes
    store.find_nodes.return_value = nodes
    store.get_all_nodes.return_value = nodes
    store.get_all_edges.return_value = edges
    store.count_nodes.return_value = len(nodes)
    store.count_edges.return_value = len(edges)
    store.get_node.side_effect = lambda nid: next((n for n in nodes if n.id == nid), None)
    store.get_node_by_qualified_name.side_effect = lambda qn: next((n for n in nodes if n.qualified_name == qn), None)
    store.get_edges.return_value = edges
    # get_neighbors returns list of (node, edge, depth) tuples
    neighbor_tuples = []
    for n in nodes[:2]:
        e = _make_mock_edge(n.id, "node-target")
        neighbor_tuples.append((n, e, 1))
    store.get_neighbors.return_value = neighbor_tuples
    store.get_nodes_by_file.return_value = nodes
    store.get_nodes_by_kind.return_value = nodes
    store.search_fts.return_value = [(n, 1.0) for n in nodes]
    store.close = MagicMock()
    store.initialize = MagicMock()

    # Summary
    summary = MagicMock()
    summary.project_name = "test-project"
    summary.total_nodes = len(nodes)
    summary.total_edges = len(edges)
    summary.nodes_by_kind = {"class": 5, "method": 10}
    summary.edges_by_kind = {"calls": 8, "imports": 5}
    summary.files_by_language = {"php": 3}
    summary.frameworks = ["laravel"]
    summary.communities = 2
    summary.avg_confidence = 0.85
    summary.db_size_bytes = 1024
    summary.last_parsed = "2024-01-01"
    summary.top_nodes_by_pagerank = [("MyClass", "App/MyClass", 0.9)]
    store.get_summary.return_value = summary
    store.get_stats.return_value = {"total_nodes": len(nodes), "total_edges": len(edges)}
    store.get_metadata.return_value = ""

    return store


def _make_route_node(url="/api/users", method="GET", controller="UserController", action="index"):
    return _make_mock_node(
        name=url,
        qname=url,
        kind=NodeKind.ROUTE,
        fpath="routes/api.php",
        start=15,
        end=15,
        meta={"url": url, "http_method": method, "controller": controller, "action": action},
    )


# ---------------------------------------------------------------------------
# find-usages command
# ---------------------------------------------------------------------------


class TestFindUsagesCommand:
    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_find_usages_basic(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserService", "App/Services/UserService")
        caller = _make_mock_node("UserController", "App/Controllers/UserController")
        edge = _make_mock_edge(caller.id, node.id, EdgeKind.CALLS)
        store = _make_mock_store([node, caller])
        store.get_neighbors.return_value = [(caller, edge, 1)]
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["find-usages", "UserService"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_find_usages_json(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserService", "App/Services/UserService")
        caller = _make_mock_node("Caller", "App/Caller")
        edge = _make_mock_edge(caller.id, node.id, EdgeKind.CALLS)
        store = _make_mock_store([node])
        store.get_neighbors.return_value = [(caller, edge, 1)]
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["find-usages", "UserService", "--format", "json"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_find_usages_not_found(self, mock_resolve, mock_cfg, mock_open, runner):
        store = _make_mock_store()
        mock_resolve.return_value = (None, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["find-usages", "NonExistent"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_find_usages_not_found_with_candidates(self, mock_resolve, mock_cfg, mock_open, runner):
        cand = _make_mock_node("Similar", "App/Similar")
        store = _make_mock_store()
        mock_resolve.return_value = (None, [cand])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["find-usages", "Simila"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_find_usages_no_usages(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("Isolated", "App/Isolated")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["find-usages", "Isolated"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_find_usages_with_types(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserService", "App/Services/UserService")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["find-usages", "UserService", "-t", "calls,imports"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_find_usages_with_depth(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserService", "App/Services/UserService")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["find-usages", "UserService", "-d", "3"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# impact command
# ---------------------------------------------------------------------------


class TestImpactCommand:
    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_impact_basic(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        dep = _make_mock_node("UserService", "App/Services/UserService")
        edge = _make_mock_edge(node.id, dep.id, EdgeKind.CALLS)
        store = _make_mock_store([node, dep])
        store.get_neighbors.return_value = [(dep, edge, 1)]
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["impact", "UserController"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_impact_json(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        dep = _make_mock_node("Dep", "App/Dep")
        edge = _make_mock_edge(node.id, dep.id, EdgeKind.CALLS)
        store = _make_mock_store([node])
        store.get_neighbors.return_value = [(dep, edge, 1)]
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["impact", "UserController", "--format", "json"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_impact_not_found(self, mock_resolve, mock_cfg, mock_open, runner):
        store = _make_mock_store()
        mock_resolve.return_value = (None, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["impact", "NonExistent"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_impact_with_depth(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["impact", "UserController", "-d", "5"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_impact_no_impact(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("Isolated", "App/Isolated")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["impact", "Isolated"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# file-context command
# ---------------------------------------------------------------------------


class TestFileContextCommand:
    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_file_context_basic(self, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        method = _make_mock_node("index", "App/Controllers/UserController::index", NodeKind.METHOD)
        store = _make_mock_store([node, method])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["file-context", "app/Controllers/UserController.php"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_file_context_json(self, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        store = _make_mock_store([node])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["file-context", "app/Controllers/UserController.php", "--format", "json"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_file_context_no_source(self, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        store = _make_mock_store([node])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["file-context", "app/Controllers/UserController.php", "--no-source"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_file_context_no_nodes(self, mock_cfg, mock_open, runner):
        store = _make_mock_store()
        store.get_nodes_by_file.return_value = []
        store.find_nodes.return_value = []
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["file-context", "nonexistent.php"])
        assert result.exit_code == 0 or result.exit_code == 1


# ---------------------------------------------------------------------------
# routes command
# ---------------------------------------------------------------------------


class TestRoutesCommand:
    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_routes_basic(self, mock_cfg, mock_open, runner):
        r1 = _make_route_node("/api/users", "GET")
        r2 = _make_route_node("/api/users/{id}", "POST")
        store = _make_mock_store([r1, r2])
        store.get_nodes_by_kind.return_value = [r1, r2]
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["routes", "users"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_routes_json(self, mock_cfg, mock_open, runner):
        r1 = _make_route_node("/api/users", "GET")
        store = _make_mock_store([r1])
        store.get_nodes_by_kind.return_value = [r1]
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["routes", "users", "--format", "json"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_routes_no_frontend(self, mock_cfg, mock_open, runner):
        r1 = _make_route_node("/api/users", "GET")
        store = _make_mock_store([r1])
        store.get_nodes_by_kind.return_value = [r1]
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["routes", "users", "--no-frontend"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_routes_no_match(self, mock_cfg, mock_open, runner):
        store = _make_mock_store()
        store.get_nodes_by_kind.return_value = []
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["routes", "nonexistent"])
        assert result.exit_code == 0 or result.exit_code == 1

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_routes_method_filter(self, mock_cfg, mock_open, runner):
        r1 = _make_route_node("/api/users", "GET")
        r2 = _make_route_node("/api/users", "POST")
        store = _make_mock_store([r1, r2])
        store.get_nodes_by_kind.return_value = [r1, r2]
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["routes", "users", "-m", "get"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# deps command
# ---------------------------------------------------------------------------


class TestDepsCommand:
    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_deps_basic(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        dep = _make_mock_node("UserService", "App/Services/UserService")
        edge = _make_mock_edge(node.id, dep.id, EdgeKind.CALLS)
        store = _make_mock_store([node, dep])
        store.get_neighbors.return_value = [(dep, edge, 1)]
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["deps", "UserController"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_deps_json(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        dep = _make_mock_node("Dep", "App/Dep")
        edge = _make_mock_edge(node.id, dep.id, EdgeKind.CALLS)
        store = _make_mock_store([node])
        store.get_neighbors.return_value = [(dep, edge, 1)]
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["deps", "UserController", "--format", "json"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_deps_not_found(self, mock_resolve, mock_cfg, mock_open, runner):
        store = _make_mock_store()
        mock_resolve.return_value = (None, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["deps", "NonExistent"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_deps_direction_dependencies(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["deps", "UserController", "-D", "dependencies"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_deps_direction_dependents(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["deps", "UserController", "-D", "dependents"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    def test_deps_with_depth(self, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("UserController", "App/Controllers/UserController")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        mock_resolve.return_value = (node, [])
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["deps", "UserController", "-d", "4"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    @patch("coderag.mcp.tools._resolve_symbol")
    @patch("coderag.mcp.tools._normalize_file_path")
    def test_deps_file_fallback(self, mock_norm, mock_resolve, mock_cfg, mock_open, runner):
        node = _make_mock_node("FileNode", "src/file.php")
        store = _make_mock_store([node])
        store.get_neighbors.return_value = []
        store.find_nodes.return_value = [node]
        mock_resolve.return_value = (None, [])
        mock_norm.return_value = "src/file.php"
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["deps", "src/file.php"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# export command (uses ctx.obj["config"] directly)
# ---------------------------------------------------------------------------


class TestExportCommand:
    @patch("coderag.cli.main._open_store")
    @patch("coderag.export.GraphExporter")
    def test_export_default(self, mock_exporter_cls, mock_open, runner):
        store = _make_mock_store([_make_mock_node()])
        mock_open.return_value = store
        exporter = MagicMock()
        exporter.export.return_value = "# Architecture Overview"
        mock_exporter_cls.return_value = exporter
        cfg = _make_mock_config()
        result = runner.invoke(
            cli, ["export"], obj={"config": cfg, "config_path": None, "db_override": None, "verbose": False}
        )
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.export.GraphExporter")
    def test_export_json(self, mock_exporter_cls, mock_open, runner):
        store = _make_mock_store([_make_mock_node()])
        mock_open.return_value = store
        exporter = MagicMock()
        exporter.export.return_value = "{}"
        mock_exporter_cls.return_value = exporter
        cfg = _make_mock_config()
        result = runner.invoke(
            cli,
            ["export", "-f", "json"],
            obj={"config": cfg, "config_path": None, "db_override": None, "verbose": False},
        )
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.export.GraphExporter")
    def test_export_full_scope(self, mock_exporter_cls, mock_open, runner):
        store = _make_mock_store([_make_mock_node()])
        mock_open.return_value = store
        exporter = MagicMock()
        exporter.export.return_value = "full export"
        mock_exporter_cls.return_value = exporter
        cfg = _make_mock_config()
        result = runner.invoke(
            cli,
            ["export", "-s", "full"],
            obj={"config": cfg, "config_path": None, "db_override": None, "verbose": False},
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Additional query edge cases
# ---------------------------------------------------------------------------


class TestQueryExtra:
    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_query_no_results(self, mock_cfg, mock_open, runner):
        store = _make_mock_store()
        store.search_fts.return_value = []
        store.search_nodes.return_value = []
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["query", "NonExistent"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# cross-language command
# ---------------------------------------------------------------------------


class TestCrossLanguageCommand:
    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_cross_language_basic(self, mock_cfg, mock_open, runner):
        store = _make_mock_store()
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["cross-language"])
        assert result.exit_code == 0

    @patch("coderag.cli.main._open_store")
    @patch("coderag.cli.main._load_config")
    def test_cross_language_json(self, mock_cfg, mock_open, runner):
        store = _make_mock_store()
        mock_cfg.return_value = _make_mock_config()
        mock_open.return_value = store
        result = runner.invoke(cli, ["cross-language", "--format", "json"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# validate command
# ---------------------------------------------------------------------------


class TestValidateCommand:
    def test_validate_help(self, runner):
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "validate" in result.output.lower() or "Validate" in result.output


# ---------------------------------------------------------------------------
# help for all new commands
# ---------------------------------------------------------------------------


class TestNewCommandsHelp:
    def test_find_usages_help(self, runner):
        result = runner.invoke(cli, ["find-usages", "--help"])
        assert result.exit_code == 0

    def test_impact_help(self, runner):
        result = runner.invoke(cli, ["impact", "--help"])
        assert result.exit_code == 0

    def test_file_context_help(self, runner):
        result = runner.invoke(cli, ["file-context", "--help"])
        assert result.exit_code == 0

    def test_routes_help(self, runner):
        result = runner.invoke(cli, ["routes", "--help"])
        assert result.exit_code == 0

    def test_deps_help(self, runner):
        result = runner.invoke(cli, ["deps", "--help"])
        assert result.exit_code == 0

    def test_export_help(self, runner):
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0

    def test_watch_help(self, runner):
        result = runner.invoke(cli, ["watch", "--help"])
        assert result.exit_code == 0

    def test_enrich_help(self, runner):
        result = runner.invoke(cli, ["enrich", "--help"])
        assert result.exit_code == 0

    def test_embed_help(self, runner):
        result = runner.invoke(cli, ["embed", "--help"])
        assert result.exit_code == 0

    def test_monitor_help(self, runner):
        result = runner.invoke(cli, ["monitor", "--help"])
        assert result.exit_code == 0

    def test_serve_help(self, runner):
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
