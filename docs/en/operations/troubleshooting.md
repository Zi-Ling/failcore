# Troubleshooting

Common issues and solutions when using FailCore.

---

## Installation Issues

### Import Errors

**Problem:** `ImportError: cannot import name 'run' from 'failcore'`

**Solution:**

```bash
# Reinstall FailCore
pip install --upgrade failcore
```

### Missing Dependencies

**Problem:** `ModuleNotFoundError: No module named 'langchain_core'`

**Solution:**

```bash
# Install required dependencies
pip install "failcore[langchain]"
```

---

## Runtime Issues

### Policy Not Found

**Problem:** `ValueError: Failed to load policy 'custom'`

**Solution:**

1. Check policy file exists: `.failcore/validate/custom.yaml`
2. Verify YAML syntax is correct
3. Check policy name matches file name

```python
# List available policies
from failcore.core.validate.templates import list_policies
print(list_policies())
```

### Path Resolution Errors

**Problem:** `PathError: Path outside allowed roots`

**Solution:**

```python
# Allow external paths with whitelist
from pathlib import Path

with run(
    sandbox="/tmp/external",
    allow_outside_root=True,
    allowed_sandbox_roots=[Path("/tmp")]
) as ctx:
    pass
```

### Tool Not Registered

**Problem:** `ToolNotFoundError: Tool 'my_tool' not found`

**Solution:**

```python
# Register tool before calling
with run(policy="safe") as ctx:
    ctx.tool(my_tool)  # Register first
    ctx.call("my_tool", arg=123)  # Then call
```

Or use `@guard()` decorator:

```python
with run(policy="safe") as ctx:
    @guard()
    def my_tool(arg: int):
        pass
    
    my_tool(123)  # Automatically registered
```

---

## Policy Issues

### Too Restrictive

**Problem:** Legitimate operations are blocked

**Solution:**

1. Use `shadow` mode to observe:

```python
with run(policy="shadow") as ctx:
    # Records decisions but doesn't block
    pass
```

2. Adjust validator actions:

```yaml
# .failcore/validate/custom.yaml
validators:
  - name: security_path_traversal
    action: WARN  # Warn instead of block
```

### Not Restrictive Enough

**Problem:** Unsafe operations are allowed

**Solution:**

1. Use `strict` mode:

```python
with run(policy="fs_safe", strict=True) as ctx:
    pass
```

2. Set validators to `BLOCK`:

```yaml
validators:
  - name: security_path_traversal
    action: BLOCK  # Block instead of warn
```

---

## Proxy Issues

### Connection Refused

**Problem:** `ConnectionRefusedError: [Errno 111] Connection refused`

**Solution:**

1. Check proxy is running:

```bash
failcore proxy --listen 127.0.0.1:8000
```

2. Verify client configuration:

```python
client = openai.OpenAI(
    base_url="http://127.0.0.1:8000/v1",  # Correct URL
    api_key="your-key"
)
```

### Upstream Timeout

**Problem:** Requests timeout to upstream provider

**Solution:**

Increase timeout in proxy config:

```python
from failcore.core.config.proxy import ProxyConfig

config = ProxyConfig(
    upstream_timeout_s=120.0  # Increase timeout
)
```

---

## Integration Issues

### LangChain Tool Not Detected

**Problem:** LangChain tool not auto-detected

**Solution:**

Explicitly map tool:

```python
from failcore.adapters.langchain import map_langchain_tool

with run(policy="safe") as ctx:
    spec = map_langchain_tool(lc_tool, risk="low")
    ctx.tool(spec)
```

### MCP Server Not Starting

**Problem:** MCP transport fails to connect

**Solution:**

1. Check server command is in PATH:

```python
mcp_config = McpTransportConfig(
    session=McpSessionConfig(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path"]  # Verify npx is in PATH
    )
)
```

2. Check server logs for errors

---

## Performance Issues

### Slow Execution

**Problem:** Policy checks add significant overhead

**Solution:**

1. Policy checks are typically < 1ms
2. If slow, check for:
   - Large policy files
   - Complex validator logic
   - Network calls in validators

### Memory Usage

**Problem:** High memory usage

**Solution:**

1. Limit trace file size:

```python
with run(trace=None) as ctx:  # Disable tracing
    pass
```

2. Reduce trace queue size (proxy mode):

```python
config = ProxyConfig(
    trace_queue_size=1000  # Reduce queue size
)
```

---

## Trace Issues

### Trace File Not Found

**Problem:** `FileNotFoundError: trace.jsonl`

**Solution:**

1. Check trace path:

```python
with run(trace="auto") as ctx:
    print(ctx.trace_path)  # Verify path
```

2. Use absolute path:

```python
with run(trace="/path/to/trace.jsonl") as ctx:
    pass
```

### Trace File Corrupted

**Problem:** Invalid JSON in trace file

**Solution:**

1. Trace files use JSONL format (one JSON object per line)
2. Check file encoding (should be UTF-8)
3. Validate JSON syntax:

```bash
# Check trace file
failcore show trace.jsonl
```

---

## Cost Tracking Issues

### Cost Not Tracked

**Problem:** Cost not appearing in reports

**Solution:**

1. Ensure cost tracking is enabled:

```python
with run(max_cost_usd=10.0) as ctx:  # Enables cost tracking
    pass
```

2. Check trace file contains cost events:

```bash
failcore report trace.jsonl --cost
```

### Budget Exceeded

**Problem:** `BudgetExceededError: Budget limit reached`

**Solution:**

1. Increase budget:

```python
with run(max_cost_usd=20.0) as ctx:  # Increase limit
    pass
```

2. Check current spending:

```bash
failcore report trace.jsonl --cost
```

---

## Getting Help

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### View Traces

```bash
# List all traces
failcore list

# View specific trace
failcore show trace.jsonl

# Generate report
failcore report trace.jsonl
```

### Check Configuration

```python
# List available policies
from failcore.core.validate.templates import list_policies
print(list_policies())

# Check FailCore home
from failcore.utils.paths import get_failcore_home
print(get_failcore_home())
```

---

## Next Steps

- [Configuration Reference](../reference/configuration.md) - Configuration options
- [FAQ](../appendix/faq.md) - More common questions
