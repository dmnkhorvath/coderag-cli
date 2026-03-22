"""Tests for token_tracker module."""

from __future__ import annotations

from datetime import datetime

from coderag.session.cost_models import get_pricing
from coderag.session.token_tracker import SessionStats, TokenEvent, TokenTracker


class TestTokenEvent:
    """Tests for TokenEvent dataclass."""

    def test_create_event(self):
        event = TokenEvent(
            timestamp=datetime.now(),
            event_type="context_injection",
            input_tokens=100,
            output_tokens=0,
        )
        assert event.event_type == "context_injection"
        assert event.input_tokens == 100
        assert event.output_tokens == 0
        assert event.cached_tokens == 0
        assert event.tool_name is None
        assert event.description == ""
        assert event.cost == 0.0

    def test_event_with_all_fields(self):
        event = TokenEvent(
            timestamp=datetime.now(),
            event_type="tool_call",
            input_tokens=500,
            output_tokens=200,
            cached_tokens=100,
            tool_name="search",
            description="Search for main",
            cost=0.005,
        )
        assert event.tool_name == "search"
        assert event.cached_tokens == 100
        assert event.cost == 0.005


class TestSessionStats:
    """Tests for SessionStats dataclass."""

    def test_default_values(self):
        stats = SessionStats()
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_cached_tokens == 0
        assert stats.total_cost == 0.0
        assert stats.total_events == 0
        assert stats.avg_input_per_event == 0.0
        assert stats.avg_output_per_event == 0.0
        assert stats.tokens_saved_by_cache == 0
        assert stats.estimated_savings_pct == 0.0
        assert stats.cost_by_type == {}
        assert stats.model == ""


class TestTokenTracker:
    """Tests for TokenTracker class."""

    def test_init_default_model(self):
        tracker = TokenTracker()
        assert tracker.model == "claude-sonnet-4"
        assert tracker.events == []

    def test_init_custom_model(self):
        tracker = TokenTracker(model="gpt-4o")
        assert tracker.model == "gpt-4o"

    def test_log_context_injection(self):
        tracker = TokenTracker()
        event = tracker.log_context_injection("Hello world test text", "test context")
        assert event.event_type == "context_injection"
        assert event.input_tokens > 0
        assert event.output_tokens == 0
        assert event.description == "test context"
        assert event.cost > 0
        assert len(tracker.events) == 1

    def test_log_context_injection_default_description(self):
        tracker = TokenTracker()
        event = tracker.log_context_injection("some text")
        assert event.description == "pre-loaded context"

    def test_log_tool_call(self):
        tracker = TokenTracker()
        event = tracker.log_tool_call("search", "find main entry", "result: main.py")
        assert event.event_type == "tool_call"
        assert event.input_tokens > 0
        assert event.output_tokens > 0
        assert event.tool_name == "search"
        assert event.description == "Tool: search"
        assert event.cost > 0
        assert len(tracker.events) == 1

    def test_log_query(self):
        tracker = TokenTracker()
        event = tracker.log_query("What is the entry point?", "The entry point is main.py")
        assert event.event_type == "query"
        assert event.input_tokens > 0
        assert event.output_tokens > 0
        assert "What is the entry point?" in event.description
        assert event.cost > 0
        assert len(tracker.events) == 1

    def test_log_query_truncates_description(self):
        tracker = TokenTracker()
        long_query = "x" * 200
        event = tracker.log_query(long_query, "response")
        assert len(event.description) <= 100

    def test_log_cached(self):
        tracker = TokenTracker()
        event = tracker.log_cached("cached content here", "cached data")
        assert event.event_type == "cached"
        assert event.input_tokens == 0
        assert event.output_tokens == 0
        assert event.cached_tokens > 0
        assert event.description == "cached data"
        assert event.cost > 0  # cached still has cost, just lower
        assert len(tracker.events) == 1

    def test_log_cached_default_description(self):
        tracker = TokenTracker()
        event = tracker.log_cached("some cached text")
        assert event.description == "cached context"

    def test_multiple_events(self):
        tracker = TokenTracker()
        tracker.log_context_injection("context text")
        tracker.log_tool_call("search", "query", "result")
        tracker.log_query("question", "answer")
        tracker.log_cached("cached")
        assert len(tracker.events) == 4

    def test_get_session_stats_empty(self):
        tracker = TokenTracker()
        stats = tracker.get_session_stats()
        assert stats.total_events == 0
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_cached_tokens == 0
        assert stats.total_cost == 0.0
        assert stats.avg_input_per_event == 0.0
        assert stats.avg_output_per_event == 0.0
        assert stats.model == "claude-sonnet-4"

    def test_get_session_stats_aggregation(self):
        tracker = TokenTracker()
        tracker.log_context_injection("a" * 400)  # ~100 tokens
        tracker.log_tool_call("search", "b" * 200, "c" * 200)  # ~50 + ~50
        stats = tracker.get_session_stats()
        assert stats.total_events == 2
        assert stats.total_input_tokens > 0
        assert stats.total_output_tokens > 0
        assert stats.total_cost > 0
        assert stats.model == "claude-sonnet-4"

    def test_get_session_stats_averages(self):
        tracker = TokenTracker()
        tracker.log_context_injection("a" * 400)  # ~100 input tokens
        tracker.log_context_injection("b" * 800)  # ~200 input tokens
        stats = tracker.get_session_stats()
        assert stats.total_events == 2
        assert stats.avg_input_per_event == stats.total_input_tokens / 2
        assert stats.avg_output_per_event == 0.0  # context injection has no output

    def test_get_session_stats_cost_by_type(self):
        tracker = TokenTracker()
        tracker.log_context_injection("a" * 400)
        tracker.log_tool_call("search", "query", "result")
        tracker.log_query("q", "a")
        stats = tracker.get_session_stats()
        assert "context_injection" in stats.cost_by_type
        assert "tool_call" in stats.cost_by_type
        assert "query" in stats.cost_by_type

    def test_get_session_stats_cache_savings(self):
        tracker = TokenTracker()
        tracker.log_cached("x" * 4000)  # ~1000 cached tokens
        stats = tracker.get_session_stats()
        assert stats.tokens_saved_by_cache > 0
        assert stats.estimated_savings_pct > 0
        # For claude-sonnet-4: cached is $0.30 vs input $3.0 = 90% savings
        pricing = get_pricing("claude-sonnet-4")
        expected_savings = round((1 - pricing.cached_cost / pricing.input_cost) * 100, 1)
        assert stats.estimated_savings_pct == expected_savings

    def test_get_session_stats_no_cache_no_savings(self):
        tracker = TokenTracker()
        tracker.log_context_injection("text")
        stats = tracker.get_session_stats()
        assert stats.tokens_saved_by_cache == 0
        assert stats.estimated_savings_pct == 0.0

    def test_reset(self):
        tracker = TokenTracker()
        tracker.log_context_injection("text")
        tracker.log_tool_call("search", "q", "r")
        assert len(tracker.events) == 2
        tracker.reset()
        assert len(tracker.events) == 0
        stats = tracker.get_session_stats()
        assert stats.total_events == 0

    def test_to_dict(self):
        tracker = TokenTracker(model="gpt-4o")
        tracker.log_context_injection("hello world")
        data = tracker.to_dict()
        assert data["model"] == "gpt-4o"
        assert len(data["events"]) == 1
        assert "timestamp" in data["events"][0]
        assert "event_type" in data["events"][0]
        assert "input_tokens" in data["events"][0]
        assert "output_tokens" in data["events"][0]
        assert "cached_tokens" in data["events"][0]
        assert "tool_name" in data["events"][0]
        assert "description" in data["events"][0]
        assert "cost" in data["events"][0]
        assert "stats" in data
        assert data["stats"]["total_input"] > 0

    def test_to_dict_empty(self):
        tracker = TokenTracker()
        data = tracker.to_dict()
        assert data["model"] == "claude-sonnet-4"
        assert data["events"] == []
        assert data["stats"]["total_input"] == 0
        assert data["stats"]["total_output"] == 0
        assert data["stats"]["total_cached"] == 0
        assert data["stats"]["total_cost"] == 0

    def test_to_dict_serialization(self):
        """Ensure to_dict output is JSON-serializable."""
        import json

        tracker = TokenTracker()
        tracker.log_context_injection("test")
        tracker.log_tool_call("search", "q", "r")
        tracker.log_cached("cached")
        data = tracker.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["model"] == "claude-sonnet-4"

    def test_different_models(self):
        """Test that different models produce different costs."""
        text = "x" * 4000  # ~1000 tokens
        tracker_sonnet = TokenTracker(model="claude-sonnet-4")
        tracker_flash = TokenTracker(model="gemini-2.5-flash")
        event_sonnet = tracker_sonnet.log_context_injection(text)
        event_flash = tracker_flash.log_context_injection(text)
        # Sonnet is more expensive than Flash
        assert event_sonnet.cost > event_flash.cost

    def test_stats_model_field(self):
        tracker = TokenTracker(model="gpt-4.1-mini")
        stats = tracker.get_session_stats()
        assert stats.model == "gpt-4.1-mini"
