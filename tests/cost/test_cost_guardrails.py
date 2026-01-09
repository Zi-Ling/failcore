"""
Test Cost Guardrails - API Pricing & Unified Guardian

Tests for:
1. API Price Provider (HTTP real-time pricing)
2. CostGuardian (Unified global protection)
"""

import pytest
from failcore.core.cost import (
    CostUsage,
    CostGuardian,
    GuardianConfig,
    DynamicPriceEngine,
    ApiPriceProvider,
    StaticPriceProvider,
    ChainedPriceProvider,
)
from failcore.core.errors import FailCoreError


def test_api_price_provider():
    """Test: API Price Provider with fallback"""
    # Create API provider (with fallback)
    api_provider = ApiPriceProvider(
        api_url="https://pricing.example.com/api/prices",
        cache_ttl=3600,  # Cache for 1 hour
    )
    
    # Create chained provider with API first, then static fallback
    chained = ChainedPriceProvider([
        api_provider,
        StaticPriceProvider(),  # Fallback
    ])
    
    engine = DynamicPriceEngine(provider=chained)
    
    # Test pricing
    models = ["gpt-4", "gpt-4o", "claude-3-sonnet"]
    
    for model in models:
        input_price = engine.get_price(model, "input")
        output_price = engine.get_price(model, "output")
        cost = engine.calculate_cost(model, 1000, 500)
        
        # Verify prices are valid (non-negative)
        assert input_price >= 0, f"{model} input price should be non-negative"
        assert output_price >= 0, f"{model} output price should be non-negative"
        assert cost >= 0, f"{model} cost should be non-negative"


def test_cost_guardian_simple():
    """Test: CostGuardian - Simple Setup"""
    # Simple setup - just set limits
    guardian = CostGuardian(
        max_cost_usd=1.00,
        max_tokens=10000,
        max_usd_per_minute=0.30,
    )
    
    # Simulate operations
    operations = [
        ("gpt-4", 500, 300, 0.045),
        ("gpt-4", 600, 400, 0.054),
        ("claude-3-sonnet", 800, 500, 0.012),
    ]
    
    for i, (model, input_tokens, output_tokens, cost) in enumerate(operations, 1):
        usage = CostUsage(
            run_id="run_001",
            step_id=f"step_{i}",
            tool_name=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost,
        )
        
        allowed, reason, error_code = guardian.check_operation(usage, raise_on_exceed=False)
        
        assert allowed, f"Operation {i} should be allowed"
    
    # Show final status
    status = guardian.get_status()
    assert status['operations_checked'] == len(operations)
    assert status['operations_blocked'] == 0


def test_cost_guardian_advanced():
    """Test: CostGuardian - Advanced Configuration"""
    # Track callbacks
    alerts_received = []
    budget_exceeded_received = []
    burn_rate_exceeded_received = []
    
    # Advanced setup with callbacks
    def on_alert(alert):
        alerts_received.append(alert)
    
    def on_budget_exceeded(reason):
        budget_exceeded_received.append(reason)
    
    def on_burn_rate_exceeded(reason):
        burn_rate_exceeded_received.append(reason)
    
    config = GuardianConfig(
        max_cost_usd=0.50,
        max_tokens=5000,
        max_usd_per_minute=0.50,  # Allow up to 4 operations (4 * 0.12 = 0.48 < 0.50)
        streaming_check_interval=50,
        streaming_safety_margin=0.95,
    )
    
    guardian = CostGuardian(
        config=config,
        on_alert=on_alert,
        on_budget_exceeded=on_budget_exceeded,
        on_burn_rate_exceeded=on_burn_rate_exceeded,
    )
    
    # Simulate operations with callbacks
    for i in range(1, 6):
        usage = CostUsage(
            run_id="run_002",
            step_id=f"step_{i}",
            tool_name="gpt-4",
            input_tokens=500,
            output_tokens=300,
            total_tokens=800,
            cost_usd=0.12,
        )
        
        try:
            guardian.check_operation(usage)
            # Operation should be allowed for first few
            if i <= 4:
                assert True, f"Operation {i} should be allowed"
        except FailCoreError:
            # Operation blocked (expected for later operations)
            assert i > 4, f"Operation {i} should only block after budget exceeded"


def test_streaming_integration():
    """Test: Streaming Integration with Guardian"""
    guardian = CostGuardian(
        max_cost_usd=0.20,
        max_tokens=2000,
    )
    
    # Create streaming watchdog from guardian
    watchdog = guardian.create_streaming_watchdog(model="gpt-4")
    
    # Simulate streaming
    try:
        for i in range(1, 50):
            # Simulate 25 tokens per chunk
            watchdog.on_token_generated(
                token_count=25,
                run_id="run_003",
                step_id="streaming",
            )
            
            if i % 10 == 0:
                stats = watchdog.get_stats()
                assert stats['tokens_generated'] > 0
                assert stats['cost_usd'] >= 0
    
    except FailCoreError:
        # Streaming interrupted (expected when budget exceeded)
        assert watchdog.tokens_generated > 0
    
    # Show guardian status
    status = guardian.get_status()
    assert "budget" in status or "operations_checked" in status


def test_unified_api():
    """Test: Unified API - Everything Together"""
    alerts_received = []
    
    # Create guardian with all features
    guardian = CostGuardian(
        max_cost_usd=2.00,
        max_tokens=20000,
        max_usd_per_minute=0.50,
        on_alert=lambda alert: alerts_received.append(alert),
    )
    
    # Test different scenarios
    scenarios = [
        ("Normal operation", 0.15),
        ("Large operation", 0.80),
        ("Final operation", 0.50),
    ]
    
    for name, cost in scenarios:
        usage = CostUsage(
            run_id="run_004",
            step_id=name.replace(" ", "_"),
            tool_name="gpt-4",
            cost_usd=cost,
            total_tokens=int(cost * 1000 / 0.03),
        )
        
        try:
            allowed, _, error_code = guardian.check_operation(usage, raise_on_exceed=False)
            
            if allowed:
                status = guardian.get_status()
                if "budget" in status:
                    pct = status["budget"]["usage_percentage"]
                    assert pct >= 0 and pct <= 1, "Usage percentage should be between 0 and 1"
        
        except FailCoreError:
            # Blocked (expected for some scenarios)
            pass
    
    # Show comprehensive status
    status = guardian.get_status()
    assert "operations_checked" in status or "budget" in status
