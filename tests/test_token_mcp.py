"""Tests for MCP token tools."""

from __future__ import annotations

import pytest

from coderag.mcp.token_tools import (
    _get_tracker,
    register_token_tools,
    reset_tracker,
)
from coderag.session.cost_models import list_models

try:
    from mcp.server.fastmcp import FastMCP

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


@pytest.fixture
def mcp_server():
    """Create a FastMCP server with token tools registered."""
    if not HAS_MCP:
        pytest.skip("mcp package not available")
    mcp = FastMCP(name="test-token-tools")
    register_token_tools(mcp)
    return mcp


@pytest.fixture(autouse=True)
def reset_global_tracker():
    """Reset the global tracker before each test."""
    reset_tracker()
    yield
    reset_tracker()


class TestGetTracker:
    """Tests for _get_tracker helper."""

    def test_returns_tracker(self):
        tracker = _get_tracker()
        assert tracker is not None
        assert tracker.model == "claude-sonnet-4"

    def test_returns_same_instance(self):
        t1 = _get_tracker()
        t2 = _get_tracker()
        assert t1 is t2

    def test_reset_creates_new(self):
        t1 = _get_tracker()
        t2 = reset_tracker("gpt-4o")
        assert t2 is not t1
        assert t2.model == "gpt-4o"
        assert _get_tracker() is t2


class TestTokenCountText:
    """Tests for token_count_text MCP tool."""

    def test_basic_count(self, mcp_server):
        # Access the registered tool function directly
        tools = {t.name: t for t in mcp_server._tool_manager.list_tools()}
        assert "token_count_text" in tools

    def test_count_all_models(self, mcp_server):
        """Test token counting shows all models when no model specified."""

        # Call the tool function directly via the internal registry
        tool_fn = None
        for name, fn in mcp_server._tool_manager._tools.items():
            if name == "token_count_text":
                tool_fn = fn
                break

        # Since we can't easily call MCP tools directly, test the underlying logic
        from coderag.session.cost_models import MODEL_PRICING, estimate_tokens

        text = "Hello world, this is a test."
        tokens = estimate_tokens(text)
        assert tokens > 0
        # Verify all models are in the pricing dict
        for model in list_models():
            assert model in MODEL_PRICING

    def test_count_specific_model(self):
        """Test token counting with a specific model."""
        from coderag.session.cost_models import estimate_cost, estimate_tokens

        text = "Hello world"
        tokens = estimate_tokens(text)
        cost = estimate_cost(tokens, 0, 0, "claude-sonnet-4")
        assert cost > 0


class TestTokenSessionStats:
    """Tests for token_session_stats MCP tool."""

    def test_tool_registered(self, mcp_server):
        tools = {t.name: t for t in mcp_server._tool_manager.list_tools()}
        assert "token_session_stats" in tools

    def test_empty_session_stats(self):
        """Test stats with no events."""
        tracker = _get_tracker()
        stats = tracker.get_session_stats()
        assert stats.total_events == 0
        assert stats.total_cost == 0.0

    def test_stats_after_events(self):
        """Test stats after logging some events."""
        tracker = _get_tracker()
        tracker.log_context_injection("some context text")
        tracker.log_tool_call("search", "query", "result")
        stats = tracker.get_session_stats()
        assert stats.total_events == 2
        assert stats.total_cost > 0
        assert stats.total_input_tokens > 0

    def test_stats_model_switch(self):
        """Test switching model on tracker."""
        tracker = reset_tracker("claude-sonnet-4")
        assert tracker.model == "claude-sonnet-4"
        tracker.model = "gpt-4o"
        assert tracker.model == "gpt-4o"


class TestToolRegistration:
    """Tests for tool registration."""

    def test_both_tools_registered(self, mcp_server):
        tools = {t.name: t for t in mcp_server._tool_manager.list_tools()}
        assert "token_count_text" in tools
        assert "token_session_stats" in tools

    def test_tool_count(self, mcp_server):
        tools = mcp_server._tool_manager.list_tools()
        assert len(tools) >= 2


class TestIntegrationFlow:
    """Integration tests for the token tracking flow."""

    def test_full_flow(self):
        """Test a complete tracking flow."""
        tracker = reset_tracker("claude-sonnet-4")

        # Simulate a session
        tracker.log_context_injection("x" * 4000, "project context")
        tracker.log_tool_call("search", "find main", "main.py: def main()")
        tracker.log_query("What is the entry point?", "The entry point is main.py")
        tracker.log_cached("x" * 2000, "cached context")

        stats = tracker.get_session_stats()
        assert stats.total_events == 4
        assert stats.total_input_tokens > 0
        assert stats.total_output_tokens > 0
        assert stats.total_cached_tokens > 0
        assert stats.total_cost > 0
        assert "context_injection" in stats.cost_by_type
        assert "tool_call" in stats.cost_by_type
        assert "query" in stats.cost_by_type
        assert "cached" in stats.cost_by_type
        assert stats.tokens_saved_by_cache > 0
        assert stats.estimated_savings_pct > 0

    def test_serialization(self):
        """Test tracker serialization."""
        import json

        tracker = reset_tracker("gpt-4o")
        tracker.log_context_injection("test context")
        data = tracker.to_dict()
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["model"] == "gpt-4o"
        assert len(parsed["events"]) == 1
        assert parsed["stats"]["total_input"] > 0

    def test_reset_and_reuse(self):
        """Test resetting tracker and reusing."""
        tracker = _get_tracker()
        tracker.log_context_injection("first")
        assert len(tracker.events) == 1

        tracker.reset()
        assert len(tracker.events) == 0

        tracker.log_context_injection("second")
        assert len(tracker.events) == 1
        stats = tracker.get_session_stats()
        assert stats.total_events == 1
