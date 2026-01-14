# Deployment Patterns

This guide explains different ways to deploy and use FailCore in production environments.

---

## Overview

FailCore supports two main deployment patterns:

1. **Proxy Mode** - Intercept LLM API calls transparently
2. **Runtime Mode** - Integrate directly into your application code

---

## Proxy Mode (Recommended)

Proxy mode is the recommended approach for production deployments. FailCore runs as a local proxy server that intercepts LLM API requests.

### Architecture

```
[Your Application]
        |
        v
[FailCore Proxy] ← Execution chokepoint
        |
        v
[LLM Provider API]
```

### Benefits

- ✅ **Zero code changes** - Works with any LLM SDK
- ✅ **Transparent interception** - All tool calls automatically traced
- ✅ **Production-ready** - Designed for high-throughput scenarios
- ✅ **Cost control** - Real-time budget enforcement
- ✅ **Streaming protection** - DLP detection during streaming

### Setup

1. **Install proxy dependencies:**

```bash
pip install "failcore[proxy]"
```

2. **Start the proxy server:**

```bash
failcore proxy --listen 127.0.0.1:8000
```

3. **Configure your LLM client:**

```python
# OpenAI SDK example
import openai

client = openai.OpenAI(
    base_url="http://127.0.0.1:8000/v1",  # Route through FailCore
    api_key="your-api-key"
)

# All requests are now protected
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Configuration

Proxy mode supports various configuration options:

```bash
failcore proxy \
    --listen 127.0.0.1:8000 \
    --upstream https://api.openai.com/v1 \
    --mode strict \
    --budget 10.0
```

**Options:**
- `--listen`: Proxy server address (default: 127.0.0.1:8000)
- `--upstream`: Upstream LLM provider URL
- `--mode`: Security mode (`warn` or `strict`)
- `--budget`: Maximum cost in USD

---

## Runtime Mode

Runtime mode integrates FailCore directly into your application code using the `run()` context manager.

### Architecture

```
[Your Application Code]
        |
        v
[FailCore Runtime] ← Policy enforcement
        |
        v
[Tool Execution]
```

### Benefits

- ✅ **Fine-grained control** - Per-run policy configuration
- ✅ **Explicit tool registration** - Clear visibility of protected tools
- ✅ **Flexible integration** - Works with any Python code
- ✅ **Development-friendly** - Easy to test and debug

### Setup

1. **Install FailCore:**

```bash
pip install failcore
```

2. **Use in your code:**

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # Protected execution
    write_file("test.txt", "Hello, FailCore!")
```

### Configuration

Runtime mode supports extensive configuration:

```python
with run(
    policy="fs_safe",
    sandbox="./workspace",
    trace="custom_trace.jsonl",
    strict=True,
    max_cost_usd=5.0,
    max_tokens=10000
) as ctx:
    # Your code here
    pass
```

---

## Hybrid Approach

You can combine both patterns:

- **Proxy mode** for LLM API calls
- **Runtime mode** for custom tool execution

Example:

```python
# Proxy handles LLM calls
# Runtime handles custom tools

from failcore import run, guard

# LLM calls go through proxy (configured separately)
# Custom tools use runtime mode

with run(policy="fs_safe") as ctx:
    @guard()
    def custom_tool(data: str):
        # Custom logic
        pass
    
    custom_tool("data")
```

---

## Production Considerations

### Performance

- **Proxy mode**: Minimal overhead (< 1ms per request)
- **Runtime mode**: Policy checks add < 1ms per tool call

### Scalability

- **Proxy mode**: Can handle high-throughput scenarios
- **Runtime mode**: Suitable for moderate workloads

### Monitoring

Both modes generate trace files for post-mortem analysis:

```bash
# View traces
failcore list

# Generate reports
failcore report trace.jsonl
```

---

## Next Steps

- [Configuration Reference](../reference/configuration.md) - Detailed configuration options
- [Troubleshooting](../operations/troubleshooting.md) - Common issues and solutions
- [Integrations](../integrations/overview.md) - Framework integrations
