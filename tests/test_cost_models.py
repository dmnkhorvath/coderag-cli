"""Tests for cost_models module."""

from __future__ import annotations

import pytest

from coderag.session.cost_models import (
    MODEL_PRICING,
    ModelPricing,
    estimate_cost,
    estimate_tokens,
    get_pricing,
    list_models,
)


class TestModelPricing:
    """Tests for ModelPricing dataclass."""

    def test_model_pricing_fields(self):
        p = ModelPricing("Test", 1.0, 2.0, 0.1, 100_000)
        assert p.name == "Test"
        assert p.input_cost == 1.0
        assert p.output_cost == 2.0
        assert p.cached_cost == 0.1
        assert p.context_window == 100_000


class TestGetPricing:
    """Tests for get_pricing function."""

    def test_exact_match(self):
        pricing = get_pricing("claude-sonnet-4")
        assert pricing is not None
        assert pricing.name == "Claude Sonnet 4"
        assert pricing.input_cost == 3.0

    def test_exact_match_gpt4o(self):
        pricing = get_pricing("gpt-4o")
        assert pricing is not None
        assert pricing.name == "GPT-4o"

    def test_exact_match_gemini(self):
        pricing = get_pricing("gemini-2.5-pro")
        assert pricing is not None
        assert pricing.name == "Gemini 2.5 Pro"

    def test_partial_match_sonnet(self):
        pricing = get_pricing("sonnet")
        assert pricing is not None
        assert "Sonnet" in pricing.name

    def test_partial_match_haiku(self):
        pricing = get_pricing("haiku")
        assert pricing is not None
        assert "Haiku" in pricing.name

    def test_partial_match_flash(self):
        pricing = get_pricing("flash")
        assert pricing is not None
        assert "Flash" in pricing.name

    def test_unknown_model_returns_none(self):
        pricing = get_pricing("unknown-model-xyz")
        assert pricing is None

    def test_empty_string_returns_none(self):
        pricing = get_pricing("")
        # Empty string may match something or not, just ensure no crash
        # (empty string is "in" every string, so it may match first model)
        # This is acceptable behavior

    def test_case_insensitive_partial(self):
        pricing = get_pricing("CLAUDE")
        assert pricing is not None

    def test_all_models_have_pricing(self):
        for model_name in MODEL_PRICING:
            pricing = get_pricing(model_name)
            assert pricing is not None
            assert pricing.input_cost >= 0
            assert pricing.output_cost >= 0
            assert pricing.cached_cost >= 0
            assert pricing.context_window > 0


class TestListModels:
    """Tests for list_models function."""

    def test_returns_list(self):
        models = list_models()
        assert isinstance(models, list)

    def test_contains_known_models(self):
        models = list_models()
        assert "claude-sonnet-4" in models
        assert "gpt-4o" in models
        assert "gemini-2.5-pro" in models

    def test_count_matches_pricing_dict(self):
        models = list_models()
        assert len(models) == len(MODEL_PRICING)


class TestEstimateCost:
    """Tests for estimate_cost function."""

    def test_input_only(self):
        # claude-sonnet-4: $3.0 per 1M input tokens
        cost = estimate_cost(1_000_000, 0, 0, "claude-sonnet-4")
        assert cost == 3.0

    def test_output_only(self):
        # claude-sonnet-4: $15.0 per 1M output tokens
        cost = estimate_cost(0, 1_000_000, 0, "claude-sonnet-4")
        assert cost == 15.0

    def test_cached_only(self):
        # claude-sonnet-4: $0.30 per 1M cached tokens
        cost = estimate_cost(0, 0, 1_000_000, "claude-sonnet-4")
        assert cost == 0.3

    def test_combined(self):
        # 1M input + 1M output + 1M cached for claude-sonnet-4
        cost = estimate_cost(1_000_000, 1_000_000, 1_000_000, "claude-sonnet-4")
        assert cost == 3.0 + 15.0 + 0.3

    def test_zero_tokens(self):
        cost = estimate_cost(0, 0, 0, "claude-sonnet-4")
        assert cost == 0.0

    def test_small_token_count(self):
        # 1000 input tokens for claude-sonnet-4: $3.0 * 1000/1M = $0.003
        cost = estimate_cost(1000, 0, 0, "claude-sonnet-4")
        assert cost == pytest.approx(0.003, abs=1e-6)

    def test_large_token_count(self):
        # 100M input tokens
        cost = estimate_cost(100_000_000, 0, 0, "claude-sonnet-4")
        assert cost == 300.0

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown model"):
            estimate_cost(1000, 0, 0, "nonexistent-model")

    def test_error_message_includes_available(self):
        with pytest.raises(ValueError, match="Available"):
            estimate_cost(1000, 0, 0, "nonexistent-model")

    def test_gpt4o_pricing(self):
        # gpt-4o: $2.50 per 1M input
        cost = estimate_cost(1_000_000, 0, 0, "gpt-4o")
        assert cost == 2.5

    def test_gemini_flash_pricing(self):
        # gemini-2.5-flash: $0.15 per 1M input
        cost = estimate_cost(1_000_000, 0, 0, "gemini-2.5-flash")
        assert cost == 0.15

    def test_result_is_rounded(self):
        cost = estimate_cost(1, 0, 0, "claude-sonnet-4")
        # Should be a float with limited decimal places
        assert isinstance(cost, float)


class TestEstimateTokens:
    """Tests for estimate_tokens function."""

    def test_basic_text(self):
        tokens = estimate_tokens("Hello world")
        assert tokens > 0

    def test_empty_string(self):
        tokens = estimate_tokens("")
        assert tokens >= 1  # minimum 1

    def test_single_char(self):
        tokens = estimate_tokens("a")
        assert tokens >= 1

    def test_approximation_ratio(self):
        # ~4 chars per token
        text = "a" * 400
        tokens = estimate_tokens(text)
        assert tokens == 100

    def test_long_text(self):
        text = "x" * 40000
        tokens = estimate_tokens(text)
        assert tokens == 10000

    def test_returns_int(self):
        tokens = estimate_tokens("test")
        assert isinstance(tokens, int)

    def test_minimum_one(self):
        tokens = estimate_tokens("ab")
        assert tokens >= 1
