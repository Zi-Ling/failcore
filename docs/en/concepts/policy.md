# Policy

Policy is FailCore's core mechanism for defining and enforcing security rules.

---

## What is a Policy

A policy is a set of **validation rules** used to check whether tool calls are allowed before execution.

Policies decide:
- ✅ Which operations are allowed
- ❌ Which operations are blocked
- ⚠️ Which operations need warnings

---

## Policy Presets

FailCore provides the following policy presets:

### safe (Default)

Comprehensive security policy including filesystem and network safety:

```python
from failcore import run

with run(policy="safe") as ctx:
    # Enabled:
    # - Path traversal protection
    # - SSRF protection
    # - Basic resource limits
    pass
```

**Enabled validators:**
- `security_path_traversal`: Path traversal protection
- `network_ssrf`: SSRF protection
- `resource_file_size`: File size limits (warning mode)

### fs_safe

Filesystem safety policy:

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    # Enabled:
    # - Sandbox path protection
    # - Path traversal protection
    # - File size limits
    pass
```

**Enabled validators:**
- `security_path_traversal`: Path traversal and sandbox protection
- `resource_file_size`: File size limits

### net_safe

Network safety policy:

```python
with run(policy="net_safe") as ctx:
    # Enabled:
    # - SSRF protection
    # - Private network blocking
    # - Protocol restrictions
    pass
```

**Enabled validators:**
- `network_ssrf`: SSRF and private network protection

### shadow

Observation mode policy:

```python
with run(policy="shadow") as ctx:
    # Enabled:
    # - All validators (observation mode)
    # - Record decisions but don't block
    pass
```

**Features:**
- All validators enabled but set to `SHADOW` mode
- Record all decisions but don't block execution
- Used to evaluate policy impact

### permissive

Permissive policy:

```python
with run(policy="permissive") as ctx:
    # Enabled:
    # - Basic safety checks (warning mode)
    # - Don't block execution
    pass
```

**Features:**
- Most validators set to `WARN` mode
- Only block obviously dangerous operations

---

## Policy Structure

Policies consist of the following parts:

### Validators

Validators are components that perform checks:

```python
ValidatorConfig(
    id="security_path_traversal",
    domain="security",
    enabled=True,
    enforcement=EnforcementMode.BLOCK,
    priority=30,
    config={
        "path_params": ["path", "file_path"],
        "sandbox_root": "./data"
    }
)
```

**Field descriptions:**
- `id`: Validator unique identifier
- `domain`: Validator domain (security/network/resource)
- `enabled`: Whether enabled
- `enforcement`: Enforcement mode (BLOCK/WARN/SHADOW)
- `priority`: Priority (lower numbers = higher priority)
- `config`: Validator configuration

### Enforcement Modes

- **BLOCK**: Block execution (strict mode)
- **WARN**: Warn but don't block (permissive mode)
- **SHADOW**: Only record, don't block (observation mode)

### Global Override

Policies can be overridden in emergencies:

```python
OverrideConfig(
    enabled=False,  # Disabled by default
    require_token=True  # Requires token to enable
)
```

---

## Policy Check Flow

Policy checks execute in a fixed order:

```
1. Side-effect boundary gate (fast pre-check)
   ↓
2. Semantic guard (high-confidence malicious pattern detection)
   ↓
3. Taint tracking/DLP (data loss prevention)
   ↓
4. Main policy check (user/system policy)
   ↓
   Validators sorted by priority
   ↓
   First validator returning DENY blocks execution
```

### Validator Priority

Validators are sorted by `priority` field:
- Lower numbers = higher priority
- High-priority validators execute first
- If high-priority validator returns DENY, subsequent validators don't execute

---

## Policy Decisions

Each validator returns a decision:

### PolicyResult

```python
@dataclass
class PolicyResult:
    allowed: bool  # Whether allowed
    reason: str  # Reason
    error_code: Optional[str]  # Error code
    suggestion: Optional[str]  # Fix suggestion
    remediation: Optional[Dict]  # Structured fix instructions
```

### Allow Decision

```python
PolicyResult.allow(reason="Path is within sandbox")
```

### Deny Decision

```python
PolicyResult.deny(
    reason="Path traversal detected: '../../etc/passwd'",
    error_code="PATH_TRAVERSAL",
    suggestion="Use relative paths, don't use '..'",
    remediation={
        "action": "sanitize_path",
        "template": "Remove '..': {sanitized_path}",
        "vars": {"sanitized_path": "etc/passwd"}
    }
)
```

---

## Custom Policies

### Load from File

Create policy file `policy.yaml`:

```yaml
version: v1
validators:
  security_path_traversal:
    enabled: true
    enforcement: BLOCK
    priority: 30
    config:
      path_params: ["path", "file_path"]
      sandbox_root: "./workspace"
metadata:
  name: "custom_policy"
  description: "Custom policy"
```

Load policy:

```python
from failcore.core.validate.loader import load_policy

policy = load_policy("policy.yaml")
```

### Programmatic Creation

```python
from failcore.core.validate.contracts import Policy, ValidatorConfig, EnforcementMode

policy = Policy(
    version="v1",
    validators={
        "security_path_traversal": ValidatorConfig(
            id="security_path_traversal",
            domain="security",
            enabled=True,
            enforcement=EnforcementMode.BLOCK,
            priority=30,
            config={
                "path_params": ["path"],
                "sandbox_root": "./data"
            }
        )
    },
    metadata={
        "name": "my_policy",
        "description": "My custom policy"
    }
)
```

---

## Policy Merging

FailCore supports policy merging:

### Active Policy + Shadow Policy

```python
from failcore.core.validate.loader import load_merged_policy

# Load merged policy (active + shadow)
policy = load_merged_policy(use_shadow=True)
```

### Active Policy + Breakglass Override

```python
# Load merged policy (active + breakglass)
policy = load_merged_policy(use_breakglass=True)
```

Merging rules:
- Shadow policy: Overrides active policy's `enforcement` mode to `SHADOW`
- Breakglass override: Temporarily disables all validators

---

## Policy Management CLI

### Initialize Policy Directory

```bash
failcore policy init
```

Creates:
- `active.yaml`: Active policy
- `shadow.yaml`: Shadow policy
- `breakglass.yaml`: Emergency override

### List Validators

```bash
failcore policy list-validators
```

### Show Policy

```bash
failcore policy show
failcore policy show --type shadow
failcore policy show --type merged
```

### Explain Policy Decisions

```bash
failcore policy explain --tool write_file --param path=../../etc/passwd
```

Shows which validators would trigger and why.

---

## Policy Best Practices

### 1. Start with Presets

```python
# Good: Use presets
with run(policy="fs_safe") as ctx:
    pass

# Bad: Create from scratch
# Unless you have special requirements
```

### 2. Gradually Tighten

```python
# Phase 1: Observation mode
with run(policy="shadow") as ctx:
    # Record all decisions, don't block

# Phase 2: Warning mode
# Modify policy, change enforcement to WARN

# Phase 3: Block mode
# Modify policy, change enforcement to BLOCK
```

### 3. Test Policies

```python
def test_policy():
    with run(policy="fs_safe", sandbox="./test") as ctx:
        @guard()
        def write_file(path: str, content: str):
            with open(path, "w") as f:
                f.write(content)
        
        # Should succeed
        write_file("test.txt", "data")
        
        # Should be blocked
        try:
            write_file("../../etc/passwd", "hack")
            assert False, "Should be blocked"
        except PolicyDeny:
            pass  # Expected behavior
```

### 4. Document Policy Changes

Policy files should:
- Use version control
- Document change reasons
- Include test cases

---

## Policy vs Boundary

**Policy**:
- Procedural: Defines how to check
- Dynamic: Can be context-based
- Complex: Can contain conditional logic

**Boundary**:
- Declarative: Defines what's allowed
- Static: Defined before execution
- Simple: Yes/No judgment

Policies execute **after** boundary checks, providing more detailed validation.

---

## Summary

Policies are FailCore's core security mechanism:

- ✅ Define validation rules
- ✅ Support multiple enforcement modes
- ✅ Provide LLM-friendly error messages
- ✅ Support policy merging and overrides
- ✅ Complete CLI management tools

---

## Next Steps

- [Execution Boundary](execution-boundary.md) - Learn how boundaries work
- [Trace and Replay](trace-and-replay.md) - How to use policy decision records
- [Filesystem Safety](../guides/fs-safety.md) - Filesystem policy practices
