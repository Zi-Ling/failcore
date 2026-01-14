# LangChain Integration

This guide explains how to use FailCore with LangChain tools and agents.

---

## Overview

FailCore provides seamless integration with LangChain:

- ✅ Automatic LangChain tool detection
- ✅ BaseTool compatibility for agents
- ✅ Full async support
- ✅ Parameter schema preservation
- ✅ Zero breaking changes

---

## Installation

Install LangChain support:

```bash
pip install "failcore[langchain]"
```

This installs:
- `langchain-core` (>=0.3.0, <2.0.0)

---

## Basic Usage

### Method 1: Auto-Detection (Recommended)

FailCore automatically detects LangChain tools:

```python
from failcore import run, guard
from langchain_core.tools import tool

@tool
def multiply(x: int) -> int:
    """Multiply by 2"""
    return x * 2

# guard() automatically detects LangChain tool
with run(policy="safe") as ctx:
    safe_tool = guard(multiply, risk="low", effect="read")
    result = safe_tool(x=5)  # ✅ Protected execution
```

### Method 2: Agent Compatibility

For LangChain agents, use `guard_tool()`:

```python
from failcore import run, guard
from failcore.adapters.langchain import guard_tool
from langchain_core.tools import tool

@tool
def write_file(path: str, content: str) -> str:
    """Write content to file"""
    with open(path, "w") as f:
        f.write(content)
    return f"Wrote to {path}"

with run(policy="fs_safe", sandbox="./data") as ctx:
    # Register tool first
    guard(write_file, risk="high", effect="fs")
    
    # Create BaseTool facade for Agent
    lc_tool = guard_tool("write_file", description="Write files safely")
    
    # Use with LangChain agent
    from langchain.agents import create_agent
    agent = create_agent(tools=[lc_tool])
    result = agent.invoke({"input": "Write hello to test.txt"})
```

---

## Advanced Usage

### Custom Tool Registration

You can register tools explicitly:

```python
from failcore import run, guard
from failcore.adapters.langchain import map_langchain_tool

@tool
def my_tool(x: int) -> int:
    """My tool"""
    return x * 2

with run(policy="safe") as ctx:
    # Map LangChain tool to ToolSpec
    spec = map_langchain_tool(
        my_tool,
        risk="low",
        effect="read"
    )
    
    # Register and use
    ctx.tool(spec)
    result = ctx.call("my_tool", x=5)
```

### Async Support

FailCore fully supports async LangChain tools:

```python
from failcore import run, guard
from langchain_core.tools import tool

@tool
async def async_tool(data: str) -> str:
    """Async tool"""
    await asyncio.sleep(0.1)
    return f"Processed: {data}"

async def main():
    with run(policy="safe") as ctx:
        safe_tool = guard(async_tool, risk="low")
        result = await safe_tool(data="test")  # ✅ Async works
```

---

## Agent Integration

### Creating Protected Agents

```python
from failcore import run, guard
from failcore.adapters.langchain import guard_tool
from langchain.agents import create_agent

@tool
def read_file(path: str) -> str:
    """Read file content"""
    with open(path, "r") as f:
        return f.read()

@tool
def write_file(path: str, content: str) -> str:
    """Write content to file"""
    with open(path, "w") as f:
        f.write(content)
    return "Written"

with run(policy="fs_safe", sandbox="./workspace") as ctx:
    # Register tools
    guard(read_file, risk="low", effect="read")
    guard(write_file, risk="high", effect="fs")
    
    # Create BaseTool facades
    tools = [
        guard_tool("read_file", description="Read files"),
        guard_tool("write_file", description="Write files")
    ]
    
    # Create agent with protected tools
    agent = create_agent(tools=tools)
    
    # Agent calls are automatically protected
    result = agent.invoke({
        "input": "Read config.txt and write backup.txt"
    })
```

### Tool Schema Preservation

When creating `guard_tool()` inside `run()`, parameter schemas are preserved:

```python
with run(policy="fs_safe") as ctx:
    guard(write_file, risk="high", effect="fs")
    
    # ✅ Full schema support (recommended)
    lc_tool = guard_tool("write_file", description="Write files")
    # LangChain can see parameter types and validate inputs
```

If created outside `run()`, schemas may be limited:

```python
# ⚠️ Limited schema support
lc_tool = guard_tool("write_file", description="Write files")

with run(policy="fs_safe") as ctx:
    guard(write_file, risk="high", effect="fs")
    # Tool works but AI agents can't see parameter types
```

**Best Practice:** Always create `guard_tool()` inside `run()` after `guard()` registration.

---

## Policy Configuration

### Per-Tool Policies

You can specify policies per tool:

```python
with run(policy="safe") as ctx:
    # Low-risk tool
    read_tool = guard(read_file, risk="low", effect="read")
    
    # High-risk tool with strict policy
    write_tool = guard(
        write_file,
        risk="high",
        effect="fs",
        action="block"  # Strict blocking
    )
```

### Context-Level Policies

Policies apply to all tools in a context:

```python
# All tools in this context use fs_safe policy
with run(policy="fs_safe", sandbox="./data") as ctx:
    guard(read_file)
    guard(write_file)
    # Both protected by fs_safe
```

---

## Error Handling

FailCore errors are compatible with LangChain:

```python
from failcore import run, guard
from failcore.core.errors import FailCoreError

@tool
def risky_tool(path: str) -> str:
    """Risky operation"""
    pass

try:
    with run(policy="fs_safe", strict=True) as ctx:
        safe_tool = guard(risky_tool, risk="high")
        result = safe_tool(path="/etc/passwd")  # May be blocked
except FailCoreError as e:
    print(f"Blocked: {e}")
```

---

## Best Practices

### 1. Register Tools First

Always register tools with `guard()` before creating `guard_tool()`:

```python
# ✅ Correct
with run(policy="fs_safe") as ctx:
    guard(write_file)  # Register first
    lc_tool = guard_tool("write_file")  # Then create facade
```

### 2. Use Appropriate Policies

Match policies to tool risk levels:

```python
# Low-risk: read operations
guard(read_file, risk="low", effect="read")

# High-risk: write operations
guard(write_file, risk="high", effect="fs", action="block")
```

### 3. Preserve Schemas

Create `guard_tool()` inside `run()` for full schema support:

```python
# ✅ Recommended
with run(policy="fs_safe") as ctx:
    guard(write_file)
    lc_tool = guard_tool("write_file")  # Full schema
```

---

## Troubleshooting

### Tool Not Detected

If LangChain tool is not auto-detected:

```python
# Explicitly map tool
from failcore.adapters.langchain import map_langchain_tool

spec = map_langchain_tool(my_tool, risk="low")
ctx.tool(spec)
```

### Schema Issues

If parameter schemas are missing:

```python
# Create guard_tool() inside run() context
with run(policy="safe") as ctx:
    guard(my_tool)
    lc_tool = guard_tool("my_tool")  # ✅ Schema preserved
```

---

## Next Steps

- [Integrations Overview](overview.md) - Other integrations
- [Configuration Reference](../reference/configuration.md) - Configuration options
- [Policy Guide](../concepts/policy.md) - Policy configuration
