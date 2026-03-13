from unittest.mock import MagicMock, patch

import pytest

from coderag.core.models import Node, NodeKind
from coderag.mcp.tools import (
    HttpMethod,
    _normalize_file_path,
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


def test_normalize_file_path_like(mock_store):
    # Test line 159
    mock_store.connection.execute.return_value.fetchone.return_value = ("src/file1.py",)
    assert _normalize_file_path("file1.py", mock_store) == "src/file1.py"


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


def test_search_semantic_and_fts(mock_mcp, mock_store, mock_analyzer):
    register_tools(mock_mcp, mock_store, mock_analyzer)
    search = mock_mcp.tools["coderag_search"]

    # Test semantic search logic
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

        mock_sr = MagicMock()
        mock_sr.qualified_name = "Class1"
        mock_sr.name = "Class1"
        mock_sr.kind = "class"
        mock_sr.language = "python"
        mock_sr.file_path = "file.py"
        mock_sr.score = 0.9
        mock_sr.match_type = "semantic"
        mock_sr.vector_similarity = 0.9

        mock_hybrid_instance.search_semantic.return_value = [mock_sr]

        result = search("query", mode="semantic")
        assert "Class1" in result

    node1 = Node(
        id="1",
        kind=NodeKind.CLASS,
        name="Class1",
        qualified_name="Class1",
        file_path="file.py",
        start_line=1,
        end_line=2,
        language="python",
    )

    # Test semantic search logic
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
        mock_sr2 = MagicMock()
        mock_sr2.qualified_name = "Class1"
        mock_sr2.name = "Class1"
        mock_sr2.kind = "class"
        mock_sr2.language = "python"
        mock_sr2.file_path = "file.py"
        mock_sr2.score = 0.9
        mock_sr2.match_type = "semantic"
        mock_sr2.vector_similarity = 0.9
        mock_hybrid_instance.search_semantic.return_value = [mock_sr2]

        result = search("query", mode="semantic")
        assert "Class1" in result

    node1 = mock_store.get_node("node1")

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
        mock_sr3 = MagicMock()
        mock_sr3.qualified_name = "Class1"
        mock_sr3.name = "Class1"
        mock_sr3.kind = "class"
        mock_sr3.language = "python"
        mock_sr3.file_path = "file.py"
        mock_sr3.score = 0.9
        mock_sr3.match_type = "semantic"
        mock_sr3.vector_similarity = 0.9
        mock_hybrid_instance.search_semantic.return_value = [mock_sr3]

        result = search("query", mode="semantic")
        print("SEMANTIC RESULT:", result)
        assert "Class1" in result


def test_search_semantic_and_fts_extended(mock_mcp, mock_store, mock_analyzer):
    register_tools(mock_mcp, mock_store, mock_analyzer)
    search = mock_mcp.tools["coderag_search"]

    # Test semantic search logic
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

        mock_sr = MagicMock()
        mock_sr.qualified_name = "Class1"
        mock_sr.name = "Class1"
        mock_sr.kind = "class"
        mock_sr.language = "python"
        mock_sr.file_path = "file.py"
        mock_sr.score = 0.9
        mock_sr.match_type = "semantic"
        mock_sr.vector_similarity = 0.9

        mock_hybrid_instance.search_semantic.return_value = [mock_sr]

        result = search("query", mode="semantic")
        assert "Class1" in result
