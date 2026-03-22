"""MCP tools for token counting and session cost tracking.

Provides tools to estimate token counts and costs across
different AI models, and track session-level token usage.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from coderag.session.cost_models import (
    MODEL_PRICING,
    estimate_cost,
    estimate_tokens,
    get_pricing,
    list_models,
)
from coderag.session.token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# Global tracker instance for the MCP session
_session_tracker: TokenTracker | None = None


def _get_tracker() -> TokenTracker:
    """Get or create the global session tracker."""
    global _session_tracker
    if _session_tracker is None:
        _session_tracker = TokenTracker()
    return _session_tracker


def reset_tracker(model: str = "claude-sonnet-4") -> TokenTracker:
    """Reset the global tracker with a new model. Returns the new tracker."""
    global _session_tracker
    _session_tracker = TokenTracker(model=model)
    return _session_tracker


def register_token_tools(mcp: FastMCP) -> None:
    """Register token counting and cost tracking MCP tools."""

    @mcp.tool()
    def token_count_text(text: str, model: str = "") -> str:
        """Count tokens in a text string and estimate cost across models.

        Args:
            text: The text to count tokens for.
            model: Optional specific model to show cost for.
                   If empty, shows costs for all supported models.

        Returns:
            Formatted table with token count and cost per model.
        """
        tokens = estimate_tokens(text)
        char_count = len(text)

        lines = [
            "## Token Count Analysis",
            "",
            f"- **Characters**: {char_count:,}",
            f"- **Estimated tokens**: {tokens:,}",
            f"- **Ratio**: ~{char_count / tokens:.1f} chars/token",
            "",
        ]

        if model:
            pricing = get_pricing(model)
            if pricing:
                input_cost = estimate_cost(tokens, 0, 0, model)
                output_cost = estimate_cost(0, tokens, 0, model)
                cached_cost = estimate_cost(0, 0, tokens, model)
                lines.extend(
                    [
                        f"### Cost for {pricing.name}",
                        "",
                        "| Usage | Cost |",
                        "|-------|------|",
                        f"| As input | ${input_cost:.6f} |",
                        f"| As output | ${output_cost:.6f} |",
                        f"| As cached input | ${cached_cost:.6f} |",
                    ]
                )
            else:
                available = ", ".join(list_models())
                lines.append(f"Unknown model: {model}. Available: {available}")
        else:
            lines.extend(
                [
                    f"### Cost Estimates ({tokens:,} tokens)",
                    "",
                    "| Model | Input Cost | Output Cost | Cached Cost |",
                    "|-------|-----------|-------------|-------------|",
                ]
            )
            for name, pricing in MODEL_PRICING.items():
                ic = estimate_cost(tokens, 0, 0, name)
                oc = estimate_cost(0, tokens, 0, name)
                cc = estimate_cost(0, 0, tokens, name)
                lines.append(f"| {pricing.name} | ${ic:.6f} | ${oc:.6f} | ${cc:.6f} |")

        # Log to session tracker
        tracker = _get_tracker()
        tracker.log_tool_call("token_count_text", text[:200], "\n".join(lines))

        return "\n".join(lines)

    @mcp.tool()
    def token_session_stats(model: str = "") -> str:
        """Get current session token usage statistics.

        Shows aggregated token usage, costs, and savings for the
        current MCP session.

        Args:
            model: Optional model to switch to for future tracking.

        Returns:
            Formatted session statistics.
        """
        tracker = _get_tracker()

        if model:
            pricing = get_pricing(model)
            if pricing:
                tracker.model = model

        stats = tracker.get_session_stats()

        lines = [
            "## Session Token Statistics",
            "",
            f"**Model**: {stats.model}",
            f"**Total events**: {stats.total_events}",
            "",
            "### Token Usage",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Input tokens | {stats.total_input_tokens:,} |",
            f"| Output tokens | {stats.total_output_tokens:,} |",
            f"| Cached tokens | {stats.total_cached_tokens:,} |",
            f"| **Total cost** | **${stats.total_cost:.6f}** |",
            "",
        ]

        if stats.total_events > 0:
            lines.extend(
                [
                    "### Averages",
                    "",
                    f"- Avg input/event: {stats.avg_input_per_event:,.0f} tokens",
                    f"- Avg output/event: {stats.avg_output_per_event:,.0f} tokens",
                    "",
                ]
            )

        if stats.tokens_saved_by_cache > 0:
            lines.extend(
                [
                    "### Cache Savings",
                    "",
                    f"- Tokens served from cache: {stats.tokens_saved_by_cache:,}",
                    f"- Estimated savings: {stats.estimated_savings_pct:.1f}%",
                    "",
                ]
            )

        if stats.cost_by_type:
            lines.extend(
                [
                    "### Cost by Event Type",
                    "",
                    "| Type | Cost |",
                    "|------|------|",
                ]
            )
            for event_type, cost in sorted(stats.cost_by_type.items()):
                lines.append(f"| {event_type} | ${cost:.6f} |")

        return "\n".join(lines)
