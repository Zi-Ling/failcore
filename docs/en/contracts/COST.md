# Cost Tracking & Budget Enforcement

FailCore provides comprehensive cost tracking and budget enforcement for LLM agent executions, helping you control spending and prevent unexpected costs.

## Overview

FailCore's cost tracking system includes:

- **Token Counting**: Automatic extraction of input/output tokens from tool responses
- **Cost Calculation**: Dynamic pricing based on model and provider
- **Budget Enforcement**: Real-time budget limits and burn rate controls
- **Streaming Support**: Real-time token monitoring during streaming responses
- **Storage & Analytics**: SQLite persistence for cost analysis

---

## Core Concepts

### CostUsage

The fundamental data model for cost tracking:

```python
from failcore.core.cost import CostUsage

usage = CostUsage(
    run_id="run-001",
    step_id="step-001",
    tool_name="llm_call",
    model="gpt-4",
    provider="openai",
    input_tokens=100,
    output_tokens=50,
    total_tokens=150,
    cost_usd=0.006,
    estimated=False,  # True if estimated, False if from actual API response
    api_calls=1,
)
```

**Fields:**
- `input_tokens`: Input/prompt tokens
- `output_tokens`: Output/completion tokens
- `total_tokens`: Total tokens (auto-calculated if not provided)
- `cost_usd`: Cost in USD
- `estimated`: Whether this is an estimate or actual usage
- `model` / `provider`: Model and provider identification

### Budget

Budget defines spending limits:

```python
from failcore.core.cost import Budget

budget = Budget(
    max_cost_usd=10.0,      # Maximum total cost
    max_tokens=100000,       # Maximum total tokens
    max_api_calls=1000,      # Maximum API calls
    max_usd_per_minute=1.0,  # Burn rate limit
)
```

**Limits:**
- `max_cost_usd`: Total cost limit (USD)
- `max_tokens`: Total token limit
- `max_api_calls`: Total API call limit
- `max_usd_per_minute`: Burn rate (spending velocity) limit

---

## Token Extraction

FailCore automatically extracts token counts from tool return values.

### Supported Formats

**1. Dict with "usage" key:**
```python
def llm_call(prompt: str):
    return {
        "result": "Generated text...",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "cost_usd": 0.006,
            "model": "gpt-4",
            "provider": "openai",
        }
    }
```

**2. Object with .usage attribute:**
```python
class LLMResponse:
    def __init__(self):
        self.result = "Generated text..."
        self.usage = type('obj', (object,), {
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'total_tokens': 150,
        })()
```

**3. OpenAI-style response:**
```python
# response.usage.prompt_tokens
# response.usage.completion_tokens
# response.usage.total_tokens
```

**4. Anthropic-style response:**
```python
# response.usage.input_tokens
# response.usage.output_tokens
```

### Automatic Mapping

FailCore automatically maps different naming conventions:
- `prompt_tokens` → `input_tokens`
- `completion_tokens` → `output_tokens`
- `input_tokens` + `output_tokens` → `total_tokens` (if not provided)

---

## Cost Calculation

### Dynamic Pricing

FailCore supports multiple pricing sources:

**1. Static Pricing (Default):**
```python
from failcore.core.cost import StaticPriceProvider

provider = StaticPriceProvider({
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4o": {"input": 0.005, "output": 0.015},
})
```

**2. Environment Variables:**
```python
from failcore.core.cost import EnvPriceProvider

# Reads from environment:
# FAILCORE_PRICE_gpt-4_INPUT=0.03
# FAILCORE_PRICE_gpt-4_OUTPUT=0.06
provider = EnvPriceProvider()
```

**3. JSON File:**
```python
from failcore.core.cost import JsonPriceProvider

provider = JsonPriceProvider("prices.json")
```

**4. API Endpoint:**
```python
from failcore.core.cost import ApiPriceProvider

provider = ApiPriceProvider(
    endpoint="https://api.example.com/prices",
    cache_ttl=3600,  # Cache for 1 hour
)
```

**5. Chained Provider (Priority Order):**
```python
from failcore.core.cost import ChainedPriceProvider

provider = ChainedPriceProvider([
    ApiPriceProvider(...),    # First: Try API
    JsonPriceProvider(...),   # Second: Fallback to JSON
    StaticPriceProvider(...), # Third: Fallback to static
])
```

### Cost Formula

```python
cost_usd = (input_tokens / 1000.0) * input_price + (output_tokens / 1000.0) * output_price
```

---

## Budget Enforcement

### CostGuardian

Unified global protection manager:

```python
from failcore.core.cost import CostGuardian

guardian = CostGuardian(
    max_cost_usd=10.0,
    max_tokens=100000,
    max_usd_per_minute=1.0,  # Burn rate limit
)
```

**Features:**
- Budget limits (cost, tokens, API calls)
- Burn rate limiting (spending velocity)
- Multi-level alerts (80%/90%/95%)
- Streaming token watchdog

### Budget Checks

**Pre-execution (CostPrecheckStage):**
```python
# Before tool execution
allowed, reason, error_code = guardian.check_operation(usage, raise_on_exceed=False)

if not allowed:
    # Block execution
    return StepResult(status=StepStatus.BLOCKED, error_code=error_code)
```

**Post-execution (CostFinalizeStage):**
```python
# After tool execution
guardian.record_usage(actual_usage)
```

### Error Codes

- `ECONOMIC_BUDGET_EXCEEDED`: Total budget exceeded
- `ECONOMIC_TOKEN_LIMIT`: Token limit exceeded
- `ECONOMIC_BURN_RATE_EXCEEDED`: Burn rate exceeded
- `ECONOMIC_API_CALL_LIMIT`: API call limit exceeded

---

## Streaming Support

### StreamingTokenWatchdog

Real-time token monitoring during streaming:

```python
from failcore.core.cost import StreamingTokenWatchdog

watchdog = StreamingTokenWatchdog(
    budget=budget,
    check_interval=100,  # Check every 100 tokens
    safety_margin=0.95,  # Stop at 95% of budget
)

for chunk in stream:
    tokens = count_tokens(chunk)
    watchdog.on_token_generated(tokens)  # May raise if over budget
```

**Features:**
- Real-time token counting
- Budget enforcement during generation
- Automatic interruption when limit approached
- Thread-safe for concurrent streams

### StreamingCostGuard

High-level streaming guard:

```python
from failcore.core.cost import StreamingCostGuard

guard = StreamingCostGuard(
    max_cost_usd=1.0,
    max_tokens=5000,
    model="gpt-4",
)

for chunk in stream:
    guard.on_chunk(chunk, token_counter=count_tokens)

total_tokens = guard.get_total_tokens()
```

---

## Cost Metrics in Trace Events

Cost information is automatically included in `STEP_END` events:

```json
{
  "event": {
    "type": "STEP_END",
    "data": {
      "metrics": {
        "cost": {
          "incremental": {
            "cost_usd": 0.006,
            "tokens": 150,
            "input_tokens": 100,
            "output_tokens": 50,
            "api_calls": 1,
            "estimated": false,
            "pricing_ref": "openai:gpt-4"
          },
          "cumulative": {
            "cost_usd": 0.012,
            "tokens": 300,
            "api_calls": 2
          }
        }
      }
    }
  }
}
```

**Incremental**: Cost for this step only  
**Cumulative**: Total cost for the run so far

---

## Storage & Analytics

### SQLite Storage

Cost data is automatically persisted to SQLite:

```python
from failcore.infra.storage.cost import CostStorage

storage = CostStorage()

# Query usage by run
usage = storage.get_run_usage("run-001")

# Query usage by tool
tool_usage = storage.get_tool_usage("llm_call", limit=10)

# Query cost trends
trends = storage.get_cost_trends(days=7)
```

**Tables:**
- `cost_usage`: Step-level usage records
- `cost_runs`: Run-level summaries

### CostRecorder

Automatic recording during execution:

```python
from failcore.core.cost.execution import CostRecorder

recorder = CostRecorder(storage=storage)

# Automatically called by Executor
recorder.record_step(
    run_id="run-001",
    step_id="step-001",
    seq=1,
    tool="llm_call",
    usage=cost_usage,
    metrics=metrics,
    status="OK",
    started_at="2024-01-01T00:00:00Z",
    duration_ms=1000,
)
```

---

## Usage Examples

### Basic Cost Tracking

```python
from failcore import run
from failcore.core.cost import CostGuardian

# Enable cost tracking with budget
with run(
    max_cost_usd=10.0,
    max_tokens=100000,
) as ctx:
    # Tool calls are automatically tracked
    result = ctx.call("llm_generate", prompt="Hello")
    
    # Check current cost
    cost = ctx.cost_storage.get_run_usage(ctx.run_id)
    print(f"Total cost: ${cost['total_cost_usd']:.4f}")
    print(f"Total tokens: {cost['total_tokens']}")
```

### Burn Rate Limiting

```python
from failcore import run

# Limit spending velocity
with run(
    max_cost_usd=100.0,
    max_usd_per_minute=1.0,  # Max $1 per minute
) as ctx:
    # Multiple rapid calls will be blocked if burn rate exceeded
    for i in range(10):
        ctx.call("expensive_tool", x=i)
```

### Streaming Cost Control

```python
from failcore.core.cost import StreamingCostGuard

guard = StreamingCostGuard(
    max_cost_usd=1.0,
    max_tokens=5000,
    model="gpt-4",
)

def stream_llm(prompt: str):
    for chunk in llm_stream(prompt):
        guard.on_chunk(chunk)  # May raise if over budget
        yield chunk

total = guard.get_total_tokens()
print(f"Generated {total} tokens")
```

### Custom Token Extraction

```python
from failcore.core.cost import UsageExtractor

extractor = UsageExtractor()

# Extract from custom format
usage = extractor.extract(
    tool_output={
        "result": "...",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
        }
    },
    run_id="run-001",
    step_id="step-001",
    tool_name="custom_llm",
)

print(f"Tokens: {usage.total_tokens}")
```

---

## Cost Estimation

### CostEstimator

Estimate costs before execution:

```python
from failcore.core.cost import CostEstimator

estimator = CostEstimator()

# Estimate based on params
estimated = estimator.estimate(
    tool_name="llm_call",
    params={"prompt": "Hello world"},
    metadata={"model": "gpt-4"},
)

print(f"Estimated cost: ${estimated.cost_usd:.4f}")
print(f"Estimated tokens: {estimated.total_tokens}")
```

**Estimation Methods:**
- Character-based heuristic (~4 chars per token)
- Metadata hints (if provided)
- Model-specific defaults

---

## Best Practices

### 1. Always Set Budgets

```python
# Good: Explicit budget limits
with run(max_cost_usd=10.0, max_tokens=100000) as ctx:
    ...

# Bad: No limits (unbounded spending)
with run() as ctx:
    ...
```

### 2. Use Burn Rate Limits

```python
# Prevent rapid spending spikes
with run(
    max_cost_usd=100.0,
    max_usd_per_minute=1.0,  # Smooth spending
) as ctx:
    ...
```

### 3. Monitor Streaming

```python
# Always use watchdog for streaming
watchdog = StreamingTokenWatchdog(budget, check_interval=50)

for chunk in stream:
    watchdog.on_token_generated(count_tokens(chunk))
```

### 4. Extract Actual Usage

```python
# Return usage in tool response
def llm_call(prompt: str):
    response = openai.chat.completions.create(...)
    return {
        "result": response.choices[0].message.content,
        "usage": {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    }
```

### 5. Use Dynamic Pricing

```python
# Keep prices up-to-date
provider = ChainedPriceProvider([
    ApiPriceProvider(endpoint="...", cache_ttl=3600),
    StaticPriceProvider(fallback_prices),
])
```

---

## API Reference

### CostRunAccumulator

In-memory accumulator for run-level cost tracking:

```python
from failcore.core.cost.execution import CostRunAccumulator

accumulator = CostRunAccumulator()
accumulator.add_usage(run_id, usage, commit=True)
cumulative = accumulator.get_cumulative(run_id)
```

### CostRecorder

Storage writer for persisting cost data:

```python
from failcore.core.cost.execution import CostRecorder

recorder = CostRecorder(storage=storage)
recorder.record_step(...)
recorder.record_run_summary(...)
```

### build_cost_metrics

Build cost metrics dict for trace events:

```python
from failcore.core.cost.execution import build_cost_metrics

metrics = build_cost_metrics(
    run_id="run-001",
    usage=cost_usage,
    accumulator=accumulator,
    commit=True,
)
```

---

## Troubleshooting

### Tokens Not Extracted

**Problem**: Token counts are 0 or missing

**Solutions:**
1. Ensure tool returns usage in supported format
2. Check `UsageExtractor.extract()` return value
3. Verify tool response structure matches expected format

### Cost Not Calculated

**Problem**: `cost_usd` is 0.0

**Solutions:**
1. Check pricing provider configuration
2. Verify model/provider identification
3. Ensure pricing data is available

### Budget Not Enforced

**Problem**: Spending exceeds budget limits

**Solutions:**
1. Verify `CostGuardian` is initialized
2. Check `CostPrecheckStage` is in execution pipeline
3. Ensure `guard_config` is passed to Executor

### Streaming Over Budget

**Problem**: Streaming continues after budget exceeded

**Solutions:**
1. Use `StreamingTokenWatchdog` with appropriate `check_interval`
2. Verify `safety_margin` is set correctly
3. Check that `on_token_generated()` is called for each chunk

---

## Related Documentation

- [FailCore README](../../README.md)
- [Trace Format](trace-spec-v0.1.2.md)
