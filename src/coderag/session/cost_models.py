"""Pricing models for popular AI models.

Provides cost estimation for token usage across different LLM providers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelPricing:
    """Pricing per 1M tokens."""

    name: str
    input_cost: float  # $ per 1M input tokens
    output_cost: float  # $ per 1M output tokens
    cached_cost: float  # $ per 1M cached input tokens
    context_window: int  # max context window size in tokens


# Pricing database (per 1M tokens)
MODEL_PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-4": ModelPricing("Claude Sonnet 4", 3.0, 15.0, 0.30, 200_000),
    "claude-opus-4": ModelPricing("Claude Opus 4", 15.0, 75.0, 1.50, 200_000),
    "claude-haiku-3.5": ModelPricing("Claude Haiku 3.5", 0.80, 4.0, 0.08, 200_000),
    "gpt-4o": ModelPricing("GPT-4o", 2.50, 10.0, 1.25, 128_000),
    "gpt-4.1": ModelPricing("GPT-4.1", 2.0, 8.0, 0.50, 1_000_000),
    "gpt-4.1-mini": ModelPricing("GPT-4.1 Mini", 0.40, 1.60, 0.10, 1_000_000),
    "gemini-2.5-pro": ModelPricing("Gemini 2.5 Pro", 1.25, 10.0, 0.315, 1_000_000),
    "gemini-2.5-flash": ModelPricing("Gemini 2.5 Flash", 0.15, 0.60, 0.0375, 1_000_000),
}


def get_pricing(model: str) -> ModelPricing | None:
    """Get pricing for a model. Supports partial matching."""
    # Exact match first
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    # Partial match
    for key, pricing in MODEL_PRICING.items():
        if model.lower() in key.lower() or key.lower() in model.lower():
            return pricing
    return None


def list_models() -> list[str]:
    """List all supported model names."""
    return list(MODEL_PRICING.keys())


def estimate_cost(input_tokens: int, output_tokens: int, cached_tokens: int, model: str) -> float:
    """Estimate cost in dollars for given token counts."""
    pricing = get_pricing(model)
    if not pricing:
        raise ValueError(f"Unknown model: {model}. Available: {list_models()}")
    cost = (
        (input_tokens / 1_000_000) * pricing.input_cost
        + (output_tokens / 1_000_000) * pricing.output_cost
        + (cached_tokens / 1_000_000) * pricing.cached_cost
    )
    return round(cost, 6)


def estimate_tokens(text: str) -> int:
    """Estimate token count from text. Rough approximation: 1 token ~ 4 chars."""
    return max(1, len(text) // 4)
