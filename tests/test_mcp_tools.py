from unittest.mock import MagicMock, patch

import pytest

from coderag.core.models import Edge, EdgeKind, Node, NodeKind
from coderag.mcp.tools import (
    ArchitectureFocus,
    DependencyDirection,
    HttpMethod,
    _normalize_file_path,
    _truncate_to_budget,
    register_tools,
)


@pytest.fixture
def mock_mcp():
    mcp = MagicMock()
    mcp.tools = {}

    def tool_decorator(name=None, description=None):
        def decorator(func):
            tool_name = name or func.__name__
            mcp.tools[tool_name] = func
            return func

        return decorator

    mcp.tool = tool_decorator
    return mcp


@pytest.fixture
def mock_store():
    store = MagicMock()

    # Mock get_node
    def get_node(nid):
        if nid == "node1":
            return Node(
                id="node1",
                kind=NodeKind.CLASS,
                name="Class1",
                qualified_name="pkg.Class1",
                file_path="file1.py",
                start_line=1,
                end_line=10,
                language="python",
                docblock="First line\nSecond line",
            )
        elif nid == "node2":
            return Node(
                id="node2",
                kind=NodeKind.FUNCTION,
                name="func1",
                qualified_name="pkg.func1",
                file_path="file2.py",
                start_line=1,
                end_line=5,
                language="python",
            )
        elif nid == "route1":
            return Node(
                id="route1",
                kind=NodeKind.ROUTE,
                name="GET /api/users",
                qualified_name="GET /api/users",
                file_path="routes.py",
                start_line=1,
                end_line=5,
                language="python",
                metadata={"url": "/api/users", "http_method": "GET"},
            )
        elif nid == "route2":
            return Node(
                id="route2",
                kind=NodeKind.ROUTE,
                name="POST /api/users",
                qualified_name="POST /api/users",
                file_path="routes.py",
                start_line=6,
                end_line=10,
                language="python",
                metadata={"url": "/api/users", "http_method": "POST"},
            )
        elif nid == "frontend_caller":
            return Node(
                id="frontend_caller",
                kind=NodeKind.FUNCTION,
                name="fetchUsers",
                qualified_name="fetchUsers",
                file_path="api.js",
                start_line=1,
                end_line=5,
                language="javascript",
            )
        return None

    store.get_node.side_effect = get_node
    store.find_nodes.return_value = []

    # Mock connection for _normalize_file_path
    conn = MagicMock()
    store.connection = conn

    return store


@pytest.fixture
def mock_analyzer():
    analyzer = MagicMock()
    return analyzer


def test_truncate_to_budget():
    # Test line 98
    text = "a" * 350
    budget = 100
    # max_chars = 350
    # len(text) <= max_chars -> returns text
    assert _truncate_to_budget(text, budget) == text


def test_normalize_file_path_like(mock_store):
    # Test line 159
    mock_store.connection.execute.return_value.fetchone.return_value = ("src/file1.py",)
    assert _normalize_file_path("file1.py", mock_store) == "src/file1.py"


def test_find_usages_filters_and_depth(mock_mcp, mock_store, mock_analyzer):
    register_tools(mock_mcp, mock_store, mock_analyzer)
    find_usages = mock_mcp.tools["coderag_find_usages"]

    # Mock resolve_symbol
    with patch("coderag.mcp.tools._resolve_symbol") as mock_resolve:
        node1 = Node(
            id="node1",
            kind=NodeKind.CLASS,
            name="Class1",
            qualified_name="pkg.Class1",
            file_path="file1.py",
            start_line=1,
            end_line=10,
            language="python",
        )
        mock_resolve.return_value = (node1, [])

        # Test no usages (lines 267-268)
        mock_store.get_neighbors.return_value = []
        result = find_usages("Class1", usage_types=None, max_depth=1)
        assert "No usages found" in result

        # Test with usage_types and depth grouping (lines 254-256, 285, 288-302)
        class UsageType:
            def __init__(self, value):
                self.value = value

        node2 = Node(
            id="node2",
            kind=NodeKind.FUNCTION,
            name="func1",
            qualified_name="pkg.func1",
            file_path="file2.py",
            start_line=1,
            end_line=5,
            language="python",
        )
        mock_store.get_neighbors.return_value = [
            (node2, Edge(source_id="node2", target_id="node1", kind=EdgeKind.CALLS), 1),
            (node2, Edge(source_id="node2", target_id="node1", kind=EdgeKind.IMPORTS), 2),
        ]

        result = find_usages("Class1", usage_types=[UsageType("calls")], max_depth=2)
        assert "Depth 1" in result
        assert "Depth 2" in result
        assert "calls" in result
        assert "imports" in result


def test_file_context_not_found(mock_mcp, mock_store, mock_analyzer):
    register_tools(mock_mcp, mock_store, mock_analyzer)
    file_context = mock_mcp.tools["coderag_file_context"]

    with patch("coderag.mcp.tools._normalize_file_path") as mock_norm:
        mock_norm.return_value = None
        mock_store.connection.execute.return_value.fetchall.return_value = []

        # Test line 387
        result = file_context("nonexistent.py")
        assert "not found in the knowledge graph" in result


def test_find_routes(mock_mcp, mock_store, mock_analyzer):
    register_tools(mock_mcp, mock_store, mock_analyzer)
    find_routes = mock_mcp.tools["coderag_find_routes"]

    route1 = mock_store.get_node("route1")
    route2 = mock_store.get_node("route2")
    mock_store.find_nodes.return_value = [route1, route2]

    # Test HTTP method filter (lines 441-443)
    result = find_routes("/api/users", http_method=HttpMethod.GET)
    assert "GET `/api/users`" in result
    assert "POST `/api/users`" not in result

    # Test no routes matched (line 447)
    result = find_routes("/api/users", http_method=HttpMethod.PUT)
    assert "No routes matching" in result

    # Test outgoing edges and frontend callers (lines 478-481, 493-498)
    mock_store.get_edges.side_effect = lambda source_id=None, target_id=None: (
        [Edge(source_id="route1", target_id="node2", kind=EdgeKind.CALLS)]
        if source_id
        else [
            Edge(
                source_id="frontend_caller",
                target_id="route1",
                kind=EdgeKind.API_CALLS,
                metadata={"call_url": "/api/users"},
            )
        ]
    )

    result = find_routes("/api/users", http_method=HttpMethod.GET, include_frontend=True)
    assert "pkg.func1" in result  # Outgoing edge target
    assert "Frontend callers" in result
    assert "fetchUsers" in result


def test_search_semantic_and_fts(mock_mcp, mock_store, mock_analyzer):
    register_tools(mock_mcp, mock_store, mock_analyzer)
    search = mock_mcp.tools["coderag_search"]

    # Test FTS fallback with node_types and docblock (lines 612-622, 652-653)
    node1 = mock_store.get_node("node1")
    mock_store.search_nodes.return_value = [node1]

    result = search("query", node_types=["class"], mode="fts")
    assert "Class1" in result
    assert "First line" in result
    assert "Second line" not in result  # Only first line of docblock

    # Test semantic search logic (lines 555-560, 563-607)
    import coderag.search

    coderag.search.SEMANTIC_AVAILABLE = True

    with (
        patch("coderag.search.vector_store.VectorStore") as mock_vs,
        patch("coderag.search.embedder.CodeEmbedder"),
        patch("coderag.search.hybrid.HybridSearcher") as mock_hybrid,
    ):
        mock_vs.exists.return_value = True
        mock_hybrid_instance = MagicMock()
        mock_hybrid.return_value = mock_hybrid_instance

        # Mock search_semantic instead of search
        class MockResult:
            def __init__(self):
                self.qualified_name = "pkg.Class1"
                self.name = "Class1"
                self.kind = "class"
                self.language = "python"
                self.file_path = "file1.py"
                self.score = 0.9
                self.match_type = "semantic"
                self.vector_similarity = 0.9

        mock_hybrid_instance.search_semantic.return_value = [MockResult()]

        result = search("query", mode="semantic")
        assert "Class1" in result


def test_architecture_focus(mock_mcp, mock_store, mock_analyzer):
    register_tools(mock_mcp, mock_store, mock_analyzer)
    architecture = mock_mcp.tools["coderag_architecture"]

    mock_analyzer.community_detection.return_value = [["node1", "node2", "frontend_caller"]]
    mock_analyzer.get_top_nodes.return_value = [("node1", 0.9), ("node2", 0.8), ("frontend_caller", 0.7)]
    mock_analyzer.get_entry_points.return_value = ["node1", "frontend_caller"]

    with patch("coderag.output.markdown.MarkdownFormatter") as mock_formatter:
        mock_formatter_instance = MagicMock()
        mock_formatter.return_value = mock_formatter_instance
        mock_formatter_instance.format_architecture_overview.return_value = "Arch Overview"

        # Test backend focus (lines 694, 722-726, 736-740, 748-752, 763)
        result = architecture(focus=ArchitectureFocus.backend)
        assert "Focus: backend" in result

        # Test frontend focus
        result = architecture(focus=ArchitectureFocus.frontend)
        assert "Focus: frontend" in result

        # Test api_layer focus
        result = architecture(focus=ArchitectureFocus.api_layer)
        assert "Focus: api_layer" in result

        # Test data_layer focus
        result = architecture(focus=ArchitectureFocus.data_layer)
        assert "Focus: data_layer" in result


def test_dependency_graph(mock_mcp, mock_store, mock_analyzer):
    register_tools(mock_mcp, mock_store, mock_analyzer)
    dependency_graph = mock_mcp.tools["coderag_dependency_graph"]

    with (
        patch("coderag.mcp.tools._resolve_symbol") as mock_resolve,
        patch("coderag.mcp.tools._normalize_file_path") as mock_norm,
    ):
        # Test resolving target as file path (lines 807-809)
        mock_resolve.return_value = (None, [])
        mock_norm.return_value = "file1.py"
        node1 = mock_store.get_node("node1")
        mock_store.find_nodes.return_value = [node1]

        # Test no dependencies/dependents (lines 845, 870)
        mock_store.get_neighbors.return_value = []

        result = dependency_graph("file1.py", direction=DependencyDirection.both)
        assert "No dependencies found" in result
        assert "No dependents found" in result

        # Test candidates (line 813)
        mock_resolve.return_value = (None, [node1])
        mock_norm.return_value = None
        mock_store.find_nodes.return_value = []

        result = dependency_graph("ambiguous")
        assert "Did you mean one of these?" in result
