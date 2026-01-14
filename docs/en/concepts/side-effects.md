# Side Effects

Side effects are what FailCore tracks and controls during execution.

---

## What Are Side Effects

Side effects are changes to the **external world** when tools execute:

- Modify filesystem
- Send network requests
- Spawn processes
- Modify environment variables

**Pure functions** (only compute, don't change external state) have no side effects.

---

## Side-Effect Categories

FailCore categorizes side effects as follows:

### 1. Filesystem (FILESYSTEM)

Filesystem operations:

- **Read**: `filesystem.read`
  - Read file content
  - List directories
  - Check file existence

- **Write**: `filesystem.write`
  - Create files
  - Modify files
  - Append content

- **Delete**: `filesystem.delete`
  - Delete files
  - Delete directories
  - Clear directories

### 2. Network (NETWORK)

Network operations:

- **Egress**: `network.egress`
  - HTTP/HTTPS requests
  - WebSocket connections
  - Socket connections

- **DNS**: `network.dns`
  - DNS queries
  - Domain resolution

### 3. Process (PROCESS)

Process operations:

- **Spawn**: `process.spawn`
  - Create child processes
  - Execute commands

- **Kill**: `process.kill`
  - Terminate processes
  - Send signals

---

## Side-Effect Detection

FailCore uses **two-phase detection**:

### Phase 1: Prediction (Pre-execution)

Before execution, FailCore analyzes tool calls:

```python
@guard()
def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)
```

When calling `write_file("test.txt", "data")`:
- Tool name: `write_file`
- Parameters: `{"path": "test.txt", "content": "data"}`
- Predicted side effect: `filesystem.write` → `test.txt`

### Phase 2: Observation (Post-execution)

After execution, FailCore observes actual side effects:

```python
# Actual execution
with open("test.txt", "w") as f:
    f.write("data")

# Observed side effects
observed_side_effects = [
    SideEffectEvent(
        type="filesystem.write",
        target="test.txt",
        tool="write_file"
    )
]
```

---

## Side-Effect Recording

All side effects are recorded to trace files:

```json
{
  "event": "SIDE_EFFECT",
  "type": "filesystem.write",
  "target": "test.txt",
  "category": "filesystem",
  "tool": "write_file",
  "step_id": "abc123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Side Effects in Trace Files

```jsonl
{"event": "STEP_START", "tool": "write_file", "params": {"path": "test.txt"}}
{"event": "SIDE_EFFECT", "type": "filesystem.write", "target": "test.txt"}
{"event": "STEP_END", "status": "SUCCESS"}
```

---

## Side-Effect Boundaries

Side-effect boundaries define **allowed side effects**:

```python
from failcore import run

# Only allow filesystem reads
with run(policy="fs_safe") as ctx:
    @guard()
    def read_file(path: str):
        with open(path, "r") as f:
            return f.read()
    
    # Allow: read is within boundary
    read_file("data.txt")
    
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # Block: write is not within boundary (if boundary only allows reads)
    try:
        write_file("output.txt", "data")
    except SideEffectBoundaryCrossedError:
        print("Write exceeds boundary")
```

---

## Side-Effect Auditing

FailCore provides side-effect auditing:

### View Side Effects

```bash
failcore show <trace_file>
```

Output includes:
- All observed side effects
- Side-effect types and targets
- Occurrence times

### Audit Reports

```bash
failcore report <trace_file>
```

Generate audit reports including:
- Side-effect summary
- Violation statistics
- Timeline

---

## Side-Effect Detection Mechanisms

### Static Analysis

FailCore uses static analysis to predict side effects:

```python
# Tool name and parameter analysis
tool = "write_file"
params = {"path": "test.txt"}

# Detection rules
if tool in ["write_file", "create_file"]:
    side_effect = detect_filesystem_side_effect(tool, params, "write")
    # Returns: SideEffectEvent(type="filesystem.write", target="test.txt")
```

### Runtime Observation

Observe actual side effects after execution:

```python
# Filesystem monitoring (if enabled)
# Network monitoring (if enabled)
# Process monitoring (if enabled)
```

---

## Side-Effect Type Definitions

### Filesystem Side Effects

```python
FILESYSTEM_READ = "filesystem.read"
FILESYSTEM_WRITE = "filesystem.write"
FILESYSTEM_DELETE = "filesystem.delete"
FILESYSTEM_METADATA = "filesystem.metadata"  # Read metadata
```

### Network Side Effects

```python
NETWORK_EGRESS = "network.egress"
NETWORK_DNS = "network.dns"
NETWORK_INGRESS = "network.ingress"  # Listen on ports
```

### Process Side Effects

```python
PROCESS_SPAWN = "process.spawn"
PROCESS_KILL = "process.kill"
PROCESS_SIGNAL = "process.signal"
```

---

## Side-Effect Metadata

Each side-effect event contains metadata:

```python
@dataclass
class SideEffectEvent:
    type: SideEffectType
    target: Optional[str] = None  # Target (path/URL/command)
    tool: Optional[str] = None  # Tool name
    step_id: Optional[str] = None  # Step ID
    metadata: Dict[str, Any] = None  # Additional metadata
```

### Metadata Example

```json
{
  "type": "filesystem.write",
  "target": "test.txt",
  "tool": "write_file",
  "step_id": "abc123",
  "metadata": {
    "file_size": 1024,
    "permissions": "0644",
    "created": true
  }
}
```

---

## Side Effects and Policy

Side-effect checks occur before policy checks:

```
1. Predict side effects
   ↓
2. Check side-effect boundary
   ↓
3. If exceeds boundary → Block
4. If within boundary → Continue policy check
   ↓
5. Execute tool
   ↓
6. Observe actual side effects
   ↓
7. Record side effects
```

---

## Best Practices

### 1. Explicitly Declare Side Effects

Declare side effects in tool metadata:

```python
from failcore.core.tools.metadata import ToolMetadata, SideEffect

@guard(metadata=ToolMetadata(
    side_effect=SideEffect.FILESYSTEM
))
def write_file(path: str, content: str):
    pass
```

### 2. Minimize Side Effects

When designing tools, minimize side effects:

```python
# Good: Side effects are clear
def read_config(path: str) -> dict:
    # Only read, don't modify
    with open(path, "r") as f:
        return json.load(f)

# Bad: Side effects unclear
def process_file(path: str):
    # Read or write? Unclear
    pass
```

### 3. Test Side Effects

Verify side effects are correctly detected:

```python
def test_side_effect_detection():
    with run(policy="fs_safe") as ctx:
        @guard()
        def write_file(path: str, content: str):
            with open(path, "w") as f:
                f.write(content)
        
        write_file("test.txt", "data")
        
        # Check side-effect records in trace file
        trace = load_trace(ctx.trace_path)
        side_effects = [e for e in trace if e["event"] == "SIDE_EFFECT"]
        assert len(side_effects) > 0
        assert side_effects[0]["type"] == "filesystem.write"
```

---

## Summary

Side effects are a core concept of FailCore:

- ✅ Two-phase detection: Prediction + Observation
- ✅ Complete recording: All side effects recorded to trace files
- ✅ Boundary control: Limit allowed side effects through boundaries
- ✅ Audit support: Complete side-effect history for auditing

---

## Next Steps

- [Execution Boundary](execution-boundary.md) - Learn how to define side-effect boundaries
- [Policy](policy.md) - Learn how policies control side effects
- [Trace and Replay](trace-and-replay.md) - How to use side-effect records
