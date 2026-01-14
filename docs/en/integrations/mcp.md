# MCP Integration

This guide explains how to use FailCore with Model Context Protocol (MCP).

---

## Overview

FailCore provides comprehensive support for MCP, including:

- ✅ MCP client implementation
- ✅ Policy protection for MCP tools
- ✅ SSRF and network security
- ✅ Cost tracking for remote calls
- ✅ Trace recording for audit

---

## What is MCP?

Model Context Protocol (MCP) is a protocol for LLMs to communicate with external tools and data sources.

MCP enables:
- Remote tool execution
- Secure tool discovery
- Standardized tool interfaces

---

## Basic Usage

### Install MCP Support

```bash
pip install "failcore[mcp]"
```

### Configure MCP Transport

```python
from failcore.infra.transports.mcp import McpTransport, McpTransportConfig
from failcore.infra.transports.mcp.session import McpSessionConfig
from failcore.core.runtime import ToolRuntime
from failcore.core.runtime.middleware import PolicyMiddleware

# Configure MCP session
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    )
)

# Create transport
transport = McpTransport(mcp_config)

# Create tool runtime with policy protection
runtime = ToolRuntime(
    transport=transport,
    middlewares=[
        PolicyMiddleware(policy="fs_safe")  # Apply filesystem safety
    ]
)
```

### List Available Tools

```python
# List tools from MCP server
tools = await runtime.list_tools()

for tool in tools:
    print(f"Tool: {tool.name}")
    print(f"Description: {tool.description}")
```

### Call MCP Tools

```python
from failcore.core.runtime.types import CallContext

# Call tool with policy protection
result = await runtime.call(
    tool=tools[0],
    args={"path": "test.txt"},
    ctx=CallContext(run_id="run-001")
)

print(f"Result: {result.output}")
```

---

## Policy Protection

### Filesystem Tools

MCP filesystem tools automatically apply `fs_safe` policy:

```python
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

# Call filesystem tool (protected)
result = await runtime.call(
    tool=file_tool,
    args={"path": "data.txt"},
    ctx=CallContext(run_id="run-001")
)
```

### Network Tools

MCP network tools can use `net_safe` policy:

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

## Security Features

### SSRF Protection

FailCore automatically protects against SSRF attacks:

```python
# This will be blocked by net_safe policy
result = await runtime.call(
    tool=http_tool,
    args={"url": "http://169.254.169.254/latest/meta-data"},  # Private IP
    ctx=CallContext(run_id="run-001")
)
# ❌ BLOCKED: Private network access
```

### Path Traversal Protection

Filesystem tools are protected against path traversal:

```python
# This will be blocked by fs_safe policy
result = await runtime.call(
    tool=file_tool,
    args={"path": "../../etc/passwd"},  # Path traversal
    ctx=CallContext(run_id="run-001")
)
# ❌ BLOCKED: Path traversal detected
```

---

## Cost Tracking

MCP tool calls are automatically tracked for cost analysis:

```python
# Cost is tracked automatically
result = await runtime.call(
    tool=expensive_tool,
    args={"query": "complex operation"},
    ctx=CallContext(run_id="run-001")
)

# View cost in trace file
# failcore report trace.jsonl
```

---

## Trace Recording

All MCP tool calls are recorded in trace files:

```python
# Traces are automatically recorded
result = await runtime.call(
    tool=tool,
    args={"input": "data"},
    ctx=CallContext(run_id="run-001")
)

# View trace
# failcore show trace.jsonl
```

---

## Advanced Configuration

### Custom MCP Server

```python
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command=["python", "-m", "my_mcp_server", "--config", "config.json"]
    ),
    provider="custom-mcp",
    protocol_version="2024-11-05"
)

transport = McpTransport(mcp_config)
```

### Multiple MCP Servers

```python
# Create multiple transports
transport1 = McpTransport(McpTransportConfig(...))
transport2 = McpTransport(McpTransportConfig(...))

# Use different runtimes for different servers
runtime1 = ToolRuntime(transport=transport1, ...)
runtime2 = ToolRuntime(transport=transport2, ...)
```

---

## Troubleshooting

### Connection Issues

If MCP server fails to start:

```python
# Check server command
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path"]  # Ensure npx is in PATH
    )
)
```

### Policy Blocking Legitimate Calls

Use `shadow` mode to observe without blocking:

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

## Next Steps

- [MCP Protection Guide](../guides/mcp-guard.md) - Detailed protection guide
- [Configuration Reference](../reference/configuration.md) - Configuration options
- [Troubleshooting](../operations/troubleshooting.md) - Common issues
