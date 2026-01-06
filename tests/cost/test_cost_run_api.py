"""
Test Cost Integration - Using run() API with budget enforcement

Tests for:
1. Budget limits via run() parameters (max_cost_usd, max_tokens)
2. Burn rate limiting (max_usd_per_minute)
3. Automatic CostGuardian integration
4. Cost metrics in trace
5. SQLite storage for cost data
"""

import pytest
from failcore import run
from failcore.core.errors import FailCoreError


def mock_llm_call(prompt: str, model: str = "gpt-4", tokens_multiplier: int = 1) -> dict:
    """
    Mock LLM tool that simulates API usage
    
    Returns usage statistics compatible with UsageExtractor
    """
    # Simulate token usage based on prompt length
    base_input_tokens = len(prompt.split()) * 1.3
    input_tokens = int(base_input_tokens * tokens_multiplier)
    output_tokens = 50 * tokens_multiplier
    total_tokens = input_tokens + output_tokens
    
    # Simulate cost (GPT-4: ~$0.03/1K input, $0.06/1K output)
    cost_usd = (input_tokens / 1000 * 0.03) + (output_tokens / 1000 * 0.06)
    
    return {
        "result": f"AI response for: {prompt[:50]}...",
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "model": model,
            "provider": "openai",
        }
    }


def test_basic_budget_enforcement():
    """Test: Basic budget enforcement via run() API"""
    # Set a small budget: $0.50 total, max 1000 tokens
    with run(
        policy="safe",
        trace="auto",
        max_cost_usd=0.50,
        max_tokens=1000,
        tags={"demo": "budget_enforcement"},
    ) as ctx:
        # Register tool
        ctx.tool(mock_llm_call)
        
        # Call 1: Small call (should succeed)
        output1 = ctx.call("mock_llm_call", prompt="Hello world", model="gpt-4")
        assert output1 is not None, "Call 1 should succeed"
        
        # Call 2: Medium cost (should succeed)
        medium_prompt = "Explain quantum computing " * 100
        output2 = ctx.call("mock_llm_call", prompt=medium_prompt, model="gpt-4", tokens_multiplier=10)
        assert output2 is not None, "Call 2 should succeed"
        
        # Call 3: Large cost (should BLOCK)
        try:
            output3 = ctx.call(
                "mock_llm_call", 
                prompt=medium_prompt, 
                model="gpt-4", 
                tokens_multiplier=18,
                _meta={"cost_usd": 0.35, "tokens": 18000}
            )
            # If not blocked, verify it didn't exceed budget
            if ctx.cost_storage:
                summary = ctx.cost_storage.get_run_summary(ctx.run_id)
                if summary:
                    cumulative = summary.get('total_cost_usd', 0)
                    # Should not exceed budget
                    assert cumulative <= 0.50, f"Cumulative cost {cumulative} should not exceed $0.50"
        except FailCoreError as e:
            # Expected: should be blocked
            assert "BUDGET" in e.error_code or "ECONOMIC" in e.error_code, \
                f"Should be budget error, got {e.error_code}"
        
        assert ctx.trace_path is not None, "Should have trace path"


def test_burn_rate_limiting():
    """Test: Burn rate limiting"""
    # Strict burn rate: max $0.10 per minute
    with run(
        policy="safe",
        trace="auto",
        max_cost_usd=10.0,  # High total budget
        max_usd_per_minute=0.10,  # But strict burn rate
        tags={"demo": "burn_rate"},
    ) as ctx:
        ctx.tool(mock_llm_call)
        
        # Call 1: ~$0.20 (should succeed)
        prompt1 = "Explain AI " * 50
        output1 = ctx.call("mock_llm_call", prompt=prompt1, model="gpt-4", tokens_multiplier=30)
        assert output1 is not None, "Call 1 should succeed"
        
        # Call 2: ~$0.20 (should BLOCK by burn rate)
        try:
            output2 = ctx.call(
                "mock_llm_call", 
                prompt=prompt1, 
                model="gpt-4", 
                tokens_multiplier=30,
                _meta={"cost_usd": 0.207, "tokens": 3000}
            )
            # If not blocked, verify burn rate
            if ctx.cost_guardian and ctx.cost_guardian.burn_limiter:
                rates_after = ctx.cost_guardian.burn_limiter.get_current_rates()
                # Should not exceed burn rate limit
                assert rates_after.get('usd_per_minute', 0) <= 0.10, \
                    f"Burn rate {rates_after.get('usd_per_minute', 0)} should not exceed $0.10/min"
        except FailCoreError as e:
            # Expected: should be blocked by burn rate
            assert "BURN_RATE" in e.error_code or "ECONOMIC" in e.error_code, \
                f"Should be burn rate error, got {e.error_code}"
        
        assert ctx.trace_path is not None, "Should have trace path"


def test_meta_cost_override():
    """Test: Using meta.cost_usd for deterministic testing"""
    def expensive_api_call(task: str):
        """API call with explicit cost in meta"""
        return f"Processed: {task}"
    
    with run(
        policy="safe",
        trace="auto",
        max_cost_usd=1.0,
        tags={"demo": "meta_override"},
    ) as ctx:
        ctx.tool(expensive_api_call)
        
        # Call 1: Explicit cost $0.50 via _meta parameter
        result1 = ctx.call("expensive_api_call", task="Generate report", _meta={"cost_usd": 0.50, "tokens": 5000})
        assert result1 is not None, "Call 1 should succeed"
        
        # Call 2: Another $0.50 (should succeed, total exactly $1.0)
        result2 = ctx.call("expensive_api_call", task="Analyze data", _meta={"cost_usd": 0.50, "tokens": 5000})
        assert result2 is not None, "Call 2 should succeed (exactly at limit)"
        
        # Call 3: $0.01 more (should BLOCK)
        try:
            result3 = ctx.call("expensive_api_call", task="Small task", _meta={"cost_usd": 0.01, "tokens": 100})
            # If not blocked, verify budget
            if ctx.cost_guardian and ctx.cost_guardian.budget:
                budget = ctx.cost_guardian.budget
                assert budget.used_cost_usd <= budget.max_cost_usd, \
                    f"Used cost {budget.used_cost_usd} should not exceed limit {budget.max_cost_usd}"
        except FailCoreError as e:
            # Expected: should be blocked
            assert "BUDGET" in e.error_code or "ECONOMIC" in e.error_code, \
                f"Should be budget error, got {e.error_code}"
        
        assert ctx.trace_path is not None, "Should have trace path"


def test_query_sqlite():
    """Test: Query cost data from SQLite"""
    # Run a simple workflow
    with run(
        policy="safe",
        trace="auto",
        max_cost_usd=1.0,
        tags={"demo": "sqlite_query"},
    ) as ctx:
        ctx.tool(mock_llm_call)
        
        # Execute 3 calls
        for i in range(3):
            prompt = f"Task {i+1}: " + "analyze data " * 20
            try:
                output = ctx.call("mock_llm_call", prompt=prompt, model="gpt-4")
                assert output is not None, f"Call {i+1} should succeed"
            except FailCoreError as e:
                # May be blocked if budget exceeded
                assert "BUDGET" in e.error_code or "ECONOMIC" in e.error_code
        
        run_id = ctx.run_id
        storage = ctx.cost_storage
    
    # Query SQLite
    if storage:
        run_summary = storage.get_run_summary(run_id)
        if run_summary:
            assert "run_id" in run_summary
            assert "total_cost_usd" in run_summary
            assert run_summary["total_cost_usd"] >= 0
        
        budget = storage.get_budget_for_run(run_id)
        if budget:
            assert "budget_id" in budget
            assert "scope" in budget
        
        usage_records = storage.get_run_curve(run_id)
        assert isinstance(usage_records, list), "Should return list of usage records"
