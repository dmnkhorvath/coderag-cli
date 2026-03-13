from unittest.mock import MagicMock

import networkx as nx
import pytest

from coderag.analysis.networkx_analyzer import NetworkXAnalyzer


@pytest.fixture
def analyzer():
    return NetworkXAnalyzer()


@pytest.fixture
def mock_store():
    store = MagicMock()
    conn = MagicMock()
    store.connection = conn

    # Mock nodes
    def mock_execute(query):
        if "SELECT * FROM nodes" in query:
            return [
                {
                    "id": "n1",
                    "kind": "class",
                    "name": "ClassA",
                    "qualified_name": "mod.ClassA",
                    "file_path": "a.py",
                    "start_line": 1,
                    "end_line": 10,
                    "language": "python",
                    "metadata": '{"foo": "bar"}',
                    "pagerank": 0.1,
                    "community_id": 1,
                },
                {
                    "id": "n2",
                    "kind": "function",
                    "name": "funcB",
                    "qualified_name": "mod.funcB",
                    "file_path": "b.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                    "metadata": None,
                    "pagerank": 0.2,
                    "community_id": 1,
                },
                {
                    "id": "n3",
                    "kind": "module",
                    "name": "modC",
                    "qualified_name": "modC",
                    "file_path": "c.py",
                    "start_line": 1,
                    "end_line": 2,
                    "language": "python",
                    "metadata": "invalid json",
                    "pagerank": 0.3,
                    "community_id": 2,
                },
            ]
        elif "SELECT * FROM edges" in query:
            return [
                {"source_id": "n1", "target_id": "n2", "kind": "calls", "confidence": 1.0, "metadata": '{"line": 5}'},
                {"source_id": "n2", "target_id": "n3", "kind": "imports", "confidence": 0.9, "metadata": None},
                {
                    "source_id": "n3",
                    "target_id": "n1",
                    "kind": "imports",
                    "confidence": 0.8,
                    "metadata": "invalid json",
                },
                {
                    "source_id": "n1",
                    "target_id": "missing",
                    "kind": "calls",
                    "confidence": 1.0,
                    "metadata": None,
                },  # Should be ignored
            ]
        return []

    conn.execute.side_effect = mock_execute
    return store


def test_init(analyzer):
    assert not analyzer.is_loaded
    assert analyzer.node_count == 0
    assert analyzer.edge_count == 0
    assert isinstance(analyzer.graph, nx.DiGraph)


def test_load_from_store(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    assert analyzer.is_loaded
    assert analyzer.node_count == 3
    assert analyzer.edge_count == 3

    # Check node attributes
    n1 = analyzer.graph.nodes["n1"]
    assert n1["kind"] == "class"
    assert n1["metadata"] == {"foo": "bar"}

    n2 = analyzer.graph.nodes["n2"]
    assert n2["metadata"] == {}

    n3 = analyzer.graph.nodes["n3"]
    assert n3["metadata"] == {}

    # Check edge attributes
    e1 = analyzer.graph.edges["n1", "n2"]
    assert e1["kind"] == "calls"
    assert e1["metadata"] == {"line": 5}

    e2 = analyzer.graph.edges["n2", "n3"]
    assert e2["metadata"] == {}

    e3 = analyzer.graph.edges["n3", "n1"]
    assert e3["metadata"] == {}


def test_ensure_loaded(analyzer):
    with pytest.raises(RuntimeError, match="Graph not loaded"):
        analyzer.pagerank()


def test_pagerank(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    scores = analyzer.pagerank()
    assert len(scores) == 3
    assert "n1" in scores

    # Test cache
    assert analyzer._pagerank_cache is scores
    scores2 = analyzer.pagerank()
    assert scores2 is scores

    # Test personalization
    pers = {"n1": 1.0, "n2": 0.0, "n3": 0.0}
    scores3 = analyzer.pagerank(personalization=pers)
    assert scores3 is not scores


def test_pagerank_empty(analyzer):
    analyzer._loaded = True
    assert analyzer.pagerank() == {}


def test_betweenness_centrality(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    scores = analyzer.betweenness_centrality()
    assert len(scores) == 3
    assert "n1" in scores

    # Test cache
    assert analyzer._betweenness_cache is scores
    scores2 = analyzer.betweenness_centrality()
    assert scores2 is scores


def test_betweenness_centrality_empty(analyzer):
    analyzer._loaded = True
    assert analyzer.betweenness_centrality() == {}


def test_community_detection(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    communities = analyzer.community_detection()
    assert isinstance(communities, list)
    assert len(communities) > 0
    assert isinstance(communities[0], (set, frozenset))


def test_community_detection_empty(analyzer):
    analyzer._loaded = True
    assert analyzer.community_detection() == []


def test_shortest_path(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    path = analyzer.shortest_path("n1", "n3")
    assert path == ["n1", "n2", "n3"]

    assert analyzer.shortest_path("n1", "missing") is None

    # Remove edge to test no path
    analyzer.graph.remove_edge("n2", "n3")
    assert analyzer.shortest_path("n1", "n3") is None


def test_find_cycles(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    cycles = analyzer.find_cycles()
    assert len(cycles) > 0
    assert ["n1", "n2", "n3"] in cycles or ["n2", "n3", "n1"] in cycles or ["n3", "n1", "n2"] in cycles

    # Test with edge kinds
    cycles_filtered = analyzer.find_cycles(edge_kinds=["calls"])
    assert len(cycles_filtered) == 0


def test_blast_radius(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    # n3 -> n1 -> n2 -> n3
    # Predecessors of n2 is n1
    # Predecessors of n1 is n3
    radius = analyzer.blast_radius("n2", max_depth=2)
    assert 1 in radius
    assert "n1" in radius[1]
    assert 2 in radius
    assert "n3" in radius[2]

    assert analyzer.blast_radius("missing") == {}


def test_relevance_score(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    score1 = analyzer.relevance_score("n1")
    assert 0.0 <= score1 <= 1.0

    # Test with query context
    score2 = analyzer.relevance_score("n1", query_context="classa")
    assert score2 > score1

    assert analyzer.relevance_score("missing") == 0.0


def test_get_connected_subgraph(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    subgraph = analyzer.get_connected_subgraph("n1", max_depth=1)
    assert isinstance(subgraph, nx.DiGraph)
    assert "n1" in subgraph
    assert "n2" in subgraph
    assert "n3" in subgraph

    assert analyzer.get_connected_subgraph("missing").number_of_nodes() == 0


def test_get_statistics(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    stats = analyzer.get_statistics()
    assert stats["node_count"] == 3
    assert stats["edge_count"] == 3
    assert stats["nodes_by_kind"]["class"] == 1
    assert stats["edges_by_kind"]["calls"] == 1
    assert not stats["is_dag"]  # Has cycle


def test_get_statistics_empty(analyzer):
    analyzer._loaded = True
    stats = analyzer.get_statistics()
    assert stats["node_count"] == 0


def test_get_top_nodes(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    top_pr = analyzer.get_top_nodes(metric="pagerank", limit=2)
    assert len(top_pr) == 2

    top_in = analyzer.get_top_nodes(metric="in_degree", limit=2)
    assert len(top_in) == 2

    top_out = analyzer.get_top_nodes(metric="out_degree", limit=2)
    assert len(top_out) == 2

    top_bw = analyzer.get_top_nodes(metric="betweenness", limit=2)
    assert len(top_bw) == 2

    top_filtered = analyzer.get_top_nodes(metric="pagerank", limit=10, kind_filter="class")
    assert len(top_filtered) == 1
    assert top_filtered[0][0] == "n1"

    with pytest.raises(ValueError):
        analyzer.get_top_nodes(metric="invalid")


def test_get_entry_points(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    entry_points = analyzer.get_entry_points()
    assert isinstance(entry_points, list)
    assert len(entry_points) > 0
    assert isinstance(entry_points[0], str)
    assert entry_points[0] == "n1"


def test_get_node_info(analyzer, mock_store):
    analyzer.load_from_store(mock_store)
    info = analyzer.get_node_info("n1")
    assert info["kind"] == "class"
    assert info["name"] == "ClassA"

    assert analyzer.get_node_info("missing") is None


def test_repr(analyzer):
    assert "NetworkXAnalyzer" in repr(analyzer)
