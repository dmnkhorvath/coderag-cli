"""Token tracking system for coding sessions.

Tracks token usage events and computes session statistics
including cost estimates and cache savings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from coderag.session.cost_models import estimate_cost, estimate_tokens, get_pricing


@dataclass
class TokenEvent:
    """A single token usage event."""

    timestamp: datetime
    event_type: str  # "context_injection", "tool_call", "query", "cached"
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    tool_name: str | None = None
    description: str = ""
    cost: float = 0.0  # computed


@dataclass
class SessionStats:
    """Aggregated session statistics."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    total_cost: float = 0.0
    total_events: int = 0
    avg_input_per_event: float = 0.0
    avg_output_per_event: float = 0.0
    tokens_saved_by_cache: int = 0
    estimated_savings_pct: float = 0.0
    cost_by_type: dict[str, float] = field(default_factory=dict)
    model: str = ""


class TokenTracker:
    """Track token usage across a coding session."""

    def __init__(self, model: str = "claude-sonnet-4") -> None:
        self.model = model
        self.events: list[TokenEvent] = []

    def log_context_injection(self, text: str, description: str = "pre-loaded context") -> TokenEvent:
        """Log tokens used for pre-loaded context."""
        tokens = estimate_tokens(text)
        event = TokenEvent(
            timestamp=datetime.now(),
            event_type="context_injection",
            input_tokens=tokens,
            output_tokens=0,
            cached_tokens=0,
            description=description,
            cost=estimate_cost(tokens, 0, 0, self.model),
        )
        self.events.append(event)
        return event

    def log_tool_call(self, tool_name: str, input_text: str, output_text: str) -> TokenEvent:
        """Log tokens used for an MCP tool call."""
        input_tokens = estimate_tokens(input_text)
        output_tokens = estimate_tokens(output_text)
        event = TokenEvent(
            timestamp=datetime.now(),
            event_type="tool_call",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_name=tool_name,
            description=f"Tool: {tool_name}",
            cost=estimate_cost(input_tokens, output_tokens, 0, self.model),
        )
        self.events.append(event)
        return event

    def log_query(self, query: str, response: str) -> TokenEvent:
        """Log a user query and response."""
        input_tokens = estimate_tokens(query)
        output_tokens = estimate_tokens(response)
        event = TokenEvent(
            timestamp=datetime.now(),
            event_type="query",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            description=query[:100],
            cost=estimate_cost(input_tokens, output_tokens, 0, self.model),
        )
        self.events.append(event)
        return event

    def log_cached(self, text: str, description: str = "cached context") -> TokenEvent:
        """Log tokens served from cache (cheaper)."""
        tokens = estimate_tokens(text)
        event = TokenEvent(
            timestamp=datetime.now(),
            event_type="cached",
            input_tokens=0,
            output_tokens=0,
            cached_tokens=tokens,
            description=description,
            cost=estimate_cost(0, 0, tokens, self.model),
        )
        self.events.append(event)
        return event

    def get_session_stats(self) -> SessionStats:
        """Get aggregated session statistics."""
        stats = SessionStats(model=self.model)
        cost_by_type: dict[str, float] = {}

        for event in self.events:
            stats.total_input_tokens += event.input_tokens
            stats.total_output_tokens += event.output_tokens
            stats.total_cached_tokens += event.cached_tokens
            stats.total_cost += event.cost
            stats.total_events += 1
            cost_by_type[event.event_type] = cost_by_type.get(event.event_type, 0) + event.cost

        if stats.total_events > 0:
            stats.avg_input_per_event = stats.total_input_tokens / stats.total_events
            stats.avg_output_per_event = stats.total_output_tokens / stats.total_events

        # Savings from caching
        if stats.total_cached_tokens > 0:
            pricing = get_pricing(self.model)
            if pricing:
                full_cost = (stats.total_cached_tokens / 1_000_000) * pricing.input_cost
                cached_cost = (stats.total_cached_tokens / 1_000_000) * pricing.cached_cost
                stats.tokens_saved_by_cache = stats.total_cached_tokens
                if full_cost > 0:
                    stats.estimated_savings_pct = round((1 - cached_cost / full_cost) * 100, 1)

        stats.cost_by_type = cost_by_type
        return stats

    def reset(self) -> None:
        """Clear all events."""
        self.events.clear()

    def to_dict(self) -> dict:
        """Serialize tracker state to dict."""
        return {
            "model": self.model,
            "events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "cached_tokens": e.cached_tokens,
                    "tool_name": e.tool_name,
                    "description": e.description,
                    "cost": e.cost,
                }
                for e in self.events
            ],
            "stats": {
                "total_input": sum(e.input_tokens for e in self.events),
                "total_output": sum(e.output_tokens for e in self.events),
                "total_cached": sum(e.cached_tokens for e in self.events),
                "total_cost": sum(e.cost for e in self.events),
            },
        }
