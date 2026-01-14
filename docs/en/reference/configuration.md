# Configuration Reference

Complete reference for FailCore configuration options.

---

## Runtime Configuration

### `run()` Parameters

The `run()` function accepts the following parameters:

#### Policy Configuration

```python
run(
    policy: str = "safe",  # Policy name or None
    strict: bool = True,    # Enable strict validation
)
```

**Policy Options:**
- `"safe"` (default): Combined fs_safe + net_safe
- `"fs_safe"`: Filesystem safety only
- `"net_safe"`: Network safety only
- `"shadow"`: Observation mode (no blocking)
- `"permissive"`: Minimal restrictions
- `None`: No policy (not recommended)

#### Path Configuration

```python
run(
    sandbox: Optional[str] = None,  # Sandbox root directory
    trace: str = "auto",            # Trace file path
    allow_outside_root: bool = False,  # Allow external paths
    allowed_trace_roots: Optional[list] = None,  # Trace whitelist
    allowed_sandbox_roots: Optional[list] = None,  # Sandbox whitelist
)
```

**Path Resolution Rules:**

1. **Name-only** (no path separators):
   - `sandbox="data"` → `<project>/.failcore/runs/<run>/sandbox/data/`
   - `trace="trace.jsonl"` → `<project>/.failcore/runs/<run>/trace.jsonl`

2. **Relative path** (contains `/` or `\`):
   - `sandbox="./workspace"` → `<project>/workspace/`
   - `trace="artifacts/demo.jsonl"` → `<project>/artifacts/demo.jsonl`

3. **Absolute path**:
   - `sandbox="/tmp/sandbox"` → `/tmp/sandbox/` (requires `allow_outside_root=True`)
   - `trace="/var/log/trace.jsonl"` → `/var/log/trace.jsonl` (requires whitelist)

**Special Values:**
- `trace="auto"` (default): Auto-generated path
- `trace=None`: Disable tracing

#### Cost Control

```python
run(
    max_cost_usd: Optional[float] = None,      # Maximum total cost
    max_tokens: Optional[int] = None,          # Maximum tokens
    max_usd_per_minute: Optional[float] = None,  # Maximum burn rate
)
```

**Examples:**
```python
# Budget limit
run(max_cost_usd=10.0)  # Stop at $10.00

# Token limit
run(max_tokens=10000)  # Stop at 10k tokens

# Burn rate limit
run(max_usd_per_minute=0.5)  # Max $0.50/minute
```

#### Run Metadata

```python
run(
    run_id: Optional[str] = None,  # Custom run ID
    tags: Optional[Dict[str, str]] = None,  # Tags for filtering
    auto_ingest: bool = True,  # Auto-ingest trace to database
)
```

**Examples:**
```python
# Custom run ID
run(run_id="production-run-001")

# Tags for filtering
run(tags={"environment": "prod", "version": "1.0"})

# Disable auto-ingest
run(auto_ingest=False)
```

---

## Proxy Configuration

### Command-Line Options

```bash
failcore proxy [OPTIONS]
```

**Options:**

- `--listen ADDRESS` (default: `127.0.0.1:8000`)
  - Proxy server listen address

- `--upstream URL` (optional)
  - Override upstream LLM provider URL

- `--mode MODE` (default: `warn`)
  - Security mode: `warn` or `strict`

- `--trace-dir PATH` (default: `.failcore/proxy`)
  - Directory for trace files

- `--budget FLOAT` (optional)
  - Maximum cost in USD

- `--run-id ID` (optional)
  - Custom run ID

### Programmatic Configuration

```python
from failcore.core.config.proxy import ProxyConfig

config = ProxyConfig(
    host="127.0.0.1",
    port=8000,
    upstream_timeout_s=60.0,
    upstream_max_retries=2,
    enable_streaming=True,
    streaming_chunk_size=8192,
    streaming_strict_mode=False,
    enable_dlp=True,
    dlp_strict_mode=False,
    trace_queue_size=10000,
    drop_on_full=True,
    allowed_providers=set(),  # Empty = allow all
    run_id=None,
    budget=None,
)
```

---

## Policy Configuration

### Policy Presets

FailCore provides built-in policy presets:

#### `safe` (Default)

```python
run(policy="safe")
```

**Enabled validators:**
- `security_path_traversal`: Path traversal protection
- `network_ssrf`: SSRF protection
- `resource_file_size`: File size limits (warning mode)

#### `fs_safe`

```python
run(policy="fs_safe", sandbox="./data")
```

**Enabled validators:**
- `security_path_traversal`: Path traversal and sandbox protection
- `resource_file_size`: File size limits

#### `net_safe`

```python
run(policy="net_safe")
```

**Enabled validators:**
- `network_ssrf`: SSRF and private network protection

#### `shadow`

```python
run(policy="shadow")
```

**Features:**
- All validators enabled in `SHADOW` mode
- Records decisions but doesn't block
- Useful for policy evaluation

#### `permissive`

```python
run(policy="permissive")
```

**Features:**
- Most validators in `WARN` mode
- Minimal blocking
- Suitable for development

### Custom Policies

Create custom policy files at `.failcore/validate/<name>.yaml`:

```yaml
# .failcore/validate/custom.yaml
validators:
  - name: security_path_traversal
    action: BLOCK
  - name: network_ssrf
    action: WARN
```

Use custom policy:

```python
run(policy="custom")
```

---

## Guard Configuration

### `guard()` Parameters

```python
guard(
    fn: Optional[Callable] = None,
    risk: RiskType = "medium",
    effect: Optional[EffectType] = None,
    action: Optional[str] = None,
    description: str = "",
)
```

**Parameters:**

- `risk`: Risk level (`"low"`, `"medium"`, `"high"`)
- `effect`: Effect type (`"read"`, `"fs"`, `"net"`, `"exec"`)
- `action`: Enforcement mode (`"block"`, `"warn"`, `"shadow"`)
- `description`: Tool description

**Examples:**

```python
# Low-risk read operation
guard(read_file, risk="low", effect="read")

# High-risk write operation
guard(write_file, risk="high", effect="fs", action="block")

# Network operation
guard(http_request, risk="medium", effect="net")
```

---

## Environment Variables

FailCore respects the following environment variables:

### `FAILCORE_HOME`

Default FailCore home directory:

```bash
export FAILCORE_HOME=/path/to/failcore
```

Default: `<project>/.failcore`

### `FAILCORE_POLICY`

Default policy name:

```bash
export FAILCORE_POLICY=fs_safe
```

### `FAILCORE_STRICT`

Enable strict mode by default:

```bash
export FAILCORE_STRICT=1
```

---

## Configuration Files

### Policy Files

Location: `.failcore/validate/<name>.yaml`

```yaml
validators:
  - name: security_path_traversal
    action: BLOCK
    config:
      allow_absolute: false
  - name: network_ssrf
    action: WARN
```

### Trace Configuration

Traces are stored in: `.failcore/runs/<date>/<run_id>_<time>/`

Structure:
```
.failcore/
  runs/
    20240101/
      run001_120000/
        trace.jsonl
        sandbox/
```

---

## Next Steps

- [Policy Syntax](policy-syntax.md) - Policy file format
- [Troubleshooting](../operations/troubleshooting.md) - Common issues
