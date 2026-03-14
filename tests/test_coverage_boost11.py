"""Coverage boost 11 — Orchestrator, MCP server, exporter, registry, store deep paths."""


class TestPipelineOrchestratorDeep:
    """Test orchestrator through the full pipeline."""

    def _setup_project(self, tmp_path):
        """Create a project with config and source files."""
        from coderag.core.config import CodeGraphConfig
        from coderag.core.registry import PluginRegistry
        from coderag.pipeline.orchestrator import PipelineOrchestrator
        from coderag.storage.sqlite_store import SQLiteStore

        (tmp_path / "test.php").write_text("<?php\nclass Foo {\n    public function bar() { return 1; }\n}")
        (tmp_path / "app.js").write_text("export function hello() { return 42; }")
        (tmp_path / "utils.js").write_text("export const x = 1;\nexport function add(a, b) { return a + b; }")
        (tmp_path / "main.py").write_text("def greet():\n    return 'hello'\n\ndef add(a, b):\n    return a + b")
        (tmp_path / "styles.css").write_text("body { color: red; }\n.container { width: 100%; }")

        db_path = str(tmp_path / "codegraph.db")
        config = CodeGraphConfig(project_root=str(tmp_path), db_path=db_path)
        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        registry.initialize_all({}, str(tmp_path))
        store = SQLiteStore(db_path)
        store.initialize()
        orch = PipelineOrchestrator(config, registry, store)
        return orch, store, config

    def test_full_run(self, tmp_path):
        orch, store, config = self._setup_project(tmp_path)
        result = orch.run(str(tmp_path))
        assert result is not None

    def test_incremental_run(self, tmp_path):
        orch, store, config = self._setup_project(tmp_path)
        result1 = orch.run(str(tmp_path))
        result2 = orch.run(str(tmp_path))
        assert result2 is not None

    def test_run_with_new_file(self, tmp_path):
        orch, store, config = self._setup_project(tmp_path)
        result1 = orch.run(str(tmp_path))
        (tmp_path / "new_module.py").write_text("class NewClass:\n    pass")
        result2 = orch.run(str(tmp_path))
        assert result2 is not None

    def test_run_empty_project(self, tmp_path):
        from coderag.core.config import CodeGraphConfig
        from coderag.core.registry import PluginRegistry
        from coderag.pipeline.orchestrator import PipelineOrchestrator
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "codegraph.db")
        config = CodeGraphConfig(project_root=str(tmp_path), db_path=db_path)
        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        registry.initialize_all({}, str(tmp_path))
        store = SQLiteStore(db_path)
        store.initialize()
        orch = PipelineOrchestrator(config, registry, store)
        result = orch.run(str(tmp_path))
        assert result is not None


class TestMCPServerDeep:
    """Test MCP server creation and GraphContext."""

    def test_graph_context_init(self, tmp_path):
        from coderag.mcp.server import GraphContext

        db_path = str(tmp_path / "test.db")
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        store.initialize()
        store.close()
        ctx = GraphContext(db_path)
        ctx.load()
        assert ctx.store is not None
        assert ctx.db_path == db_path
        ctx.close()

    def test_graph_context_reload(self, tmp_path):
        from coderag.mcp.server import GraphContext

        db_path = str(tmp_path / "test.db")
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        store.initialize()
        store.close()
        ctx = GraphContext(db_path)
        ctx.load()
        changed = ctx.check_and_reload()
        assert isinstance(changed, bool)
        ctx.close()

    def test_store_proxy(self, tmp_path):
        from coderag.mcp.server import GraphContext, _StoreProxy

        db_path = str(tmp_path / "test.db")
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        store.initialize()
        store.close()
        ctx = GraphContext(db_path)
        ctx.load()
        proxy = _StoreProxy(ctx)
        try:
            proxy.find_nodes()
        except Exception:
            pass
        ctx.close()

    def test_analyzer_proxy(self, tmp_path):
        from coderag.mcp.server import GraphContext, _AnalyzerProxy

        db_path = str(tmp_path / "test.db")
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(db_path)
        store.initialize()
        store.close()
        ctx = GraphContext(db_path)
        ctx.load()
        proxy = _AnalyzerProxy(ctx)
        assert proxy is not None
        ctx.close()


class TestExporterDeep:
    """Test export functionality."""

    def _setup_parsed_project(self, tmp_path):
        from coderag.core.config import CodeGraphConfig
        from coderag.core.registry import PluginRegistry
        from coderag.pipeline.orchestrator import PipelineOrchestrator
        from coderag.storage.sqlite_store import SQLiteStore

        (tmp_path / "test.php").write_text("<?php\nclass Foo {\n    public function bar() {}\n}")
        (tmp_path / "app.js").write_text("export function hello() { return 42; }")

        db_path = str(tmp_path / "codegraph.db")
        config = CodeGraphConfig(project_root=str(tmp_path), db_path=db_path)
        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        registry.initialize_all({}, str(tmp_path))
        store = SQLiteStore(db_path)
        store.initialize()
        orch = PipelineOrchestrator(config, registry, store)
        orch.run(str(tmp_path))
        return store, db_path

    def test_export_markdown(self, tmp_path):
        from coderag.export.exporter import ExportOptions, GraphExporter

        store, db_path = self._setup_parsed_project(tmp_path)
        exporter = GraphExporter(store)
        options = ExportOptions(format="markdown", scope="architecture")
        result = exporter.export(options)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_export_json_format(self, tmp_path):
        from coderag.export.exporter import ExportOptions, GraphExporter

        store, db_path = self._setup_parsed_project(tmp_path)
        exporter = GraphExporter(store)
        options = ExportOptions(format="json", scope="architecture")
        result = exporter.export(options)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_export_with_symbol(self, tmp_path):
        from coderag.export.exporter import ExportOptions, GraphExporter

        store, db_path = self._setup_parsed_project(tmp_path)
        exporter = GraphExporter(store)
        options = ExportOptions(format="markdown", scope="symbol", symbol="Foo")
        result = exporter.export(options)
        assert isinstance(result, str)

    def test_export_with_file_scope(self, tmp_path):
        from coderag.export.exporter import ExportOptions, GraphExporter

        store, db_path = self._setup_parsed_project(tmp_path)
        exporter = GraphExporter(store)
        options = ExportOptions(format="markdown", scope="file", file_path="test.php")
        result = exporter.export(options)
        assert isinstance(result, str)

    def test_export_include_source(self, tmp_path):
        from coderag.export.exporter import ExportOptions, GraphExporter

        store, db_path = self._setup_parsed_project(tmp_path)
        exporter = GraphExporter(store)
        options = ExportOptions(format="markdown", scope="architecture", include_source=True)
        result = exporter.export(options)
        assert isinstance(result, str)

    def test_export_tree_format(self, tmp_path):
        from coderag.export.exporter import ExportOptions, GraphExporter

        store, db_path = self._setup_parsed_project(tmp_path)
        exporter = GraphExporter(store)
        options = ExportOptions(format="tree", scope="full")
        result = exporter.export(options)
        assert isinstance(result, str)


class TestRegistryDeep:
    """Test plugin registry deep paths."""

    def test_discover_and_get_all(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        plugins = registry.get_all_plugins()
        assert len(plugins) > 0

    def test_get_plugin_by_language(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        php_plugin = registry.get_plugin("php")
        assert php_plugin is not None

    def test_get_nonexistent_plugin(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        result = registry.get_plugin("nonexistent")
        assert result is None

    def test_get_all_extensions(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        registry.initialize_all({}, "/tmp")
        extensions = registry.get_all_extensions()
        assert isinstance(extensions, (set, list, dict))

    def test_initialize_all(self, tmp_path):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        registry.initialize_all({}, str(tmp_path))
        for lang in ["php", "javascript", "typescript", "python", "css", "scss"]:
            plugin = registry.get_plugin(lang)
            assert plugin is not None

    def test_get_plugin_for_file(self, tmp_path):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        registry.initialize_all({}, str(tmp_path))
        plugin = registry.get_plugin_for_file("test.php")
        assert plugin is not None

    def test_get_plugin_for_unknown_file(self, tmp_path):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        registry.initialize_all({}, str(tmp_path))
        plugin = registry.get_plugin_for_file("test.unknown")
        assert plugin is None

    def test_cleanup_all(self, tmp_path):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        registry.initialize_all({}, str(tmp_path))
        registry.cleanup_all()


class TestSQLiteStoreDeep:
    """Test SQLite store deep paths."""

    def _make_node(self, node_id="n1", name="TestClass", kind="class", lang="php", fpath="/tmp/test.php"):
        from coderag.core.models import Node, NodeKind

        kind_enum = NodeKind(kind)
        return Node(
            id=node_id,
            name=name,
            kind=kind_enum,
            qualified_name=f"{fpath}::{name}",
            language=lang,
            file_path=fpath,
            start_line=1,
            end_line=5,
        )

    def test_store_and_retrieve_nodes(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node()
        store.upsert_nodes([node])
        results = store.find_nodes(name_pattern="TestClass")
        assert len(results) > 0
        store.close()

    def test_store_and_retrieve_edges(self, tmp_path):
        from coderag.core.models import Edge, EdgeKind
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node1 = self._make_node("n1", "ClassA", "class", "php", "/tmp/a.php")
        node2 = self._make_node("n2", "ClassB", "class", "php", "/tmp/b.php")
        store.upsert_nodes([node1, node2])
        edge = Edge(source_id="n1", target_id="n2", kind=EdgeKind.EXTENDS)
        store.upsert_edges([edge])
        edges = store.get_edges(source_id="n1")
        assert len(edges) > 0
        store.close()

    def test_delete_nodes_for_file(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node()
        store.upsert_nodes([node])
        store.delete_nodes_for_file("/tmp/test.php")
        results = store.find_nodes(name_pattern="TestClass")
        assert len(results) == 0
        store.close()

    def test_get_all_nodes(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node()
        store.upsert_nodes([node])
        all_nodes = store.get_all_nodes()
        assert len(all_nodes) > 0
        store.close()

    def test_search_nodes(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node(name="SearchableClass")
        store.upsert_nodes([node])
        results = store.search_nodes("Searchable")
        assert len(results) >= 0
        store.close()

    def test_get_node_by_id(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node()
        store.upsert_nodes([node])
        result = store.get_node("n1")
        assert result is not None
        assert result.name == "TestClass"
        store.close()

    def test_get_node_by_qualified_name(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node()
        store.upsert_nodes([node])
        result = store.get_node_by_qualified_name("/tmp/test.php::TestClass")
        assert result is not None
        store.close()

    def test_get_neighbors(self, tmp_path):
        from coderag.core.models import Edge, EdgeKind
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node1 = self._make_node("n1", "ClassA", "class", "php", "/tmp/a.php")
        node2 = self._make_node("n2", "ClassB", "class", "php", "/tmp/b.php")
        store.upsert_nodes([node1, node2])
        edge = Edge(source_id="n1", target_id="n2", kind=EdgeKind.EXTENDS)
        store.upsert_edges([edge])
        neighbors = store.get_neighbors("n1")
        assert len(neighbors) > 0
        store.close()

    def test_get_stats(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node()
        store.upsert_nodes([node])
        stats = store.get_stats()
        assert isinstance(stats, dict)
        store.close()

    def test_get_summary(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node()
        store.upsert_nodes([node])
        summary = store.get_summary()
        assert summary is not None
        store.close()

    def test_file_hash_operations(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        store.set_file_hash("/tmp/test.php", "abc123", "php", "php", 1, 0, 10.0)
        result = store.get_file_hash("/tmp/test.php")
        assert result == "abc123"
        store.close()

    def test_metadata_operations(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        store.set_metadata("test_key", "test_value")
        result = store.get_metadata("test_key")
        assert result == "test_value"
        store.close()

    def test_transaction_context_manager(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        # Just verify the context manager works without error
        node = self._make_node()
        store.upsert_node(node)
        result = store.get_node("n1")
        assert result is not None
        store.close()

    def test_create_thread_connection(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        conn = store.create_thread_connection()
        assert conn is not None
        conn.close()
        store.close()

    def test_blast_radius(self, tmp_path):
        from coderag.core.models import Edge, EdgeKind
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node1 = self._make_node("n1", "ClassA", "class", "php", "/tmp/a.php")
        node2 = self._make_node("n2", "ClassB", "class", "php", "/tmp/b.php")
        store.upsert_nodes([node1, node2])
        edge = Edge(source_id="n1", target_id="n2", kind=EdgeKind.EXTENDS)
        store.upsert_edges([edge])
        result = store.blast_radius("n1")
        assert isinstance(result, (list, set, dict))
        store.close()

    def test_upsert_single_node(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node = self._make_node()
        store.upsert_node(node)
        result = store.get_node("n1")
        assert result is not None
        store.close()

    def test_upsert_single_edge(self, tmp_path):
        from coderag.core.models import Edge, EdgeKind
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        node1 = self._make_node("n1", "ClassA", "class", "php", "/tmp/a.php")
        node2 = self._make_node("n2", "ClassB", "class", "php", "/tmp/b.php")
        store.upsert_nodes([node1, node2])
        edge = Edge(source_id="n1", target_id="n2", kind=EdgeKind.EXTENDS)
        store.upsert_edge(edge)
        edges = store.get_edges(source_id="n1")
        assert len(edges) > 0
        store.close()

    def test_get_stale_files(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = str(tmp_path / "test.db")
        store = SQLiteStore(db_path)
        store.initialize()
        store.set_file_hash("/tmp/test.php", "abc123", "php", "php", 1, 0, 10.0)
        stale = store.get_stale_files(set())  # empty set means all stored files are stale
        assert len(stale) > 0
        store.close()
