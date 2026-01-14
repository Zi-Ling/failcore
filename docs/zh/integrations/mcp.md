# MCP 集成

本指南介绍如何将 FailCore 与 Model Context Protocol (MCP) 一起使用。

---

## 概述

FailCore 为 MCP 提供全面支持，包括：

- ✅ MCP 客户端实现
- ✅ MCP 工具的策略保护
- ✅ SSRF 和网络安全
- ✅ 远程调用的成本追踪
- ✅ 用于审计的追踪记录

---

## 什么是 MCP？

Model Context Protocol (MCP) 是一个用于 LLM 与外部工具和数据源通信的协议。

MCP 支持：
- 远程工具执行
- 安全工具发现
- 标准化工具接口

---

## 基本用法

### 安装 MCP 支持

```bash
pip install "failcore[mcp]"
```

### 配置 MCP 传输

```python
from failcore.adapters.mcp import McpTransport, McpTransportConfig
from failcore.adapters.mcp.session import McpSessionConfig
from failcore.core.tools.runtime import ToolRuntime
from failcore.core.tools.runtime.middleware import PolicyMiddleware

# 配置 MCP 会话
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    )
)

# 创建传输
transport = McpTransport(mcp_config)

# 创建带策略保护的工具运行时
runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy="fs_safe")  # 应用文件系统安全
    ]
)
```

### 列出可用工具

```python
# 从 MCP 服务器列出工具
tools = await runtime.list_tools()

for tool in tools:
    print(f"工具: {tool.name}")
    print(f"描述: {tool.description}")
```

### 调用 MCP 工具

```python
from failcore.core.tools.runtime.types import CallContext

# 使用策略保护调用工具
result = await runtime.call(
    tool=tools[0],
    args={"path": "test.txt"},
    ctx=CallContext(run_id="run-001")
)

print(f"结果: {result.output}")
```

---

## 策略保护

### 文件系统工具

MCP 文件系统工具自动应用 `fs_safe` 策略：

```python
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

# 调用文件系统工具（受保护）
result = await runtime.call(
    tool=file_tool,
    args={"path": "data.txt"},
    ctx=CallContext(run_id="run-001")
)
```

### 网络工具

MCP 网络工具可以使用 `net_safe` 策略：

```python
from failcore.core.validate.templates import net_safe_policy

policy = net_safe_policy()

runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy=policy)
    ]
)
```

---

## 安全功能

### SSRF 保护

FailCore 自动保护免受 SSRF 攻击：

```python
# 这将被 net_safe 策略阻止
result = await runtime.call(
    tool=http_tool,
    args={"url": "http://169.254.169.254/latest/meta-data"},  # 私有 IP
    ctx=CallContext(run_id="run-001")
)
# ❌ 被阻止：私有网络访问
```

### 路径遍历保护

文件系统工具受到路径遍历保护：

```python
# 这将被 fs_safe 策略阻止
result = await runtime.call(
    tool=file_tool,
    args={"path": "../../etc/passwd"},  # 路径遍历
    ctx=CallContext(run_id="run-001")
)
# ❌ 被阻止：检测到路径遍历
```

---

## 成本追踪

MCP 工具调用自动追踪用于成本分析：

```python
# 成本自动追踪
result = await runtime.call(
    tool=expensive_tool,
    args={"query": "复杂操作"},
    ctx=CallContext(run_id="run-001")
)

# 在追踪文件中查看成本
# failcore report trace.jsonl
```

---

## 追踪记录

所有 MCP 工具调用都记录在追踪文件中：

```python
# 追踪自动记录
result = await runtime.call(
    tool=tool,
    args={"input": "data"},
    ctx=CallContext(run_id="run-001")
)

# 查看追踪
# failcore show trace.jsonl
```

---

## 高级配置

### 自定义 MCP 服务器

```python
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command="python",
        args=["-m", "my_mcp_server", "--config", "config.json"]
    ),
    provider="custom-mcp",
    protocol_version="2024-11-05"
)

transport = McpTransport(mcp_config)
```

### 多个 MCP 服务器

```python
# 创建多个传输
transport1 = McpTransport(McpTransportConfig(...))
transport2 = McpTransport(McpTransportConfig(...))

# 为不同服务器使用不同的运行时
runtime1 = ToolRuntime(transport=transport1, ...)
runtime2 = ToolRuntime(transport=transport2, ...)
```

---

## 故障排除

### 连接问题

如果 MCP 服务器无法启动：

```python
# 检查服务器命令
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command="npx",  # 确保命令在 PATH 中
        args=["-y", "@modelcontextprotocol/server-filesystem", "/path"]
    )
)
```

### 策略阻止合法调用

使用 `shadow` 模式观察而不阻止：

```python
from failcore.core.validate.templates import shadow_policy

runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy=shadow_policy())
    ]
)
```

---

## 下一步

- [MCP 保护指南](../guides/mcp-guard.md) - 详细保护指南
- [配置参考](../reference/configuration.md) - 配置选项
- [故障排除](../operations/troubleshooting.md) - 常见问题
