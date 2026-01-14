# MCP 保护

本指南介绍如何使用 FailCore 保护 Model Context Protocol (MCP) 工具调用。

---

## 概述

FailCore 支持 MCP 集成，提供：

- ✅ MCP 工具的策略保护
- ✅ 远程工具调用的追踪
- ✅ SSRF 和网络安全
- ✅ 成本控制

---

## MCP 简介

Model Context Protocol (MCP) 是一个用于 LLM 与外部工具通信的协议。

FailCore 可以作为 MCP 客户端，保护 MCP 工具调用。

---

## 基本用法

### 配置 MCP 传输

```python
from failcore.adapters.mcp import McpTransport, McpTransportConfig
from failcore.core.tools.runtime import ToolRuntime
from failcore.core.tools.runtime.middleware import PolicyMiddleware

# 配置 MCP 传输
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    )
)

# 创建传输
transport = McpTransport(mcp_config)

# 创建工具运行时（带策略保护）
runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy="safe")  # 应用策略
    ]
)
```

### 调用 MCP 工具

```python
# 列出可用工具
tools = await runtime.list_tools()

# 调用工具（受策略保护）
result = await runtime.call(
    tool=tools[0],
    args={"path": "test.txt"},
    ctx=CallContext(run_id="abc123")
)
```

---

## 策略保护

### 文件系统工具

MCP 文件系统工具自动应用 `fs_safe` 策略：

```python
from failcore.core.tools.runtime.middleware import PolicyMiddleware
from failcore.core.validate.templates import fs_safe_policy

# 创建文件系统安全策略
policy = fs_safe_policy(sandbox_root="./workspace")

# 应用到 MCP 运行时
runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy=policy)
    ]
)

# 调用文件系统工具
result = await runtime.call(
    tool=file_tool,
    args={"path": "data.txt"},  # 在沙箱内
    ctx=ctx
)

# 这会被阻止（路径遍历）
try:
    result = await runtime.call(
        tool=file_tool,
        args={"path": "../../etc/passwd"},  # 路径遍历
        ctx=ctx
    )
except PolicyDeny:
    print("路径遍历被阻止")
```

### 网络工具

MCP 网络工具自动应用 `net_safe` 策略：

```python
from failcore.core.validate.templates import net_safe_policy

# 创建网络安全策略
policy = net_safe_policy()

runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy=policy)
    ]
)

# 调用网络工具
result = await runtime.call(
    tool=http_tool,
    args={"url": "https://api.example.com/data"},  # 公共 URL
    ctx=ctx
)

# 这会被阻止（SSRF）
try:
    result = await runtime.call(
        tool=http_tool,
        args={"url": "http://169.254.169.254/latest/meta-data/"},  # SSRF
        ctx=ctx
    )
except PolicyDeny:
    print("SSRF 被阻止")
```

---

## 追踪 MCP 调用

所有 MCP 工具调用都被记录到追踪文件：

```python
from failcore.core.trace.recorder import JsonlTraceRecorder

# 创建追踪记录器
recorder = JsonlTraceRecorder("mcp_trace.jsonl")

# 在运行时中使用
runtime = ToolRuntime(
    transport=transport,
    recorder=recorder,
    middlewares=[PolicyMiddleware(policy="safe")]
)

# 所有调用都会被记录
result = await runtime.call(tool=tool, args={}, ctx=ctx)

# 查看追踪
# failcore show mcp_trace.jsonl
```

---

## 成本控制

MCP 工具调用也支持成本控制：

```python
from failcore.core.cost import CostGuardian, GuardianConfig

# 创建成本守护者
guardian = CostGuardian(
    config=GuardianConfig(
        max_cost_usd=10.0,
        max_tokens=100000
    )
)

# 在运行时中使用
runtime = ToolRuntime(
    transport=transport,
    cost_guardian=guardian,
    middlewares=[PolicyMiddleware(policy="safe")]
)

# 如果成本超过预算，调用会被阻止
try:
    result = await runtime.call(tool=expensive_tool, args={}, ctx=ctx)
except FailCoreError as e:
    if e.error_code == "ECONOMIC_BUDGET_EXCEEDED":
        print("成本预算已用完")
```

---

## 错误处理

### 网络错误

MCP 传输错误被分类为：

- `NETWORK_ERROR`：网络连接错误
- `TIMEOUT`：请求超时
- `PROTOCOL_ERROR`：协议错误

```python
try:
    result = await runtime.call(tool=tool, args={}, ctx=ctx)
except FailCoreError as e:
    if e.error_code == "NETWORK_ERROR":
        print(f"网络错误: {e.message}")
    elif e.error_code == "TIMEOUT":
        print(f"请求超时: {e.message}")
```

### 策略错误

策略违规返回 `PolicyDeny` 异常：

```python
try:
    result = await runtime.call(
        tool=tool,
        args={"path": "../../etc/passwd"},
        ctx=ctx
    )
except PolicyDeny as e:
    print(f"策略拒绝: {e.result.reason}")
    print(f"建议: {e.result.suggestion}")
```

---

## 最佳实践

### 1. 始终使用策略

```python
# 好：应用策略保护
runtime = ToolRuntime(
    transport=transport,
    middlewares=[PolicyMiddleware(policy="safe")]
)

# 不好：无策略保护
runtime = ToolRuntime(transport=transport)
```

### 2. 配置适当的沙箱

```python
# 为文件系统工具配置沙箱
policy = fs_safe_policy(sandbox_root="./mcp_workspace")
runtime = ToolRuntime(
    transport=transport,
    middlewares=[PolicyMiddleware(policy=policy)]
)
```

### 3. 监控成本

```python
# 设置成本限制
guardian = CostGuardian(config=GuardianConfig(max_cost_usd=10.0))
runtime = ToolRuntime(
    transport=transport,
    cost_guardian=guardian
)
```

### 4. 记录追踪

```python
# 启用追踪
recorder = JsonlTraceRecorder("mcp_trace.jsonl")
runtime = ToolRuntime(
    transport=transport,
    recorder=recorder
)
```

---

## 高级配置

### 自定义中间件

```python
from failcore.core.tools.runtime.middleware import Middleware

class CustomMiddleware(Middleware):
    async def on_call_start(self, tool, args, ctx, emit):
        # 自定义逻辑
        print(f"调用工具: {tool.name}")
        return None
    
    async def on_call_success(self, tool, args, ctx, result, emit):
        # 自定义逻辑
        print(f"工具成功: {tool.name}")
    
    async def on_call_error(self, tool, args, ctx, error, emit):
        # 自定义逻辑
        print(f"工具失败: {tool.name} - {error}")

runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy="safe"),
        CustomMiddleware()
    ]
)
```

### 重试逻辑

```python
from failcore.core.tools.runtime.middleware import RetryMiddleware

runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        RetryMiddleware(max_retries=3, backoff=1.0),
        PolicyMiddleware(policy="safe")
    ]
)
```

---

## 常见问题

### Q: MCP 工具调用是否受策略保护？

A: 是的，如果使用 `PolicyMiddleware`，所有 MCP 工具调用都受策略保护。

### Q: 如何查看 MCP 调用的追踪？

A: 使用 `JsonlTraceRecorder` 记录追踪，然后使用 `failcore show` 查看。

### Q: MCP 工具调用是否计入成本？

A: 是的，如果配置了 `CostGuardian`，MCP 工具调用也会计入成本预算。

---

## 总结

MCP 保护功能提供：

- ✅ 策略保护
- ✅ 追踪记录
- ✅ 成本控制
- ✅ 错误处理

---

## 下一步

- [文件系统安全](fs-safety.md) - 了解文件系统保护
- [网络控制](network-control.md) - 了解网络安全
- [成本控制](cost-guard.md) - 了解成本限制
