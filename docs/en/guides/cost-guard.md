# Cost Control

This guide explains how to use FailCore to control AI agent costs.

---

## Overview

FailCore provides cost control features:

- ✅ Budget limits
- ✅ Burn rate limits
- ✅ Multi-level alerts
- ✅ Streaming output monitoring

---

## Basic Usage

### Set Budget Limits

```python
from failcore import run, guard

with run(
    policy="safe",
    max_cost_usd=1.0,  # Maximum $1.00
    max_tokens=10000,  # Maximum 10,000 tokens
) as ctx:
    @guard()
    def call_llm(prompt: str):
        # Call LLM API
        return llm_api.call(prompt)
    
    # If total cost exceeds $1.00, subsequent calls will be blocked
    for prompt in prompts:
        try:
            result = call_llm(prompt)
        except FailCoreError as e:
            if e.error_code == "ECONOMIC_BUDGET_EXCEEDED":
                print("Budget exhausted")
                break
```

### Set Burn Rate Limits

```python
with run(
    policy="safe",
    max_usd_per_minute=0.5,  # Maximum $0.50 per minute
) as ctx:
    @guard()
    def call_llm(prompt: str):
        return llm_api.call(prompt)
    
    # If burn rate exceeds $0.50/minute, calls will be blocked
    for prompt in prompts:
        call_llm(prompt)
```

---

## Budget Types

### Total Cost Budget

Limit total cost for entire run:

```python
with run(max_cost_usd=10.0) as ctx:
    # Total cost cannot exceed $10.00
    pass
```

### Token Budget

Limit total token count:

```python
with run(max_tokens=100000) as ctx:
    # Total tokens cannot exceed 100,000
    pass
```

### API Call Budget

Limit number of API calls:

```python
# Through CostGuardian configuration
from failcore.core.cost import CostGuardian, GuardianConfig

config = GuardianConfig(max_api_calls=1000)
guardian = CostGuardian(config=config)
```

---

## Burn Rate Limits

### Per Minute Limit

```python
with run(max_usd_per_minute=0.5) as ctx:
    # Maximum $0.50 per minute
    pass
```

### Per Hour Limit

```python
from failcore.core.cost import CostGuardian, GuardianConfig

config = GuardianConfig(max_usd_per_hour=10.0)
guardian = CostGuardian(config=config)
```

### Token Rate Limits

```python
config = GuardianConfig(max_tokens_per_minute=10000)
guardian = CostGuardian(config=config)
```

---

## Cost Estimation

FailCore automatically estimates cost for each operation:

```python
from failcore.core.cost import CostEstimator

estimator = CostEstimator()

# Estimate cost
usage = estimator.estimate(
    tool_name="llm_call",
    params={"prompt": "Hello", "max_tokens": 100},
    metadata={"model": "gpt-4"}
)

print(f"Estimated cost: ${usage.cost_usd}")
print(f"Estimated tokens: {usage.total_tokens}")
```

### Supported Models

FailCore supports pricing for common LLM models:

- GPT-4
- GPT-3.5
- Claude
- Others (extensible)

---

## Cost Tracking

### View Costs

```bash
failcore report <run_id> --include-cost
```

Output:
```
Total Cost: $2.45
Total Tokens: 15,234
Average per call: $0.12
```

### Cost Timeline

```bash
failcore show <run_id> --format json | jq '.cost_timeline'
```

---

## Alerts

### Budget Alerts

FailCore triggers alerts at the following thresholds:

- 80% budget usage
- 90% budget usage
- 95% budget usage

### Custom Alerts

```python
from failcore.core.cost import CostGuardian, GuardianConfig, BudgetAlert

def on_alert(alert: BudgetAlert):
    print(f"Alert: {alert.level} - {alert.message}")
    if alert.level == "CRITICAL":
        # Send notification
        send_notification(alert)

config = GuardianConfig(
    max_cost_usd=10.0,
    alert_at_80_percent=True,
    alert_at_90_percent=True,
    alert_at_95_percent=True
)

guardian = CostGuardian(
    config=config,
    on_alert=on_alert
)
```

---

## Streaming Output Monitoring

For streaming output, FailCore monitors token generation in real-time:

```python
from failcore.core.cost import StreamingTokenWatchdog

watchdog = StreamingTokenWatchdog(
    max_tokens=10000,
    check_interval=100  # Check every 100 tokens
)

for chunk in stream:
    tokens = count_tokens(chunk)
    watchdog.on_token_generated(tokens)
    
    if watchdog.would_exceed():
        # Stop streaming output
        break
```

---

## Best Practices

### 1. Set Reasonable Budgets

```python
# Good: Set based on actual needs
with run(max_cost_usd=10.0) as ctx:
    pass

# Bad: Budget too large or too small
with run(max_cost_usd=1000000.0) as ctx:  # Too large
    pass

with run(max_cost_usd=0.01) as ctx:  # Too small
    pass
```

### 2. Monitor Cost Trends

```python
# Regularly check costs
def check_cost(ctx):
    trace = load_trace(ctx.trace_path)
    total_cost = sum(step.get("cost_usd", 0) for step in trace)
    
    if total_cost > 5.0:
        print(f"Warning: Cost exceeded $5.00: ${total_cost}")
```

### 3. Use Alerts

```python
def on_budget_exceeded(reason: str):
    print(f"Budget exhausted: {reason}")
    # Send notification, stop run, etc.

guardian = CostGuardian(
    max_cost_usd=10.0,
    on_budget_exceeded=on_budget_exceeded
)
```

### 4. Test Cost Control

```python
def test_cost_guard():
    with run(max_cost_usd=0.01) as ctx:
        @guard()
        def expensive_call():
            return expensive_api.call()
        
        # Should be blocked quickly
        try:
            for _ in range(100):
                expensive_call()
        except FailCoreError as e:
            if e.error_code == "ECONOMIC_BUDGET_EXCEEDED":
                print("Cost control working correctly")
```

---

## Advanced Configuration

### Dynamic Pricing

```python
from failcore.core.cost import CostGuardian, DynamicPriceEngine

# Use dynamic pricing engine
price_engine = DynamicPriceEngine(enable_api_pricing=True)
guardian = CostGuardian(price_provider=price_engine)
```

### Custom Pricing

```python
from failcore.core.cost.pricing import PriceProvider

class CustomPriceProvider(PriceProvider):
    def get_price(self, model: str, usage_type: str) -> float:
        # Custom pricing logic
        if model == "custom-model":
            return 0.001  # $0.001 per token
        return super().get_price(model, usage_type)

guardian = CostGuardian(price_provider=CustomPriceProvider())
```

---

## Common Questions

### Q: Are cost estimates accurate?

A: Cost estimates are approximations based on model pricing. Actual costs may vary due to discounts, bulk pricing, etc.

### Q: How to disable cost control?

A: Don't set `max_cost_usd`, `max_tokens`, etc. parameters.

### Q: Does cost control affect performance?

A: Cost checks have minimal overhead (< 1ms), negligible impact on performance.

---

## Summary

Cost control features provide:

- ✅ Budget limits
- ✅ Burn rate limits
- ✅ Multi-level alerts
- ✅ Streaming output monitoring

---

## Next Steps

- [Filesystem Safety](fs-safety.md) - Learn about filesystem protection
- [Network Control](network-control.md) - Learn about network security
- [Trace and Replay](../concepts/trace-and-replay.md) - Learn about cost tracking
