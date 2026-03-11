"""
CodeRAG Markdown Output Formatter
=================================

Formats graph nodes, edges, and summaries as rich Markdown
for terminal display and file export.
"""
from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from coderag.core.models import (
    DetailLevel,
    Edge,
    EdgeKind,
    GraphSummary,
    Node,
    NodeKind,
    PipelineSummary,
)


class MarkdownFormatter:
    """Format graph data as Markdown with optional Rich terminal rendering."""

    # ── Node Formatting ───────────────────────────────────────

    @staticmethod
    def format_node(node: Node, detail: DetailLevel = DetailLevel.SUMMARY) -> str:
        """Format a single node as markdown.

        Args:
            node: The node to format.
            detail: Level of detail to include.
                SIGNATURE  -> name and kind only
                SUMMARY    -> name, kind, file, line range, metadata basics
                DETAILED   -> everything including docstring, metadata
                COMPREHENSIVE -> everything plus source text

        Returns:
            Markdown-formatted string.
        """
        lines: list[str] = []

        if detail == DetailLevel.SIGNATURE:
            # Minimal: just name and kind
            sig = node.metadata.get("signature", node.name) if node.metadata else node.name
            lines.append(f"**{node.kind.value}** `{sig}`")
            return "\n".join(lines)

        # SUMMARY and above
        lines.append(f"### {node.kind.value.title()}: `{node.qualified_name}`")
        lines.append("")
        lines.append(f"| Property | Value |")
        lines.append(f"|----------|-------|")
        lines.append(f"| **Name** | `{node.name}` |")
        lines.append(f"| **Kind** | {node.kind.value} |")
        lines.append(f"| **File** | `{node.file_path}` |")
        lines.append(f"| **Lines** | {node.start_line}–{node.end_line} |")
        lines.append(f"| **Language** | {node.language} |")

        # Extract visibility/signature from metadata
        if node.metadata:
            if "visibility" in node.metadata:
                lines.append(f"| **Visibility** | {node.metadata['visibility']} |")
            if "signature" in node.metadata:
                lines.append(f"| **Signature** | `{node.metadata['signature']}` |")
            if "is_abstract" in node.metadata and node.metadata["is_abstract"]:
                lines.append(f"| **Abstract** | Yes |")
            if "is_static" in node.metadata and node.metadata["is_static"]:
                lines.append(f"| **Static** | Yes |")

        if node.pagerank > 0:
            lines.append(f"| **PageRank** | {node.pagerank:.6f} |")
        if node.community_id is not None:
            lines.append(f"| **Community** | {node.community_id} |")

        if detail in (DetailLevel.DETAILED, DetailLevel.COMPREHENSIVE):
            # Include docstring
            if node.docblock:
                lines.append("")
                lines.append("**Documentation:**")
                lines.append(f"```")
                lines.append(node.docblock)
                lines.append(f"```")

            # Include all metadata
            if node.metadata:
                extra = {k: v for k, v in node.metadata.items()
                         if k not in ("visibility", "signature", "is_abstract", "is_static")}
                if extra:
                    lines.append("")
                    lines.append("**Metadata:**")
                    lines.append(f"```json")
                    lines.append(json.dumps(extra, indent=2, default=str))
                    lines.append(f"```")

        if detail == DetailLevel.COMPREHENSIVE:
            # Include source text
            if node.source_text:
                lines.append("")
                lines.append("**Source:**")
                lang = node.language if node.language else ""
                lines.append(f"```{lang}")
                lines.append(node.source_text)
                lines.append(f"```")

        return "\n".join(lines)

    # ── Node with Edges ───────────────────────────────────────

    @staticmethod
    def format_node_with_edges(
        node: Node,
        neighbors: list[tuple[Node, Edge, int]],
        detail: DetailLevel = DetailLevel.SUMMARY,
    ) -> str:
        """Format a node with its relationships.

        Args:
            node: The central node.
            neighbors: List of (neighbor_node, edge, depth) tuples.
            detail: Level of detail.

        Returns:
            Markdown-formatted string.
        """
        lines: list[str] = []

        # Format the main node
        lines.append(MarkdownFormatter.format_node(node, detail))
        lines.append("")

        if not neighbors:
            lines.append("*No relationships found.*")
            return "\n".join(lines)

        # Group by direction
        outgoing: list[tuple[Node, Edge, int]] = []
        incoming: list[tuple[Node, Edge, int]] = []

        for neighbor, edge, depth in neighbors:
            if edge.source_id == node.id:
                outgoing.append((neighbor, edge, depth))
            else:
                incoming.append((neighbor, edge, depth))

        if outgoing:
            lines.append("#### Outgoing Relationships")
            lines.append("")
            lines.append("| Relationship | Target | Kind | Confidence | Depth |")
            lines.append("|-------------|--------|------|------------|-------|")
            for neighbor, edge, depth in outgoing:
                lines.append(
                    f"| {edge.kind.value if isinstance(edge.kind, EdgeKind) else edge.kind} "
                    f"| `{neighbor.qualified_name}` "
                    f"| {neighbor.kind.value if isinstance(neighbor.kind, NodeKind) else neighbor.kind} "
                    f"| {edge.confidence:.2f} "
                    f"| {depth} |"
                )
            lines.append("")

        if incoming:
            lines.append("#### Incoming Relationships")
            lines.append("")
            lines.append("| Relationship | Source | Kind | Confidence | Depth |")
            lines.append("|-------------|--------|------|------------|-------|")
            for neighbor, edge, depth in incoming:
                lines.append(
                    f"| {edge.kind.value if isinstance(edge.kind, EdgeKind) else edge.kind} "
                    f"| `{neighbor.qualified_name}` "
                    f"| {neighbor.kind.value if isinstance(neighbor.kind, NodeKind) else neighbor.kind} "
                    f"| {edge.confidence:.2f} "
                    f"| {depth} |"
                )
            lines.append("")

        return "\n".join(lines)

    # ── Graph Summary ─────────────────────────────────────────

    @staticmethod
    def format_graph_summary(summary: GraphSummary) -> str:
        """Format graph statistics as markdown."""
        lines: list[str] = []

        lines.append("## CodeRAG — Graph Summary")
        lines.append("")
        lines.append(f"| Property | Value |")
        lines.append(f"|----------|-------|")
        if summary.project_name:
            lines.append(f"| **Project** | {summary.project_name} |")
        if summary.project_root:
            lines.append(f"| **Root** | `{summary.project_root}` |")
        lines.append(f"| **Database** | `{summary.db_path}` |")
        if summary.db_size_bytes > 0:
            size_kb = summary.db_size_bytes / 1024
            if size_kb > 1024:
                lines.append(f"| **DB Size** | {size_kb / 1024:.1f} MB |")
            else:
                lines.append(f"| **DB Size** | {size_kb:.1f} KB |")
        if summary.last_parsed:
            lines.append(f"| **Last Parsed** | {summary.last_parsed} |")
        lines.append(f"| **Total Nodes** | {summary.total_nodes:,} |")
        lines.append(f"| **Total Edges** | {summary.total_edges:,} |")
        lines.append(f"| **Communities** | {summary.communities} |")
        lines.append(f"| **Avg Confidence** | {summary.avg_confidence:.2f} |")
        lines.append("")

        # Nodes by kind
        if summary.nodes_by_kind:
            lines.append("### Nodes by Kind")
            lines.append("")
            lines.append("| Kind | Count |")
            lines.append("|------|-------|")
            for kind, count in sorted(summary.nodes_by_kind.items(), key=lambda x: -x[1]):
                lines.append(f"| {kind} | {count:,} |")
            lines.append("")

        # Edges by kind
        if summary.edges_by_kind:
            lines.append("### Edges by Kind")
            lines.append("")
            lines.append("| Kind | Count |")
            lines.append("|------|-------|")
            for kind, count in sorted(summary.edges_by_kind.items(), key=lambda x: -x[1]):
                lines.append(f"| {kind} | {count:,} |")
            lines.append("")

        # Files by language
        if summary.files_by_language:
            lines.append("### Files by Language")
            lines.append("")
            lines.append("| Language | Files |")
            lines.append("|----------|-------|")
            for lang, count in sorted(summary.files_by_language.items(), key=lambda x: -x[1]):
                lines.append(f"| {lang} | {count:,} |")
            lines.append("")

        # Frameworks
        if summary.frameworks:
            lines.append("### Detected Frameworks")
            lines.append("")
            for fw in summary.frameworks:
                lines.append(f"- {fw}")
            lines.append("")

        # Top nodes by PageRank
        if summary.top_nodes_by_pagerank:
            lines.append("### Top Nodes by PageRank")
            lines.append("")
            lines.append("| # | Name | Qualified Name | Score |")
            lines.append("|---|------|---------------|-------|")
            for i, (name, qname, score) in enumerate(summary.top_nodes_by_pagerank, 1):
                lines.append(f"| {i} | `{name}` | `{qname}` | {score:.6f} |")
            lines.append("")

        return "\n".join(lines)

    # ── Search Results ────────────────────────────────────────

    @staticmethod
    def format_search_results(nodes: list[Node], query: str) -> str:
        """Format search results as markdown."""
        lines: list[str] = []

        lines.append(f"## Search Results for: `{query}`")
        lines.append("")

        if not nodes:
            lines.append("*No results found.*")
            return "\n".join(lines)

        lines.append(f"Found **{len(nodes)}** result(s).")
        lines.append("")
        lines.append("| # | Kind | Name | File | Lines |")
        lines.append("|---|------|------|------|-------|")

        for i, node in enumerate(nodes, 1):
            kind = node.kind.value if isinstance(node.kind, NodeKind) else node.kind
            lines.append(
                f"| {i} | {kind} | `{node.qualified_name}` "
                f"| `{node.file_path}` | {node.start_line}–{node.end_line} |"
            )

        lines.append("")
        return "\n".join(lines)

    # ── File Overview ─────────────────────────────────────────

    @staticmethod
    def format_file_overview(
        file_path: str,
        nodes: list[Node],
        edges: list[Edge],
    ) -> str:
        """Format all symbols in a file as markdown."""
        lines: list[str] = []

        lines.append(f"## File: `{file_path}`")
        lines.append("")

        if not nodes:
            lines.append("*No symbols found in this file.*")
            return "\n".join(lines)

        lines.append(f"**{len(nodes)}** symbol(s), **{len(edges)}** relationship(s)")
        lines.append("")

        # Group nodes by kind
        by_kind: dict[str, list[Node]] = {}
        for node in sorted(nodes, key=lambda n: n.start_line):
            kind_val = node.kind.value if isinstance(node.kind, NodeKind) else node.kind
            by_kind.setdefault(kind_val, []).append(node)

        for kind, kind_nodes in by_kind.items():
            lines.append(f"### {kind.title()}s ({len(kind_nodes)})")
            lines.append("")
            for node in kind_nodes:
                sig = node.metadata.get("signature", node.name) if node.metadata else node.name
                vis = node.metadata.get("visibility", "") if node.metadata else ""
                prefix = f"{vis} " if vis else ""
                lines.append(f"- `{prefix}{sig}` (L{node.start_line}–{node.end_line})")
            lines.append("")

        return "\n".join(lines)

    # ── Pipeline Summary ──────────────────────────────────────

    @staticmethod
    def format_pipeline_summary(summary: PipelineSummary) -> str:
        """Format pipeline run results as markdown."""
        lines: list[str] = []

        lines.append("## Parse Results")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Files Found** | {summary.total_files:,} |")
        lines.append(f"| **Files Parsed** | {summary.files_parsed:,} |")
        lines.append(f"| **Files Skipped** | {summary.files_skipped:,} |")
        lines.append(f"| **Files Errored** | {summary.files_errored:,} |")
        lines.append(f"| **Nodes Added** | {summary.nodes_added:,} |")
        lines.append(f"| **Nodes Updated** | {summary.nodes_updated:,} |")
        lines.append(f"| **Nodes Removed** | {summary.nodes_removed:,} |")
        lines.append(f"| **Edges Added** | {summary.edges_added:,} |")
        lines.append(f"| **Total Nodes** | {summary.total_nodes:,} |")
        lines.append(f"| **Total Edges** | {summary.total_edges:,} |")
        lines.append(f"| **Parse Time** | {summary.total_parse_time_ms:.0f}ms |")
        lines.append(f"| **Pipeline Time** | {summary.total_pipeline_time_ms:.0f}ms |")

        if summary.resolution_rate > 0:
            lines.append(f"| **Resolution Rate** | {summary.resolution_rate:.1f}% |")
        if summary.avg_confidence > 0:
            lines.append(f"| **Avg Confidence** | {summary.avg_confidence:.2f} |")
        if summary.parse_errors > 0:
            lines.append(f"| **Parse Errors** | {summary.parse_errors} |")
        lines.append("")

        if summary.nodes_by_kind:
            lines.append("### Nodes by Kind")
            lines.append("")
            lines.append("| Kind | Count |")
            lines.append("|------|-------|")
            for kind, count in sorted(summary.nodes_by_kind.items(), key=lambda x: -x[1]):
                lines.append(f"| {kind} | {count:,} |")
            lines.append("")

        return "\n".join(lines)

    # ── Rich Terminal Rendering ───────────────────────────────

    @staticmethod
    def render_to_console(markdown_text: str, console: Console | None = None) -> None:
        """Render markdown text to the terminal using Rich."""
        if console is None:
            console = Console()
        console.print(Markdown(markdown_text))

    @staticmethod
    def render_summary_table(summary: GraphSummary, console: Console | None = None) -> None:
        """Render a rich summary table directly to the console."""
        if console is None:
            console = Console()

        # Header panel
        header = Text()
        header.append("CodeRAG", style="bold cyan")
        header.append(" — Graph Summary", style="dim")
        console.print(Panel(header, expand=False))

        # Overview table
        overview = Table(title="Overview", show_header=True, header_style="bold magenta")
        overview.add_column("Property", style="cyan")
        overview.add_column("Value", style="green")

        if summary.project_name:
            overview.add_row("Project", summary.project_name)
        if summary.project_root:
            overview.add_row("Root", summary.project_root)
        overview.add_row("Database", summary.db_path)
        if summary.db_size_bytes > 0:
            size_kb = summary.db_size_bytes / 1024
            size_str = f"{size_kb / 1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.1f} KB"
            overview.add_row("DB Size", size_str)
        if summary.last_parsed:
            overview.add_row("Last Parsed", summary.last_parsed)
        overview.add_row("Total Nodes", f"{summary.total_nodes:,}")
        overview.add_row("Total Edges", f"{summary.total_edges:,}")
        overview.add_row("Communities", str(summary.communities))
        overview.add_row("Avg Confidence", f"{summary.avg_confidence:.2f}")
        console.print(overview)
        console.print()

        # Nodes by kind
        if summary.nodes_by_kind:
            nodes_table = Table(title="Nodes by Kind", show_header=True, header_style="bold blue")
            nodes_table.add_column("Kind", style="cyan")
            nodes_table.add_column("Count", justify="right", style="green")
            for kind, count in sorted(summary.nodes_by_kind.items(), key=lambda x: -x[1]):
                nodes_table.add_row(kind, f"{count:,}")
            console.print(nodes_table)
            console.print()

        # Edges by kind
        if summary.edges_by_kind:
            edges_table = Table(title="Edges by Kind", show_header=True, header_style="bold blue")
            edges_table.add_column("Kind", style="cyan")
            edges_table.add_column("Count", justify="right", style="green")
            for kind, count in sorted(summary.edges_by_kind.items(), key=lambda x: -x[1]):
                edges_table.add_row(kind, f"{count:,}")
            console.print(edges_table)
            console.print()

        # Files by language
        if summary.files_by_language:
            lang_table = Table(title="Files by Language", show_header=True, header_style="bold blue")
            lang_table.add_column("Language", style="cyan")
            lang_table.add_column("Files", justify="right", style="green")
            for lang, count in sorted(summary.files_by_language.items(), key=lambda x: -x[1]):
                lang_table.add_row(lang, f"{count:,}")
            console.print(lang_table)
            console.print()

        # Top nodes
        if summary.top_nodes_by_pagerank:
            top_table = Table(title="Top Nodes by PageRank", show_header=True, header_style="bold yellow")
            top_table.add_column("#", justify="right", style="dim")
            top_table.add_column("Name", style="cyan")
            top_table.add_column("Qualified Name", style="white")
            top_table.add_column("Score", justify="right", style="green")
            for i, (name, qname, score) in enumerate(summary.top_nodes_by_pagerank, 1):
                top_table.add_row(str(i), name, qname, f"{score:.6f}")
            console.print(top_table)

    @staticmethod
    def render_parse_results(summary: PipelineSummary, console: Console | None = None) -> None:
        """Render pipeline results with rich tables."""
        if console is None:
            console = Console()

        # Results table
        table = Table(title="Parse Results", show_header=True, header_style="bold green")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Files Found", f"{summary.total_files:,}")
        table.add_row("Files Parsed", f"{summary.files_parsed:,}")
        table.add_row("Files Skipped", f"{summary.files_skipped:,}")
        if summary.files_errored > 0:
            table.add_row("Files Errored", f"[red]{summary.files_errored:,}[/red]")
        table.add_row("Nodes Added", f"{summary.nodes_added:,}")
        table.add_row("Edges Added", f"{summary.edges_added:,}")
        table.add_row("Total Nodes", f"{summary.total_nodes:,}")
        table.add_row("Total Edges", f"{summary.total_edges:,}")
        table.add_row("Parse Time", f"{summary.total_parse_time_ms:.0f}ms")
        table.add_row("Pipeline Time", f"{summary.total_pipeline_time_ms:.0f}ms")
        console.print(table)

        # Nodes by kind
        if summary.nodes_by_kind:
            console.print()
            nk_table = Table(title="Nodes by Kind", show_header=True, header_style="bold blue")
            nk_table.add_column("Kind", style="cyan")
            nk_table.add_column("Count", justify="right", style="green")
            for kind, count in sorted(summary.nodes_by_kind.items(), key=lambda x: -x[1]):
                nk_table.add_row(kind, f"{count:,}")
            console.print(nk_table)

    @staticmethod
    def render_search_results(
        nodes: list[Node],
        query: str,
        console: Console | None = None,
    ) -> None:
        """Render search results with rich tables."""
        if console is None:
            console = Console()

        if not nodes:
            console.print(f"[yellow]No results found for:[/yellow] [bold]{query}[/bold]")
            return

        console.print(f"\n[bold]Search results for:[/bold] [cyan]{query}[/cyan]")
        console.print(f"Found [green]{len(nodes)}[/green] result(s).\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Kind", style="cyan", width=12)
        table.add_column("Name", style="white")
        table.add_column("File", style="dim")
        table.add_column("Lines", justify="right", style="green")

        for i, node in enumerate(nodes, 1):
            kind = node.kind.value if isinstance(node.kind, NodeKind) else node.kind
            table.add_row(
                str(i),
                kind,
                node.qualified_name,
                node.file_path,
                f"{node.start_line}–{node.end_line}",
            )

        console.print(table)
