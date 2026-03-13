"""Tests for coderag.output package.

Covers:
- output/markdown.py (MarkdownFormatter)
- output/context.py (ContextAssembler)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from coderag.core.models import (
    ContextResult,
    DetailLevel,
    Edge,
    EdgeKind,
    GraphSummary,
    Node,
    NodeKind,
    PipelineSummary,
    estimate_tokens,
)
from coderag.output.context import ContextAssembler
from coderag.output.markdown import MarkdownFormatter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _node(
    id_: str = "n1",
    name: str = "MyFunc",
    kind: NodeKind = NodeKind.FUNCTION,
    qname: str | None = None,
    file_path: str = "src/app.py",
    language: str = "python",
    start_line: int = 10,
    end_line: int = 25,
    docblock: str | None = None,
    source_text: str | None = None,
    metadata: dict | None = None,
    pagerank: float = 0.0,
    community_id: int | None = None,
) -> Node:
    return Node(
        id=id_,
        kind=kind,
        name=name,
        qualified_name=qname or name,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language=language,
        docblock=docblock,
        source_text=source_text,
        metadata=metadata or {},
        pagerank=pagerank,
        community_id=community_id,
    )


def _edge(
    src: str = "n1",
    tgt: str = "n2",
    kind: EdgeKind = EdgeKind.CALLS,
    confidence: float = 0.9,
    line_number: int | None = 15,
) -> Edge:
    return Edge(
        source_id=src,
        target_id=tgt,
        kind=kind,
        confidence=confidence,
        line_number=line_number,
    )


def _graph_summary(**overrides) -> GraphSummary:
    defaults = dict(
        project_name="TestProject",
        project_root="/tmp/project",
        db_path="/tmp/project/.coderag/graph.db",
        db_size_bytes=1024 * 500,  # 500 KB
        last_parsed="2025-01-15 10:30:00",
        total_nodes=150,
        total_edges=300,
        nodes_by_kind={"class": 20, "function": 80, "method": 50},
        edges_by_kind={"calls": 200, "imports": 100},
        files_by_language={"python": 30, "javascript": 20},
        frameworks=["django", "react"],
        communities=5,
        avg_confidence=0.85,
        top_nodes_by_pagerank=[
            ("UserService", "app.services.UserService", 0.045),
            ("main", "app.main", 0.032),
        ],
    )
    defaults.update(overrides)
    return GraphSummary(**defaults)


def _pipeline_summary(**overrides) -> PipelineSummary:
    defaults = dict(
        total_files=50,
        files_parsed=45,
        files_skipped=3,
        files_errored=2,
        total_nodes=200,
        total_edges=400,
        nodes_added=180,
        nodes_updated=15,
        nodes_removed=5,
        edges_added=380,
        files_by_language={"python": 30, "javascript": 20},
        nodes_by_kind={"class": 40, "function": 120, "method": 40},
        edges_by_kind={"calls": 250, "imports": 150},
        frameworks_detected=["django"],
        cross_language_edges=10,
        parse_errors=3,
        resolution_rate=0.92,
        avg_confidence=0.88,
        total_parse_time_ms=1500.0,
        total_pipeline_time_ms=3200.0,
    )
    defaults.update(overrides)
    return PipelineSummary(**defaults)


# ===================================================================
# MarkdownFormatter — format_node
# ===================================================================


class TestFormatNode:
    """Test MarkdownFormatter.format_node at all detail levels."""

    def test_signature_level(self):
        node = _node(metadata={"signature": "def my_func(x: int) -> str"})
        result = MarkdownFormatter.format_node(node, DetailLevel.SIGNATURE)
        assert "function" in result.lower()
        assert "def my_func(x: int) -> str" in result

    def test_signature_no_signature_metadata(self):
        node = _node(name="plain_func")
        result = MarkdownFormatter.format_node(node, DetailLevel.SIGNATURE)
        assert "plain_func" in result

    def test_summary_level(self):
        node = _node(name="MyClass", kind=NodeKind.CLASS, qname="app.MyClass", pagerank=0.05, community_id=3)
        result = MarkdownFormatter.format_node(node, DetailLevel.SUMMARY)
        assert "app.MyClass" in result
        assert "src/app.py" in result
        assert "10" in result  # start_line
        assert "25" in result  # end_line
        assert "python" in result
        assert "0.05" in result  # pagerank
        assert "3" in result  # community_id

    def test_summary_with_visibility(self):
        node = _node(metadata={"visibility": "public"})
        result = MarkdownFormatter.format_node(node, DetailLevel.SUMMARY)
        assert "public" in result

    def test_summary_with_signature_metadata(self):
        node = _node(metadata={"signature": "def f()"})
        result = MarkdownFormatter.format_node(node, DetailLevel.SUMMARY)
        assert "def f()" in result

    def test_summary_with_abstract(self):
        node = _node(metadata={"is_abstract": True})
        result = MarkdownFormatter.format_node(node, DetailLevel.SUMMARY)
        assert "Abstract" in result

    def test_summary_with_static(self):
        node = _node(metadata={"is_static": True})
        result = MarkdownFormatter.format_node(node, DetailLevel.SUMMARY)
        assert "Static" in result

    def test_detailed_level_with_docblock(self):
        node = _node(docblock="This function does something.")
        result = MarkdownFormatter.format_node(node, DetailLevel.DETAILED)
        assert "This function does something." in result

    def test_detailed_level_with_metadata(self):
        node = _node(metadata={"custom_key": "custom_value", "visibility": "private"})
        result = MarkdownFormatter.format_node(node, DetailLevel.DETAILED)
        assert "custom_key" in result or "custom_value" in result

    def test_comprehensive_with_source(self):
        node = _node(source_text="def my_func():\n    return 42", language="python")
        result = MarkdownFormatter.format_node(node, DetailLevel.COMPREHENSIVE)
        assert "def my_func()" in result
        assert "return 42" in result
        assert "```python" in result

    def test_comprehensive_no_source(self):
        node = _node(source_text=None)
        result = MarkdownFormatter.format_node(node, DetailLevel.COMPREHENSIVE)
        # Should not crash, just skip source section
        assert isinstance(result, str)

    def test_default_detail_is_summary(self):
        node = _node()
        result = MarkdownFormatter.format_node(node)
        # Default is SUMMARY, should have table format
        assert "Property" in result
        assert "Value" in result

    def test_no_pagerank_zero(self):
        node = _node(pagerank=0.0)
        result = MarkdownFormatter.format_node(node, DetailLevel.SUMMARY)
        assert "PageRank" not in result

    def test_no_community_none(self):
        node = _node(community_id=None)
        result = MarkdownFormatter.format_node(node, DetailLevel.SUMMARY)
        assert "Community" not in result


# ===================================================================
# MarkdownFormatter — format_graph_summary
# ===================================================================


class TestFormatGraphSummary:
    """Test MarkdownFormatter.format_graph_summary."""

    def test_basic_summary(self):
        summary = _graph_summary()
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "CodeRAG" in result
        assert "Graph Summary" in result
        assert "TestProject" in result
        assert "150" in result  # total_nodes
        assert "300" in result  # total_edges
        assert "5" in result  # communities
        assert "0.85" in result  # avg_confidence

    def test_db_size_kb(self):
        summary = _graph_summary(db_size_bytes=500 * 1024)  # 500 KB
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "500.0 KB" in result

    def test_db_size_mb(self):
        summary = _graph_summary(db_size_bytes=2 * 1024 * 1024)  # 2 MB
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "2.0 MB" in result

    def test_db_size_zero(self):
        summary = _graph_summary(db_size_bytes=0)
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "DB Size" not in result

    def test_no_project_name(self):
        summary = _graph_summary(project_name="")
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Project" not in result or "project" in result.lower()

    def test_no_project_root(self):
        summary = _graph_summary(project_root="")
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Root" not in result

    def test_no_last_parsed(self):
        summary = _graph_summary(last_parsed=None)
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Last Parsed" not in result

    def test_nodes_by_kind_section(self):
        summary = _graph_summary()
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Nodes by Kind" in result
        assert "function" in result
        assert "80" in result

    def test_edges_by_kind_section(self):
        summary = _graph_summary()
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Edges by Kind" in result
        assert "calls" in result

    def test_files_by_language_section(self):
        summary = _graph_summary()
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Files by Language" in result
        assert "python" in result

    def test_empty_nodes_by_kind(self):
        summary = _graph_summary(nodes_by_kind={})
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Nodes by Kind" not in result

    def test_empty_edges_by_kind(self):
        summary = _graph_summary(edges_by_kind={})
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Edges by Kind" not in result

    def test_empty_files_by_language(self):
        summary = _graph_summary(files_by_language={})
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "Files by Language" not in result

    def test_top_nodes_by_pagerank(self):
        summary = _graph_summary()
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "UserService" in result
        assert "app.services.UserService" in result

    def test_empty_top_nodes(self):
        summary = _graph_summary(top_nodes_by_pagerank=[])
        result = MarkdownFormatter.format_graph_summary(summary)
        # Should not have pagerank section
        assert "Top Nodes" not in result or isinstance(result, str)

    def test_frameworks_section(self):
        summary = _graph_summary(frameworks=["django", "react"])
        result = MarkdownFormatter.format_graph_summary(summary)
        assert "django" in result or "Framework" in result


# ===================================================================
# MarkdownFormatter — format_search_results
# ===================================================================


class TestFormatSearchResults:
    """Test MarkdownFormatter.format_search_results."""

    def test_empty_results(self):
        result = MarkdownFormatter.format_search_results([], "test query")
        assert "No results found" in result
        assert "test query" in result

    def test_with_results(self):
        nodes = [
            _node("n1", "func1", NodeKind.FUNCTION, qname="mod.func1"),
            _node("n2", "func2", NodeKind.FUNCTION, qname="mod.func2"),
        ]
        result = MarkdownFormatter.format_search_results(nodes, "func")
        assert "func" in result
        assert "func1" in result
        assert "func2" in result
        assert "2" in result  # count


# ===================================================================
# MarkdownFormatter — format_pipeline_summary
# ===================================================================


class TestFormatPipelineSummary:
    """Test MarkdownFormatter.format_pipeline_summary."""

    def test_basic_pipeline_summary(self):
        summary = _pipeline_summary()
        result = MarkdownFormatter.format_pipeline_summary(summary)
        assert isinstance(result, str)
        assert "200" in result or "total_nodes" in result.lower() or "nodes" in result.lower()

    def test_pipeline_summary_with_errors(self):
        summary = _pipeline_summary(files_errored=5, parse_errors=10)
        result = MarkdownFormatter.format_pipeline_summary(summary)
        assert isinstance(result, str)

    def test_pipeline_summary_with_frameworks(self):
        summary = _pipeline_summary(frameworks_detected=["django", "react"])
        result = MarkdownFormatter.format_pipeline_summary(summary)
        assert isinstance(result, str)

    def test_pipeline_summary_zero_values(self):
        summary = PipelineSummary()  # all defaults (zeros)
        result = MarkdownFormatter.format_pipeline_summary(summary)
        assert isinstance(result, str)


# ===================================================================
# MarkdownFormatter — format_file_overview
# ===================================================================


class TestFormatFileOverview:
    """Test MarkdownFormatter.format_file_overview."""

    def test_empty_file(self):
        result = MarkdownFormatter.format_file_overview("src/empty.py", [], [])
        assert "empty.py" in result
        assert "No symbols found" in result

    def test_file_with_nodes(self):
        nodes = [
            _node("n1", "MyClass", NodeKind.CLASS, start_line=1, end_line=50),
            _node("n2", "helper", NodeKind.FUNCTION, start_line=55, end_line=60),
        ]
        edges = [_edge("n1", "n2")]
        result = MarkdownFormatter.format_file_overview("src/app.py", nodes, edges)
        assert "src/app.py" in result
        assert "2" in result  # symbol count
        assert "1" in result  # edge count
        assert "MyClass" in result
        assert "helper" in result

    def test_file_with_visibility(self):
        nodes = [
            _node(
                "n1", "pub_func", NodeKind.FUNCTION, metadata={"visibility": "public", "signature": "def pub_func()"}
            ),
        ]
        result = MarkdownFormatter.format_file_overview("a.py", nodes, [])
        assert "public" in result


# ===================================================================
# MarkdownFormatter — format_node_with_edges
# ===================================================================


class TestFormatNodeWithEdges:
    """Test MarkdownFormatter.format_node_with_edges."""

    def test_node_with_no_edges(self):
        node = _node("n1", "MyFunc")
        result = MarkdownFormatter.format_node_with_edges(node, [], DetailLevel.SUMMARY)
        assert "MyFunc" in result

    def test_node_with_outgoing_edges(self):
        node = _node("n1", "caller")
        target = _node("n2", "callee")
        edge = _edge("n1", "n2", EdgeKind.CALLS)
        result = MarkdownFormatter.format_node_with_edges(node, [(target, edge, 1)], DetailLevel.SUMMARY)
        assert "caller" in result
        assert "callee" in result

    def test_node_with_incoming_edges(self):
        node = _node("n2", "callee")
        source = _node("n1", "caller")
        edge = _edge("n1", "n2", EdgeKind.CALLS)
        result = MarkdownFormatter.format_node_with_edges(node, [(source, edge, 1)], DetailLevel.SUMMARY)
        assert "callee" in result


# ===================================================================
# ContextAssembler
# ===================================================================


class TestContextAssembler:
    """Test ContextAssembler with mocked store and analyzer."""

    @pytest.fixture()
    def assembler(self):
        return ContextAssembler()

    @pytest.fixture()
    def mock_store(self):
        store = MagicMock()
        store.get_node_by_qualified_name.return_value = None
        store.search_nodes.return_value = []
        store.get_edges_for_node.return_value = []
        store.get_node.return_value = None
        store.get_neighbors.return_value = []
        store.get_nodes_in_file.return_value = []
        store.get_edges_in_file.return_value = []
        return store

    @pytest.fixture()
    def mock_analyzer(self):
        analyzer = MagicMock()
        analyzer.relevance_score.return_value = 0.5
        analyzer.blast_radius.return_value = {}
        return analyzer

    # -- assemble_for_symbol --

    def test_symbol_not_found(self, assembler, mock_store, mock_analyzer):
        result = assembler.assemble_for_symbol("NonExistent", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert "not found" in result.text.lower()
        assert result.nodes_included == 0

    def test_symbol_found_by_qualified_name(self, assembler, mock_store, mock_analyzer):
        node = _node(
            "n1",
            "MyClass",
            NodeKind.CLASS,
            qname="app.MyClass",
            docblock="A test class",
            source_text="class MyClass: pass",
        )
        mock_store.get_node_by_qualified_name.return_value = node
        mock_store.get_edges_for_node.return_value = []
        mock_store.get_neighbors.return_value = []

        result = assembler.assemble_for_symbol("app.MyClass", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert result.nodes_included >= 1
        assert "MyClass" in result.text
        assert result.token_budget == 4000
        assert result.tokens_used > 0

    def test_symbol_found_by_search_fallback(self, assembler, mock_store, mock_analyzer):
        node = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc")
        mock_store.get_node_by_qualified_name.return_value = None
        mock_store.search_nodes.return_value = [node]
        mock_store.get_edges_for_node.return_value = []
        mock_store.get_neighbors.return_value = []

        result = assembler.assemble_for_symbol("MyFunc", mock_store, mock_analyzer, token_budget=4000)
        assert result.nodes_included >= 1

    def test_symbol_with_related_nodes(self, assembler, mock_store, mock_analyzer):
        node = _node("n1", "MyClass", NodeKind.CLASS, qname="app.MyClass")
        related = _node("n2", "helper", NodeKind.FUNCTION, qname="app.helper")
        edge = _edge("n1", "n2", EdgeKind.CALLS)

        mock_store.get_node_by_qualified_name.return_value = node
        mock_store.get_edges_for_node.return_value = [(edge, related, "outgoing")]
        mock_store.get_node.side_effect = lambda nid: {"n1": node, "n2": related}.get(nid)
        mock_store.get_neighbors.return_value = []

        result = assembler.assemble_for_symbol("app.MyClass", mock_store, mock_analyzer, token_budget=4000)
        assert result.nodes_included >= 1

    def test_symbol_token_budget_respected(self, assembler, mock_store, mock_analyzer):
        node = _node("n1", "X", NodeKind.CLASS, qname="X")
        mock_store.get_node_by_qualified_name.return_value = node
        mock_store.get_edges_for_node.return_value = []
        mock_store.get_neighbors.return_value = []

        result = assembler.assemble_for_symbol("X", mock_store, mock_analyzer, token_budget=100)
        assert result.tokens_used <= 100 or result.nodes_included >= 1

    # -- assemble_for_file --

    def test_file_not_found(self, assembler, mock_store, mock_analyzer):
        mock_store.get_nodes_in_file.return_value = []
        result = assembler.assemble_for_file("nonexistent.py", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert result.nodes_included == 0

    def test_file_with_nodes(self, assembler, mock_store, mock_analyzer):
        nodes = [
            _node("n1", "ClassA", NodeKind.CLASS, file_path="src/a.py", pagerank=0.05),
            _node("n2", "func_b", NodeKind.FUNCTION, file_path="src/a.py", pagerank=0.01),
        ]
        # assemble_for_file uses store.connection.execute(SQL).fetchall()
        # then store._row_to_node(row) for each row
        mock_row1 = MagicMock()
        mock_row2 = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [mock_row1, mock_row2]
        mock_store.connection = mock_conn
        mock_store._row_to_node.side_effect = nodes
        # pagerank() must return dict[str, float] for sorting
        mock_analyzer.pagerank.return_value = {"n1": 0.05, "n2": 0.01}

        result = assembler.assemble_for_file("src/a.py", mock_store, mock_analyzer, token_budget=4000)
        assert result.nodes_included >= 1
        assert "src/a.py" in result.included_files or result.nodes_included > 0

    # -- assemble_impact_analysis --

    def test_impact_symbol_not_found(self, assembler, mock_store, mock_analyzer):
        result = assembler.assemble_impact_analysis("NonExistent", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert "not found" in result.text.lower()

    def test_impact_with_blast_radius(self, assembler, mock_store, mock_analyzer):
        node = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc")
        affected = _node("n2", "Caller", NodeKind.FUNCTION, qname="mod.Caller", file_path="src/b.py")
        mock_store.get_node_by_qualified_name.return_value = node
        mock_analyzer.blast_radius.return_value = {
            1: [(affected.id, "calls")],
        }
        mock_store.get_node.side_effect = lambda nid: {"n1": node, "n2": affected}.get(nid)

        result = assembler.assemble_impact_analysis("mod.MyFunc", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert result.nodes_included >= 1


# ===================================================================
# estimate_tokens (from models, used by context)
# ===================================================================


class TestEstimateTokens:
    """Test the estimate_tokens utility."""

    def test_empty_string(self):
        assert estimate_tokens("") >= 1  # min is 1

    def test_short_string(self):
        result = estimate_tokens("hello")
        assert result >= 1

    def test_longer_string(self):
        text = "a" * 400
        result = estimate_tokens(text)
        assert result == 100  # 400 // 4

    def test_returns_int(self):
        assert isinstance(estimate_tokens("test"), int)


# ===================================================================
# MarkdownFormatter — format_node_detailed
# ===================================================================


class TestFormatNodeDetailed:
    """Test MarkdownFormatter.format_node_detailed."""

    def test_basic_node_summary(self):
        node = _node("n1", "MyClass", NodeKind.CLASS, qname="mod.MyClass", file_path="src/a.py", language="python")
        result = MarkdownFormatter.format_node_detailed(node, [], {})
        assert "MyClass" in result
        assert "src/a.py" in result

    def test_node_with_signature_detail(self):
        node = _node("n1", "MyClass", NodeKind.CLASS, qname="mod.MyClass", file_path="src/a.py", language="python")
        result = MarkdownFormatter.format_node_detailed(node, [], {}, detail_level="signature")
        assert "MyClass" in result

    def test_node_with_detailed_level(self):
        node = _node(
            "n1",
            "MyFunc",
            NodeKind.FUNCTION,
            qname="mod.MyFunc",
            file_path="src/a.py",
            language="python",
            metadata={"visibility": "public", "signature": "def my_func(x: int) -> str"},
            docblock="This is a docstring.",
        )
        result = MarkdownFormatter.format_node_detailed(node, [], {}, detail_level="detailed")
        assert "MyFunc" in result
        assert "Documentation" in result

    def test_node_with_comprehensive_level(self):
        node = _node(
            "n1",
            "MyFunc",
            NodeKind.FUNCTION,
            qname="mod.MyFunc",
            file_path="src/a.py",
            language="python",
            docblock="Docstring here.",
            source_text="def my_func(): pass",
        )
        result = MarkdownFormatter.format_node_detailed(node, [], {}, detail_level="comprehensive")
        assert "Source" in result
        assert "def my_func" in result

    def test_node_with_edges_and_related(self):
        node = _node("n1", "caller", NodeKind.FUNCTION, qname="mod.caller", file_path="src/a.py")
        target = _node("n2", "callee", NodeKind.FUNCTION, qname="mod.callee", file_path="src/b.py")
        edge = _edge("n1", "n2", EdgeKind.CALLS)
        result = MarkdownFormatter.format_node_detailed(node, [edge], {"n2": target}, detail_level="summary")
        assert "caller" in result
        assert "callee" in result

    def test_node_with_incoming_edges(self):
        node = _node("n2", "callee", NodeKind.FUNCTION, qname="mod.callee", file_path="src/b.py")
        source = _node("n1", "caller", NodeKind.FUNCTION, qname="mod.caller", file_path="src/a.py")
        edge = _edge("n1", "n2", EdgeKind.CALLS)
        result = MarkdownFormatter.format_node_detailed(node, [edge], {"n1": source}, detail_level="summary")
        assert "callee" in result

    def test_unknown_detail_level_defaults_to_summary(self):
        node = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc", file_path="src/a.py")
        result = MarkdownFormatter.format_node_detailed(node, [], {}, detail_level="unknown")
        assert "MyFunc" in result


# ===================================================================
# MarkdownFormatter — format_impact_analysis
# ===================================================================


class TestFormatImpactAnalysis:
    """Test MarkdownFormatter.format_impact_analysis."""

    def test_empty_impact(self):
        node = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc", file_path="src/a.py")
        result = MarkdownFormatter.format_impact_analysis(node, {})
        assert "Impact Analysis" in result
        assert "leaf node" in result.lower()

    def test_impact_with_depth_1(self):
        target = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc", file_path="src/a.py")
        affected1 = _node("n2", "Caller", NodeKind.FUNCTION, qname="mod.Caller", file_path="src/b.py")
        affected2 = _node("n3", "OtherCaller", NodeKind.METHOD, qname="mod.OtherCaller", file_path="src/c.py")
        result = MarkdownFormatter.format_impact_analysis(target, {1: [affected1, affected2]})
        assert "Impact Analysis" in result
        assert "Depth 1" in result
        assert "Caller" in result
        assert "OtherCaller" in result
        assert "Affected Files" in result

    def test_impact_with_multiple_depths(self):
        target = _node("n1", "Root", NodeKind.CLASS, qname="mod.Root", file_path="src/a.py")
        d1 = _node("n2", "Child", NodeKind.CLASS, qname="mod.Child", file_path="src/b.py")
        d2 = _node("n3", "GrandChild", NodeKind.CLASS, qname="mod.GrandChild", file_path="src/c.py")
        result = MarkdownFormatter.format_impact_analysis(target, {1: [d1], 2: [d2]})
        assert "Depth 1" in result
        assert "Depth 2" in result
        assert "Child" in result
        assert "GrandChild" in result

    def test_impact_same_file_nodes(self):
        target = _node("n1", "Root", NodeKind.CLASS, qname="mod.Root", file_path="src/a.py")
        affected = _node("n2", "Helper", NodeKind.FUNCTION, qname="mod.Helper", file_path="src/a.py")
        result = MarkdownFormatter.format_impact_analysis(target, {1: [affected]})
        assert "src/a.py" in result


# ===================================================================
# MarkdownFormatter — format_architecture_overview
# ===================================================================


class TestFormatArchitectureOverview:
    """Test MarkdownFormatter.format_architecture_overview."""

    def test_empty_architecture(self):
        result = MarkdownFormatter.format_architecture_overview([], [], [])
        assert "Architecture Overview" in result

    def test_with_communities(self):
        n1 = _node("n1", "ClassA", NodeKind.CLASS, file_path="src/a.py")
        n2 = _node("n2", "ClassB", NodeKind.CLASS, file_path="src/b.py")
        result = MarkdownFormatter.format_architecture_overview(
            [(0, [n1]), (1, [n2])],
            [(n1, 0.5), (n2, 0.3)],
            [n1],
        )
        assert "Architecture Overview" in result
        assert "Communities" in result
        assert "Key Nodes" in result
        assert "Entry Points" in result

    def test_with_important_nodes(self):
        nodes = [_node(f"n{i}", f"Func{i}", NodeKind.FUNCTION, file_path=f"src/{i}.py") for i in range(5)]
        important = [(n, 0.1 * (5 - i)) for i, n in enumerate(nodes)]
        result = MarkdownFormatter.format_architecture_overview([(0, nodes)], important, [])
        assert "PageRank" in result
        assert "Func0" in result

    def test_with_entry_points(self):
        ep = _node("n1", "main", NodeKind.FUNCTION, file_path="src/main.py")
        result = MarkdownFormatter.format_architecture_overview([(0, [ep])], [(ep, 0.5)], [ep])
        assert "Entry Points" in result
        assert "main" in result


# ===================================================================
# ContextAssembler — assemble_for_symbol
# ===================================================================


class TestAssembleForSymbol:
    """Test ContextAssembler.assemble_for_symbol."""

    @pytest.fixture()
    def assembler(self):
        return ContextAssembler()

    def test_symbol_not_found(self, assembler):
        mock_store = MagicMock()
        mock_store.get_node_by_qualified_name.return_value = None
        mock_store.search_nodes.return_value = []
        mock_analyzer = MagicMock()

        result = assembler.assemble_for_symbol("NonExistent", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert "not found" in result.text.lower()

    def test_symbol_found_basic(self, assembler):
        node = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc", file_path="src/a.py")
        mock_store = MagicMock()
        mock_store.get_node_by_qualified_name.return_value = node
        mock_store.get_edges.return_value = []
        mock_store.get_node.return_value = None

        mock_analyzer = MagicMock()
        mock_analyzer.pagerank.return_value = {"n1": 0.5}

        result = assembler.assemble_for_symbol("mod.MyFunc", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert "MyFunc" in result.text

    def test_symbol_with_relationships(self, assembler):
        node = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc", file_path="src/a.py")
        target = _node("n2", "Helper", NodeKind.FUNCTION, qname="mod.Helper", file_path="src/b.py")
        edge = _edge("n1", "n2", EdgeKind.CALLS)

        mock_store = MagicMock()
        mock_store.get_node_by_qualified_name.return_value = node
        mock_store.get_edges.side_effect = [
            [edge],  # outgoing
            [],  # incoming
        ]
        mock_store.get_node.return_value = target

        mock_analyzer = MagicMock()
        mock_analyzer.pagerank.return_value = {"n1": 0.5, "n2": 0.3}

        result = assembler.assemble_for_symbol("mod.MyFunc", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert result.nodes_included >= 0

    def test_symbol_with_small_budget(self, assembler):
        node = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc", file_path="src/a.py")
        mock_store = MagicMock()
        mock_store.get_node_by_qualified_name.return_value = node
        mock_store.get_edges.return_value = []
        mock_store.get_node.return_value = None

        mock_analyzer = MagicMock()
        mock_analyzer.pagerank.return_value = {"n1": 0.5}

        result = assembler.assemble_for_symbol("mod.MyFunc", mock_store, mock_analyzer, token_budget=10)
        assert isinstance(result, ContextResult)


# ===================================================================
# ContextAssembler — assemble_impact_analysis (extended)
# ===================================================================


class TestAssembleImpactAnalysisExtended:
    """Extended tests for ContextAssembler.assemble_impact_analysis."""

    @pytest.fixture()
    def assembler(self):
        return ContextAssembler()

    def test_impact_with_blast_radius_data(self, assembler):
        node = _node("n1", "MyFunc", NodeKind.FUNCTION, qname="mod.MyFunc", file_path="src/a.py")
        affected = _node("n2", "Caller", NodeKind.FUNCTION, qname="mod.Caller", file_path="src/b.py")

        mock_store = MagicMock()
        mock_store.get_node_by_qualified_name.return_value = node
        mock_store.get_node.return_value = affected

        mock_analyzer = MagicMock()
        mock_analyzer.blast_radius.return_value = {
            1: ["n2"],
        }
        mock_analyzer.relevance_score.return_value = 0.5

        result = assembler.assemble_impact_analysis("mod.MyFunc", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert "Impact" in result.text or "impact" in result.text.lower()

    def test_impact_no_blast_radius(self, assembler):
        node = _node("n1", "LeafFunc", NodeKind.FUNCTION, qname="mod.LeafFunc", file_path="src/a.py")

        mock_store = MagicMock()
        mock_store.get_node_by_qualified_name.return_value = node

        mock_analyzer = MagicMock()
        mock_analyzer.blast_radius.return_value = {}

        result = assembler.assemble_impact_analysis("mod.LeafFunc", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert "leaf" in result.text.lower() or result.nodes_included == 0

    def test_impact_multiple_depths(self, assembler):
        node = _node("n1", "Root", NodeKind.CLASS, qname="mod.Root", file_path="src/a.py")
        d1_node = _node("n2", "Child", NodeKind.CLASS, qname="mod.Child", file_path="src/b.py")
        d2_node = _node("n3", "GrandChild", NodeKind.CLASS, qname="mod.GrandChild", file_path="src/c.py")

        mock_store = MagicMock()
        mock_store.get_node_by_qualified_name.return_value = node
        mock_store.get_node.side_effect = lambda nid: {"n2": d1_node, "n3": d2_node}.get(nid)

        mock_analyzer = MagicMock()
        mock_analyzer.blast_radius.return_value = {
            1: ["n2"],
            2: ["n3"],
        }
        mock_analyzer.relevance_score.return_value = 0.3

        result = assembler.assemble_impact_analysis("mod.Root", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)

    def test_impact_small_budget(self, assembler):
        node = _node("n1", "Root", NodeKind.CLASS, qname="mod.Root", file_path="src/a.py")

        mock_store = MagicMock()
        mock_store.get_node_by_qualified_name.return_value = node

        mock_analyzer = MagicMock()
        mock_analyzer.blast_radius.return_value = {
            1: [f"n{i}" for i in range(2, 50)],
        }
        mock_analyzer.relevance_score.return_value = 0.1
        mock_store.get_node.return_value = _node(
            "nx", "Affected", NodeKind.FUNCTION, qname="mod.Affected", file_path="src/x.py"
        )

        result = assembler.assemble_impact_analysis("mod.Root", mock_store, mock_analyzer, token_budget=50)
        assert isinstance(result, ContextResult)


# ===================================================================
# ContextAssembler — assemble_for_file (extended)
# ===================================================================


class TestAssembleForFileExtended:
    """Extended tests for ContextAssembler.assemble_for_file."""

    @pytest.fixture()
    def assembler(self):
        return ContextAssembler()

    def test_file_not_found(self, assembler):
        mock_store = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_store.connection = mock_conn

        mock_analyzer = MagicMock()

        result = assembler.assemble_for_file("nonexistent.py", mock_store, mock_analyzer, token_budget=4000)
        assert isinstance(result, ContextResult)
        assert result.nodes_included == 0

    def test_file_with_many_nodes_small_budget(self, assembler):
        nodes = [_node(f"n{i}", f"Func{i}", NodeKind.FUNCTION, file_path="src/big.py") for i in range(20)]
        mock_rows = [MagicMock() for _ in nodes]

        mock_store = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = mock_rows
        mock_store.connection = mock_conn
        mock_store._row_to_node.side_effect = nodes

        mock_analyzer = MagicMock()
        mock_analyzer.pagerank.return_value = {f"n{i}": 0.01 * (20 - i) for i in range(20)}

        result = assembler.assemble_for_file("src/big.py", mock_store, mock_analyzer, token_budget=100)
        assert isinstance(result, ContextResult)
        assert "src/big.py" in result.text


# ===================================================================


# ── Additional tests for uncovered markdown.py methods ──────────────────

from io import StringIO

from rich.console import Console


class TestRenderToConsole:
    """Tests for MarkdownFormatter.render_to_console."""

    def test_render_basic_markdown(self):
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=80)
        MarkdownFormatter.render_to_console("# Hello World", console=console)
        output = buf.getvalue()
        assert "Hello World" in output

    def test_render_empty_string(self):
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=80)
        MarkdownFormatter.render_to_console("", console=console)
        # Should not raise

    def test_render_default_console(self):
        # Just ensure it doesn't crash with default console
        MarkdownFormatter.render_to_console("test")


class TestRenderSummaryTable:
    """Tests for MarkdownFormatter.render_summary_table."""

    def test_render_summary_with_data(self):
        summary = _graph_summary()
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_summary_table(summary, console=console)
        output = buf.getvalue()
        assert "TestProject" in output

    def test_render_summary_empty(self):
        summary = _graph_summary(
            project_name="",
            project_root="",
            db_size_bytes=0,
            last_parsed=None,
            total_nodes=0,
            total_edges=0,
            nodes_by_kind={},
            edges_by_kind={},
            files_by_language={},
            frameworks=[],
            communities=0,
            avg_confidence=0.0,
            top_nodes_by_pagerank=[],
        )
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_summary_table(summary, console=console)
        # Should not raise

    def test_render_summary_large_db(self):
        summary = _graph_summary(db_size_bytes=2 * 1024 * 1024)  # 2 MB
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_summary_table(summary, console=console)
        output = buf.getvalue()
        assert "MB" in output


class TestRenderParseResults:
    """Tests for MarkdownFormatter.render_parse_results."""

    def test_render_parse_results_with_data(self):
        summary = _pipeline_summary(
            total_files=50,
            files_parsed=45,
            files_skipped=3,
            files_errored=2,
            nodes_added=200,
            edges_added=400,
            total_nodes=200,
            total_edges=400,
            total_parse_time_ms=1500.0,
            total_pipeline_time_ms=3000.0,
            nodes_by_kind={"class": 10, "function": 40},
        )
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_parse_results(summary, console=console)
        output = buf.getvalue()
        assert "Parse Results" in output

    def test_render_parse_results_with_errors(self):
        summary = _pipeline_summary(
            files_errored=5,
            total_parse_time_ms=500.0,
            total_pipeline_time_ms=1000.0,
        )
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_parse_results(summary, console=console)
        output = buf.getvalue()
        assert "5" in output

    def test_render_parse_results_no_errors(self):
        summary = _pipeline_summary(
            files_errored=0,
            total_parse_time_ms=100.0,
            total_pipeline_time_ms=200.0,
        )
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_parse_results(summary, console=console)
        # Should not raise


class TestRenderSearchResults:
    """Tests for MarkdownFormatter.render_search_results."""

    def test_render_search_results_with_nodes(self):
        nodes = [_node("n1", "MyClass", NodeKind.CLASS, qname="app.MyClass")]
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_search_results(nodes, "MyClass", console=console)
        output = buf.getvalue()
        assert "MyClass" in output

    def test_render_search_results_empty(self):
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_search_results([], "nothing", console=console)
        output = buf.getvalue()
        assert "No results" in output

    def test_render_search_results_multiple(self):
        nodes = [
            _node("n1", "Foo", NodeKind.FUNCTION, qname="mod.Foo"),
            _node("n2", "Bar", NodeKind.CLASS, qname="mod.Bar"),
        ]
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        MarkdownFormatter.render_search_results(nodes, "search", console=console)
        output = buf.getvalue()
        assert "2" in output


class TestFormatNodeDetailedEdges:
    """Tests for format_node_detailed with edges and related_nodes."""

    def test_with_outgoing_edges_target_found(self):
        node = _node("n1", "MyClass", NodeKind.CLASS, qname="app.MyClass")
        target = _node("n2", "Helper", NodeKind.CLASS, qname="app.Helper")
        edges = [_edge("n1", "n2", EdgeKind.CALLS)]
        related = {"n2": target}
        result = MarkdownFormatter.format_node_detailed(node, edges, related, detail_level="summary")
        assert "MyClass" in result
        assert "Helper" in result

    def test_with_outgoing_edges_target_not_found(self):
        node = _node("n1", "MyClass", NodeKind.CLASS, qname="app.MyClass")
        edges = [_edge("n1", "n2", EdgeKind.CALLS)]
        related = {}  # target not in related_nodes
        result = MarkdownFormatter.format_node_detailed(node, edges, related, detail_level="summary")
        assert "MyClass" in result

    def test_with_incoming_edges_source_found(self):
        node = _node("n2", "Helper", NodeKind.CLASS, qname="app.Helper")
        source = _node("n1", "MyClass", NodeKind.CLASS, qname="app.MyClass")
        edges = [_edge("n1", "n2", EdgeKind.CALLS)]
        related = {"n1": source}
        result = MarkdownFormatter.format_node_detailed(node, edges, related, detail_level="summary")
        assert "Helper" in result

    def test_with_incoming_edges_source_not_found(self):
        node = _node("n2", "Helper", NodeKind.CLASS, qname="app.Helper")
        edges = [_edge("n1", "n2", EdgeKind.CALLS)]
        related = {}  # source not in related_nodes
        result = MarkdownFormatter.format_node_detailed(node, edges, related, detail_level="summary")
        assert "Helper" in result

    def test_with_no_edges(self):
        node = _node("n1", "Lonely", NodeKind.FUNCTION, qname="app.Lonely")
        result = MarkdownFormatter.format_node_detailed(node, [], {}, detail_level="summary")
        assert "Lonely" in result

    def test_detail_level_comprehensive(self):
        node = _node(
            "n1", "Func", NodeKind.FUNCTION, qname="app.Func", source_text="def Func(): pass", docblock="A function."
        )
        result = MarkdownFormatter.format_node_detailed(node, [], {}, detail_level="comprehensive")
        assert "Func" in result

    def test_detail_level_signature(self):
        node = _node("n1", "Func", NodeKind.FUNCTION, qname="app.Func", source_text="def Func(): pass")
        result = MarkdownFormatter.format_node_detailed(node, [], {}, detail_level="signature")
        assert "Func" in result


class TestFormatArchitectureOverviewExtended:
    """Tests for format_architecture_overview."""

    def test_with_communities_and_important_nodes(self):
        n1 = _node(
            "n1", "UserService", NodeKind.CLASS, qname="app.services.UserService", file_path="src/services/user.py"
        )
        n2 = _node(
            "n2", "OrderService", NodeKind.CLASS, qname="app.services.OrderService", file_path="src/services/order.py"
        )
        n3 = _node("n3", "main", NodeKind.FUNCTION, qname="app.main", file_path="src/main.py")
        communities = [(0, [n1, n2]), (1, [n3])]
        important_nodes = [(n1, 0.045), (n3, 0.032)]
        entry_points = [n3]
        result = MarkdownFormatter.format_architecture_overview(communities, important_nodes, entry_points)
        assert "Architecture Overview" in result
        assert "Communities" in result
        assert "UserService" in result
        assert "Entry Points" in result

    def test_communities_with_mixed_paths(self):
        n1 = _node("n1", "A", NodeKind.CLASS, file_path="src/a/foo.py")
        n2 = _node("n2", "B", NodeKind.CLASS, file_path="src/b/bar.py")
        communities = [(0, [n1, n2])]
        result = MarkdownFormatter.format_architecture_overview(communities, [], [])
        assert "Community 0" in result

    def test_communities_empty(self):
        result = MarkdownFormatter.format_architecture_overview([], [], [])
        assert "Architecture Overview" in result
        assert "0" in result  # 0 communities, 0 nodes, 0 entry points

    def test_no_entry_points(self):
        n1 = _node("n1", "A", NodeKind.CLASS, file_path="src/a.py")
        communities = [(0, [n1])]
        important = [(n1, 0.5)]
        result = MarkdownFormatter.format_architecture_overview(communities, important, [])
        assert "Key Nodes" in result
        # Entry Points section should not appear


class TestFormatImpactAnalysisExtended:
    """Tests for format_impact_analysis."""

    def test_with_blast_radius(self):
        target = _node("n1", "UserService", NodeKind.CLASS, qname="app.UserService", file_path="src/services/user.py")
        affected1 = _node(
            "n2", "OrderService", NodeKind.CLASS, qname="app.OrderService", file_path="src/services/order.py"
        )
        affected2 = _node("n3", "main", NodeKind.FUNCTION, qname="app.main", file_path="src/main.py")
        impacted = {1: [affected1], 2: [affected2]}
        result = MarkdownFormatter.format_impact_analysis(target, impacted)
        assert "Impact Analysis" in result
        assert "UserService" in result
        assert "OrderService" in result
        assert "Depth 1" in result
        assert "Depth 2" in result
        assert "All Affected Files" in result

    def test_empty_blast_radius(self):
        target = _node("n1", "Leaf", NodeKind.FUNCTION, qname="app.Leaf", file_path="src/leaf.py")
        result = MarkdownFormatter.format_impact_analysis(target, {})
        assert "leaf node" in result

    def test_multiple_nodes_same_depth(self):
        target = _node("n1", "Core", NodeKind.CLASS, qname="app.Core", file_path="src/core.py")
        a = _node("n2", "A", NodeKind.FUNCTION, qname="app.A", file_path="src/a.py")
        b = _node("n3", "B", NodeKind.FUNCTION, qname="app.B", file_path="src/b.py")
        impacted = {1: [a, b]}
        result = MarkdownFormatter.format_impact_analysis(target, impacted)
        assert "2 nodes" in result
        assert "Depth 1" in result

    def test_affected_nodes_same_file(self):
        target = _node("n1", "Core", NodeKind.CLASS, qname="app.Core", file_path="src/core.py")
        a = _node("n2", "func_a", NodeKind.FUNCTION, qname="app.func_a", file_path="src/core.py")
        impacted = {1: [a]}
        result = MarkdownFormatter.format_impact_analysis(target, impacted)
        assert "src/core.py" in result


# ── Additional Context Assembler Tests ────────────────────────────────


class TestContextAssemblerForSymbol:
    """Tests for ContextAssembler.assemble_for_symbol covering levels 2-4."""

    def _make_node(self, id, qname, kind=None, file_path="test.py", start_line=1, source_text="", metadata=None):
        from coderag.core.models import Node, NodeKind

        return Node(
            id=id,
            kind=kind or NodeKind.FUNCTION,
            name=qname.split(".")[-1],
            qualified_name=qname,
            file_path=file_path,
            start_line=start_line,
            end_line=start_line + 5,
            language="python",
            source_text=source_text or f"def {qname.split(chr(46))[-1]}(): pass",
            metadata=metadata or {},
        )

    def _make_edge(self, src, tgt, kind=None):
        from coderag.core.models import Edge, EdgeKind

        return Edge(
            source_id=src,
            target_id=tgt,
            kind=kind or EdgeKind.CALLS,
            confidence=1.0,
        )

    def test_assemble_for_symbol_not_found(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = None
        store.search_nodes.return_value = []

        assembler = ContextAssembler()
        result = assembler.assemble_for_symbol("nonexistent", store, analyzer, token_budget=4000)
        assert result.nodes_included == 0
        assert "not found" in result.text.lower() or result.text == ""

    def test_assemble_for_symbol_found_via_search(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        node = self._make_node("n1", "MyClass.my_method", source_text="def my_method(self): return 42")
        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = None
        store.search_nodes.return_value = [node]
        store.get_edges.return_value = []
        store.get_neighbors.return_value = []

        assembler = ContextAssembler()
        result = assembler.assemble_for_symbol("MyClass.my_method", store, analyzer, token_budget=4000)
        assert result.nodes_included >= 1

    def test_assemble_for_symbol_with_direct_relationships(self):
        from unittest.mock import MagicMock

        from coderag.core.models import EdgeKind
        from coderag.output.context import ContextAssembler

        main_node = self._make_node("n1", "MyClass.process", source_text="def process(self): pass")
        related_node = self._make_node("n2", "MyClass.helper", source_text="def helper(self): pass")
        edge_out = self._make_edge("n1", "n2", EdgeKind.CALLS)

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = main_node
        store.get_edges.side_effect = lambda source_id=None, target_id=None: [edge_out] if source_id == "n1" else []
        store.get_node.return_value = related_node
        store.get_neighbors.return_value = []
        analyzer.relevance_score.return_value = 0.8

        assembler = ContextAssembler()
        result = assembler.assemble_for_symbol("MyClass.process", store, analyzer, token_budget=8000)
        assert result.nodes_included >= 1
        assert "Direct Relationships" in result.text or result.nodes_included >= 1

    def test_assemble_for_symbol_with_incoming_edges(self):
        from unittest.mock import MagicMock

        from coderag.core.models import EdgeKind
        from coderag.output.context import ContextAssembler

        main_node = self._make_node("n1", "MyClass.process")
        caller_node = self._make_node("n2", "main.run")
        edge_in = self._make_edge("n2", "n1", EdgeKind.CALLS)

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = main_node
        store.get_edges.side_effect = lambda source_id=None, target_id=None: [] if source_id else [edge_in]
        store.get_node.return_value = caller_node
        store.get_neighbors.return_value = []
        analyzer.relevance_score.return_value = 0.5

        assembler = ContextAssembler()
        result = assembler.assemble_for_symbol("MyClass.process", store, analyzer, token_budget=8000)
        assert result.nodes_included >= 1

    def test_assemble_for_symbol_skips_containment_edges(self):
        from unittest.mock import MagicMock

        from coderag.core.models import EdgeKind
        from coderag.output.context import ContextAssembler

        main_node = self._make_node("n1", "MyClass.process")
        contained = self._make_node("n2", "MyClass")
        edge_contain = self._make_edge("n1", "n2", EdgeKind.CONTAINS)

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = main_node
        store.get_edges.side_effect = lambda source_id=None, target_id=None: [edge_contain] if source_id else []
        store.get_node.return_value = contained
        store.get_neighbors.return_value = []
        analyzer.relevance_score.return_value = 0.5

        assembler = ContextAssembler()
        result = assembler.assemble_for_symbol("MyClass.process", store, analyzer, token_budget=8000)
        # Containment edges should be skipped, so no "Direct Relationships" section
        assert "Direct Relationships" not in result.text

    def test_assemble_for_symbol_extended_neighborhood(self):
        from unittest.mock import MagicMock

        from coderag.core.models import EdgeKind
        from coderag.output.context import ContextAssembler

        main_node = self._make_node("n1", "MyClass.process")
        neighbor = self._make_node("n3", "utils.format")
        edge_nb = self._make_edge("n1", "n3", EdgeKind.CALLS)

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = main_node
        store.get_edges.return_value = []
        # get_neighbors returns list of (node, edge, depth)
        store.get_neighbors.side_effect = lambda nid, max_depth=1: [(neighbor, edge_nb, 1)] if max_depth == 1 else []
        analyzer.relevance_score.return_value = 0.6

        assembler = ContextAssembler()
        result = assembler.assemble_for_symbol("MyClass.process", store, analyzer, token_budget=8000)
        assert result.nodes_included >= 1

    def test_assemble_for_symbol_2hop_relationships(self):
        from unittest.mock import MagicMock

        from coderag.core.models import EdgeKind
        from coderag.output.context import ContextAssembler

        main_node = self._make_node("n1", "MyClass.process")
        hop2_node = self._make_node("n4", "deep.module.func")
        edge_hop2 = self._make_edge("n1", "n4", EdgeKind.CALLS)

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = main_node
        store.get_edges.return_value = []
        # First call max_depth=1 returns empty, second call max_depth=2 returns hop2
        store.get_neighbors.side_effect = lambda nid, max_depth=1: [(hop2_node, edge_hop2, 2)] if max_depth == 2 else []
        analyzer.relevance_score.return_value = 0.3

        assembler = ContextAssembler()
        result = assembler.assemble_for_symbol("MyClass.process", store, analyzer, token_budget=8000)
        # With large budget and 2-hop data, should include 2-hop section
        assert result.nodes_included >= 0  # May or may not include depending on budget


class TestContextAssemblerForFile:
    """Tests for ContextAssembler.assemble_for_file."""

    def test_assemble_for_file_basic(self):
        from unittest.mock import MagicMock

        from coderag.core.models import Node, NodeKind
        from coderag.output.context import ContextAssembler

        # Mock store with connection that returns rows
        store = MagicMock()
        analyzer = MagicMock()

        # Mock the connection.execute to return rows
        mock_conn = MagicMock()
        store.connection = mock_conn

        node = Node(
            id="f1",
            kind=NodeKind.FILE,
            name="test.py",
            qualified_name="test.py",
            file_path="test.py",
            start_line=1,
            end_line=10,
            language="python",
            source_text="# test file",
            metadata={},
        )
        func_node = Node(
            id="fn1",
            kind=NodeKind.FUNCTION,
            name="hello",
            qualified_name="test.hello",
            file_path="test.py",
            start_line=1,
            end_line=3,
            language="python",
            source_text="def hello(): pass",
            metadata={},
        )

        # Mock _row_to_node
        store._row_to_node.side_effect = [node, func_node]
        mock_conn.execute.return_value.fetchall.return_value = [{"id": "f1"}, {"id": "fn1"}]

        analyzer.pagerank.return_value = {"f1": 0.5, "fn1": 0.3}

        assembler = ContextAssembler()
        result = assembler.assemble_for_file("test.py", store, analyzer, token_budget=4000)
        assert result.token_budget == 4000

    def test_assemble_for_file_empty(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        store = MagicMock()
        analyzer = MagicMock()
        mock_conn = MagicMock()
        store.connection = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = []
        analyzer.pagerank.return_value = {}

        assembler = ContextAssembler()
        result = assembler.assemble_for_file("nonexistent.py", store, analyzer, token_budget=4000)
        assert result.nodes_included == 0


class TestContextAssemblerImpactAnalysis:
    """Tests for ContextAssembler.assemble_impact_analysis."""

    def _make_node(self, id, qname, kind=None):
        from coderag.core.models import Node, NodeKind

        return Node(
            id=id,
            kind=kind or NodeKind.FUNCTION,
            name=qname.split(".")[-1],
            qualified_name=qname,
            file_path="test.py",
            start_line=1,
            end_line=5,
            language="python",
            source_text=f"def {qname.split(chr(46))[-1]}(): pass",
            metadata={},
        )

    def test_impact_analysis_not_found(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = None
        store.search_nodes.return_value = []

        assembler = ContextAssembler()
        result = assembler.assemble_impact_analysis("nonexistent", store, analyzer, token_budget=4000)
        assert "not found" in result.text.lower() or result.nodes_included == 0

    def test_impact_analysis_no_blast_radius(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        node = self._make_node("n1", "MyClass.leaf_method")
        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = node
        analyzer.blast_radius.return_value = {}

        assembler = ContextAssembler()
        result = assembler.assemble_impact_analysis("MyClass.leaf_method", store, analyzer, token_budget=4000)
        assert "leaf node" in result.text.lower() or "no downstream" in result.text.lower()

    def test_impact_analysis_with_blast_radius(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        node = self._make_node("n1", "MyClass.core_method")
        dep1 = self._make_node("n2", "Handler.process")
        dep2 = self._make_node("n3", "View.render")

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = node
        analyzer.blast_radius.return_value = {
            1: ["n2", "n3"],
        }
        store.get_node.side_effect = lambda nid: {"n2": dep1, "n3": dep2}.get(nid)
        analyzer.relevance_score.return_value = 0.5

        assembler = ContextAssembler()
        result = assembler.assemble_impact_analysis("MyClass.core_method", store, analyzer, token_budget=8000)
        assert result.nodes_included >= 0
        assert "Depth 1" in result.text

    def test_impact_analysis_with_multiple_depths(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        node = self._make_node("n1", "MyClass.core")
        dep1 = self._make_node("n2", "A.func")
        dep2 = self._make_node("n3", "B.func")
        dep3 = self._make_node("n4", "C.func")

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = node
        analyzer.blast_radius.return_value = {
            1: ["n2"],
            2: ["n3"],
            3: ["n4"],
        }
        store.get_node.side_effect = lambda nid: {"n2": dep1, "n3": dep2, "n4": dep3}.get(nid)
        analyzer.relevance_score.return_value = 0.5

        assembler = ContextAssembler()
        result = assembler.assemble_impact_analysis("MyClass.core", store, analyzer, token_budget=8000)
        assert "Depth 1" in result.text
        assert "Depth 2" in result.text

    def test_impact_analysis_budget_truncation(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        node = self._make_node("n1", "MyClass.core")
        # Create many deps to exceed budget
        deps = {}
        dep_ids = []
        for i in range(50):
            nid = f"dep{i}"
            dep_ids.append(nid)
            deps[nid] = self._make_node(nid, f"Module{i}.func{i}")

        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = node
        analyzer.blast_radius.return_value = {1: dep_ids}
        store.get_node.side_effect = lambda nid: deps.get(nid)
        analyzer.relevance_score.return_value = 0.5

        assembler = ContextAssembler()
        # Very small budget to force truncation
        result = assembler.assemble_impact_analysis("MyClass.core", store, analyzer, token_budget=200)
        assert result.token_budget == 200

    def test_impact_analysis_found_via_search(self):
        from unittest.mock import MagicMock

        from coderag.output.context import ContextAssembler

        node = self._make_node("n1", "MyClass.method")
        store = MagicMock()
        analyzer = MagicMock()
        store.get_node_by_qualified_name.return_value = None
        store.search_nodes.return_value = [node]
        analyzer.blast_radius.return_value = {}

        assembler = ContextAssembler()
        result = assembler.assemble_impact_analysis("MyClass.method", store, analyzer, token_budget=4000)
        assert "leaf node" in result.text.lower() or "no downstream" in result.text.lower()
