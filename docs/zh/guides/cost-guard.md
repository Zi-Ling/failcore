# 成本控制

本指南介绍如何使用 FailCore 控制 AI agent 的成本。

---

## 概述

FailCore 提供成本控制功能：

- ✅ 预算限制
- ✅ 燃烧率限制
- ✅ 多级警报
- ✅ 流式输出监控

---

## 基本用法

### 设置预算限制

```python
from failcore import run, guard

with run(
    policy="safe",
    max_cost_usd=1.0,  # 最大 $1.00
    max_tokens=10000,  # 最大 10,000 tokens
) as ctx:
    @guard()
    def call_llm(prompt: str):
        # 调用 LLM API
        return llm_api.call(prompt)
    
    # 如果总成本超过 $1.00，后续调用会被阻止
    for prompt in prompts:
        try:
            result = call_llm(prompt)
        except FailCoreError as e:
            if e.error_code == "ECONOMIC_BUDGET_EXCEEDED":
                print("预算已用完")
                break
```

### 设置燃烧率限制

```python
with run(
    policy="safe",
    max_usd_per_minute=0.5,  # 每分钟最多 $0.50
) as ctx:
    @guard()
    def call_llm(prompt: str):
        return llm_api.call(prompt)
    
    # 如果燃烧率超过 $0.50/分钟，调用会被阻止
    for prompt in prompts:
        call_llm(prompt)
```

---

## 预算类型

### 总成本预算

限制整个运行的总成本：

```python
with run(max_cost_usd=10.0) as ctx:
    # 总成本不能超过 $10.00
    pass
```

### Token 预算

限制总 token 数：

```python
with run(max_tokens=100000) as ctx:
    # 总 tokens 不能超过 100,000
    pass
```

### API 调用预算

限制 API 调用次数：

```python
# 通过 CostGuardian 配置
from failcore.core.cost import CostGuardian, GuardianConfig

config = GuardianConfig(max_api_calls=1000)
guardian = CostGuardian(config=config)
```

---

## 燃烧率限制

### 每分钟限制

```python
with run(max_usd_per_minute=0.5) as ctx:
    # 每分钟最多花费 $0.50
    pass
```

### 每小时限制

```python
from failcore.core.cost import CostGuardian, GuardianConfig

config = GuardianConfig(max_usd_per_hour=10.0)
guardian = CostGuardian(config=config)
```

### Token 速率限制

```python
config = GuardianConfig(max_tokens_per_minute=10000)
guardian = CostGuardian(config=config)
```

---

## 成本估算

FailCore 自动估算每次操作的成本：

```python
from failcore.core.cost import CostEstimator

estimator = CostEstimator()

# 估算成本
usage = estimator.estimate(
    tool_name="llm_call",
    params={"prompt": "Hello", "max_tokens": 100},
    metadata={"model": "gpt-4"}
)

print(f"估算成本: ${usage.cost_usd}")
print(f"估算 tokens: {usage.total_tokens}")
```

### 支持的模型

FailCore 支持常见 LLM 模型的定价：

- GPT-4
- GPT-3.5
- Claude
- 其他（可扩展）

---

## 成本追踪

### 查看成本

```bash
failcore report <run_id> --include-cost
```

输出：
```
总成本: $2.45
总 Tokens: 15,234
平均每次调用: $0.12
```

### 成本时间线

```bash
failcore show <run_id> --format json | jq '.cost_timeline'
```

---

## 警报

### 预算警报

FailCore 在以下阈值触发警报：

- 80% 预算使用
- 90% 预算使用
- 95% 预算使用

### 自定义警报

```python
from failcore.core.cost import CostGuardian, GuardianConfig, BudgetAlert

def on_alert(alert: BudgetAlert):
    print(f"警报: {alert.level} - {alert.message}")
    if alert.level == "CRITICAL":
        # 发送通知
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

## 流式输出监控

对于流式输出，FailCore 实时监控 token 生成：

```python
from failcore.core.cost import StreamingTokenWatchdog

watchdog = StreamingTokenWatchdog(
    max_tokens=10000,
    check_interval=100  # 每 100 tokens 检查一次
)

for chunk in stream:
    tokens = count_tokens(chunk)
    watchdog.on_token_generated(tokens)
    
    if watchdog.would_exceed():
        # 停止流式输出
        break
```

---

## 最佳实践

### 1. 设置合理的预算

```python
# 好：根据实际需求设置
with run(max_cost_usd=10.0) as ctx:
    pass

# 不好：预算过大或过小
with run(max_cost_usd=1000000.0) as ctx:  # 太大
    pass

with run(max_cost_usd=0.01) as ctx:  # 太小
    pass
```

### 2. 监控成本趋势

```python
# 定期检查成本
import json

def check_cost(ctx):
    events = []
    with open(ctx.trace_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    total_cost = sum(e.get("cost_usd", 0) for e in events if "cost_usd" in e)
    
    if total_cost > 5.0:
        print(f"警告: 成本已超过 $5.00: ${total_cost}")
```

### 3. 使用警报

```python
def on_budget_exceeded(reason: str):
    print(f"预算已用完: {reason}")
    # 发送通知、停止运行等

guardian = CostGuardian(
    max_cost_usd=10.0,
    on_budget_exceeded=on_budget_exceeded
)
```

### 4. 测试成本控制

```python
def test_cost_guard():
    with run(max_cost_usd=0.01) as ctx:
        @guard()
        def expensive_call():
            return expensive_api.call()
        
        # 应该很快被阻止
        try:
            for _ in range(100):
                expensive_call()
        except FailCoreError as e:
            if e.error_code == "ECONOMIC_BUDGET_EXCEEDED":
                print("成本控制正常工作")
```

---

## 高级配置

### 动态定价

```python
from failcore.core.cost import CostGuardian, DynamicPriceEngine

# 使用动态定价引擎
price_engine = DynamicPriceEngine(enable_api_pricing=True)
guardian = CostGuardian(price_provider=price_engine)
```

### 自定义定价

```python
from failcore.core.cost.pricing import PriceProvider

class CustomPriceProvider(PriceProvider):
    def get_price(self, model: str, usage_type: str) -> float:
        # 自定义定价逻辑
        if model == "custom-model":
            return 0.001  # $0.001 per token
        return super().get_price(model, usage_type)

guardian = CostGuardian(price_provider=CustomPriceProvider())
```

---

## 常见问题

### Q: 成本估算准确吗？

A: 成本估算是基于模型定价的近似值。实际成本可能因折扣、批量定价等因素而有所不同。

### Q: 如何禁用成本控制？

A: 不设置 `max_cost_usd`、`max_tokens` 等参数即可。

### Q: 成本控制会影响性能吗？

A: 成本检查的开销很小（< 1ms），对性能影响可以忽略不计。

---

## 总结

成本控制功能提供：

- ✅ 预算限制
- ✅ 燃烧率限制
- ✅ 多级警报
- ✅ 流式输出监控

---

## 下一步

- [文件系统安全](fs-safety.md) - 了解文件系统保护
- [网络控制](network-control.md) - 了解网络安全
- [追踪和重放](../concepts/trace-and-replay.md) - 了解成本追踪
