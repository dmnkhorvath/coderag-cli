from unittest.mock import MagicMock

import pytest

from coderag.core.models import Node, NodeKind
from coderag.mcp.resources import register_resources


@pytest.fixture
def mock_mcp():
    mcp = MagicMock()
    # Dictionary to store registered resource functions
    mcp.resources = {}

    def resource_decorator(uri, name, description, mime_type):
        def decorator(func):
            mcp.resources[uri] = func
            return func

        return decorator

    mcp.resource = resource_decorator
    return mcp


@pytest.fixture
def mock_store():
    store = MagicMock()

    # Mock summary
    summary = MagicMock()
    summary.project_name = "Test Project"
    summary.project_root = "/test/root"
    summary.db_path = "/test/db.sqlite"
    summary.db_size_bytes = 1024 * 1024 * 5  # 5 MB
    summary.last_parsed = "2023-01-01 12:00:00"
    summary.total_nodes = 100
    summary.total_edges = 200
    summary.communities = 5
    summary.avg_confidence = 0.95
    summary.files_by_language = {"python": 10, "javascript": 5}
    summary.nodes_by_kind = {"class": 20, "function": 80}
    summary.edges_by_kind = {"calls": 150, "contains": 50}
    summary.frameworks = ["django", "react"]
    summary.top_nodes_by_pagerank = [("MainClass", "app.MainClass", 0.15)]

    store.get_summary.return_value = summary

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
        return None

    store.get_node.side_effect = get_node

    # Mock connection for file map
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        ("src/main.py", "python", 10, "class,function"),
        ("src/utils.py", "python", 5, "function"),
        ("package.json", "json", 0, ""),
    ]
    store.connection = conn

    return store


@pytest.fixture
def mock_analyzer():
    analyzer = MagicMock()
    analyzer.community_detection.return_value = [["node1", "node2"], ["node3"]]
    analyzer.get_top_nodes.return_value = [("node1", 0.5), ("node2", 0.3)]
    analyzer.get_entry_points.return_value = ["node1"]
    analyzer.get_statistics.return_value = {
        "node_count": 100,
        "edge_count": 200,
        "is_dag": True,
        "weakly_connected_components": 2,
        "strongly_connected_components": 5,
        "isolate_count": 0,
    }
    return analyzer


def test_register_resources(mock_mcp, mock_store, mock_analyzer):
    register_resources(mock_mcp, mock_store, mock_analyzer)

    assert "coderag://summary" in mock_mcp.resources
    assert "coderag://architecture" in mock_mcp.resources
    assert "coderag://file-map" in mock_mcp.resources


def test_summary_resource(mock_mcp, mock_store, mock_analyzer):
    register_resources(mock_mcp, mock_store, mock_analyzer)

    summary_func = mock_mcp.resources["coderag://summary"]
    result = summary_func()

    assert "# CodeRAG Knowledge Graph Summary" in result
    assert "Test Project" in result
    assert "/test/root" in result
    assert "5.0 MB" in result
    assert "100" in result  # total nodes
    assert "200" in result  # total edges
    assert "python" in result
    assert "javascript" in result
    assert "django" in result
    assert "react" in result
    assert "MainClass" in result


def test_summary_resource_error(mock_mcp, mock_store, mock_analyzer):
    mock_store.get_summary.side_effect = Exception("DB Error")
    register_resources(mock_mcp, mock_store, mock_analyzer)

    summary_func = mock_mcp.resources["coderag://summary"]
    result = summary_func()

    assert "Error generating summary: DB Error" in result


def test_architecture_resource(mock_mcp, mock_store, mock_analyzer):
    register_resources(mock_mcp, mock_store, mock_analyzer)

    arch_func = mock_mcp.resources["coderag://architecture"]
    result = arch_func()

    assert "# Architecture Overview" in result
    assert "Nodes**: 100" in result
    assert "Edges**: 200" in result
    assert "DAG**: Yes" in result
    # The formatter will generate the rest, we just check it didn't crash
    assert len(result) > 100


def test_architecture_resource_error(mock_mcp, mock_store, mock_analyzer):
    mock_analyzer.get_statistics.side_effect = Exception("Analyzer Error")
    register_resources(mock_mcp, mock_store, mock_analyzer)

    arch_func = mock_mcp.resources["coderag://architecture"]
    result = arch_func()

    assert "Error generating architecture overview: Analyzer Error" in result


def test_file_map_resource(mock_mcp, mock_store, mock_analyzer):
    register_resources(mock_mcp, mock_store, mock_analyzer)

    file_map_func = mock_mcp.resources["coderag://file-map"]
    result = file_map_func()

    assert "# File Map" in result
    assert "Total files**: 3" in result
    assert "src/" in result
    assert "main.py" in result
    assert "utils.py" in result
    assert "package.json" in result
    assert "python**: 2 files" in result
    assert "json**: 1 files" in result


def test_file_map_resource_empty(mock_mcp, mock_store, mock_analyzer):
    mock_store.connection.execute.return_value.fetchall.return_value = []
    register_resources(mock_mcp, mock_store, mock_analyzer)

    file_map_func = mock_mcp.resources["coderag://file-map"]
    result = file_map_func()

    assert "No files found" in result


def test_file_map_resource_error(mock_mcp, mock_store, mock_analyzer):
    mock_store.connection.execute.side_effect = Exception("SQL Error")
    register_resources(mock_mcp, mock_store, mock_analyzer)

    file_map_func = mock_mcp.resources["coderag://file-map"]
    result = file_map_func()

    assert "Error generating file map: SQL Error" in result
