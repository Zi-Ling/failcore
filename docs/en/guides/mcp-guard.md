# MCP Protection

This guide explains how to use FailCore to protect Model Context Protocol (MCP) tool calls.

---

## Overview

FailCore supports MCP integration, providing:

- ✅ Policy protection for MCP tools
- ✅ Tracing of remote tool calls
- ✅ SSRF and network security
- ✅ Cost control

---

## MCP Introduction

Model Context Protocol (MCP) is a protocol for LLMs to communicate with external tools.

FailCore can act as an MCP client, protecting MCP tool calls.

---

## Basic Usage

### Configure MCP Transport

```python
from failcore.infra.transports.mcp import McpTransport, McpTransportConfig
from failcore.infra.transports.mcp.session import McpSessionConfig
from failcore.core.runtime import ToolRuntime
from failcore.core.runtime.middleware import PolicyMiddleware

# Configure MCP transport
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    )
)

# Create transport
transport = McpTransport(mcp_config)

# Create tool runtime (with policy protection)
runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy="safe")  # Apply policy
    ]
)
```

### Call MCP Tools

```python
# List available tools
tools = await runtime.list_tools()

# Call tool (protected by policy)
result = await runtime.call(
    tool=tools[0],
    args={"path": "test.txt"},
    ctx=CallContext(run_id="abc123")
)
```

---

## Policy Protection

### Filesystem Tools

MCP filesystem tools automatically apply `fs_safe` policy:

```python
from failcore.core.runtime.middleware import PolicyMiddleware
from failcore.core.validate.templates import fs_safe_policy

# Create filesystem safety policy
policy = fs_safe_policy(sandbox_root="./workspace")

# Apply to MCP runtime
runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy=policy)
    ]
)

# Call filesystem tool
result = await runtime.call(
    tool=file_tool,
    args={"path": "data.txt"},  # Within sandbox
    ctx=ctx
)

# This will be blocked (path traversal)
try:
    result = await runtime.call(
        tool=file_tool,
        args={"path": "../../etc/passwd"},  # Path traversal
        ctx=ctx
    )
except FailCoreError:
    print("Path traversal blocked")
```

### Network Tools

MCP network tools automatically apply `net_safe` policy:

```python
from failcore.core.validate.templates import net_safe_policy

# Create network safety policy
policy = net_safe_policy()

runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy=policy)
    ]
)

# Call network tool
result = await runtime.call(
    tool=http_tool,
    args={"url": "https://api.example.com/data"},  # Public URL
    ctx=ctx
)

# This will be blocked (SSRF)
try:
    result = await runtime.call(
        tool=http_tool,
        args={"url": "http://169.254.169.254/latest/meta-data/"},  # SSRF
        ctx=ctx
    )
except FailCoreError:
    print("SSRF blocked")
```

---

## Tracing MCP Calls

All MCP tool calls are recorded to trace files:

```python
from failcore.core.trace.recorder import JsonlTraceRecorder

# Create trace recorder
recorder = JsonlTraceRecorder("mcp_trace.jsonl")

# Use in runtime
runtime = ToolRuntime(
    transport=transport,
    recorder=recorder,
    middlewares=[PolicyMiddleware(policy="safe")]
)

# All calls will be recorded
result = await runtime.call(tool=tool, args={}, ctx=ctx)

# View trace
# failcore show mcp_trace.jsonl
```

---

## Cost Control

MCP tool calls also support cost control:

```python
from failcore.core.cost import CostGuardian, GuardianConfig

# Create cost guardian
guardian = CostGuardian(
    config=GuardianConfig(
        max_cost_usd=10.0,
        max_tokens=100000
    )
)

# Use in runtime
runtime = ToolRuntime(
    transport=transport,
    cost_guardian=guardian,
    middlewares=[PolicyMiddleware(policy="safe")]
)

# If cost exceeds budget, calls will be blocked
try:
    result = await runtime.call(tool=expensive_tool, args={}, ctx=ctx)
except FailCoreError as e:
    if e.error_code == "ECONOMIC_BUDGET_EXCEEDED":
        print("Cost budget exhausted")
```

---

## Error Handling

### Network Errors

MCP transport errors are classified as:

- `NETWORK_ERROR`: Network connection error
- `TIMEOUT`: Request timeout
- `PROTOCOL_ERROR`: Protocol error

```python
try:
    result = await runtime.call(tool=tool, args={}, ctx=ctx)
except FailCoreError as e:
    if e.error_code == "NETWORK_ERROR":
        print(f"Network error: {e.message}")
    elif e.error_code == "TIMEOUT":
        print(f"Request timeout: {e.message}")
```

### Policy Errors

Policy violations return `FailCoreError` exception:

```python
try:
    result = await runtime.call(
        tool=tool,
        args={"path": "../../etc/passwd"},
        ctx=ctx
    )
except FailCoreError as e:
    print(f"Policy denied: {e.message}")
    if e.suggestion:
        print(f"Suggestion: {e.suggestion}")
```

---

## Best Practices

### 1. Always Use Policies

```python
# Good: Apply policy protection
runtime = ToolRuntime(
    transport=transport,
    middlewares=[PolicyMiddleware(policy="safe")]
)

# Bad: No policy protection
runtime = ToolRuntime(transport=transport)
```

### 2. Configure Appropriate Sandbox

```python
# Configure sandbox for filesystem tools
policy = fs_safe_policy(sandbox_root="./mcp_workspace")
runtime = ToolRuntime(
    transport=transport,
    middlewares=[PolicyMiddleware(policy=policy)]
)
```

### 3. Monitor Costs

```python
# Set cost limits
guardian = CostGuardian(config=GuardianConfig(max_cost_usd=10.0))
runtime = ToolRuntime(
    transport=transport,
    cost_guardian=guardian
)
```

### 4. Record Traces

```python
# Enable tracing
recorder = JsonlTraceRecorder("mcp_trace.jsonl")
runtime = ToolRuntime(
    transport=transport,
    recorder=recorder
)
```

---

## Advanced Configuration

### Custom Middleware

```python
from failcore.core.runtime.middleware import Middleware

class CustomMiddleware(Middleware):
    async def on_call_start(self, tool, args, ctx, emit):
        # Custom logic
        print(f"Calling tool: {tool.name}")
        return None
    
    async def on_call_success(self, tool, args, ctx, result, emit):
        # Custom logic
        print(f"Tool succeeded: {tool.name}")
    
    async def on_call_error(self, tool, args, ctx, error, emit):
        # Custom logic
        print(f"Tool failed: {tool.name} - {error}")

runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy="safe"),
        CustomMiddleware()
    ]
)
```

### Retry Logic

```python
from failcore.core.runtime.middleware import RetryMiddleware

runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        RetryMiddleware(max_retries=3, backoff=1.0),
        PolicyMiddleware(policy="safe")
    ]
)
```

---

## Common Questions

### Q: Are MCP tool calls protected by policies?

A: Yes, if using `PolicyMiddleware`, all MCP tool calls are protected by policies.

### Q: How to view traces of MCP calls?

A: Use `JsonlTraceRecorder` to record traces, then use `failcore show` to view.

### Q: Do MCP tool calls count toward costs?

A: Yes, if `CostGuardian` is configured, MCP tool calls also count toward cost budgets.

---

## Summary

MCP protection features provide:

- ✅ Policy protection
- ✅ Trace recording
- ✅ Cost control
- ✅ Error handling

---

## Next Steps

- [Filesystem Safety](fs-safety.md) - Learn about filesystem protection
- [Network Control](network-control.md) - Learn about network security
- [Cost Control](cost-guard.md) - Learn about cost limits
