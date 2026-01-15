# FailCore Configuration System

## Design Principles

### 1. enabled Only Determines Registration (NOT Runtime Behavior)

**❌ WRONG:**
```python
# In runtime code
if not config.semantic.enabled:
    return  # DON'T DO THIS
```

**✅ CORRECT:**
```python
# At startup (in builder.py)
if config.semantic.enabled:
    engine = RealSemanticEngine(...)
else:
    engine = NoOpSemanticEngine()

# In runtime code (never check enabled)
result = engine.check(tool_name, params)  # Always has an engine
```

### 2. Each Module Has Its Own Semantic Configuration

**❌ WRONG:**
```python
# Unified strict_mode (misleading)
class ModuleConfig:
    enabled: bool
    strict_mode: bool  # What does this mean for each module?
```

**✅ CORRECT:**
```python
# Each module has its own semantics
class DLPConfig(ModuleConfig):
    mode: Literal["block", "sanitize", "warn"]

class SemanticConfig(ModuleConfig):
    min_severity: RuleSeverity

class DriftConfig(ModuleConfig):
    analysis_only: bool
```

### 3. Code = Truth, YAML = Input Parameters

**✅ System works without YAML:**
```python
# This works (uses code defaults)
config = FailCoreConfig.default()

# This also works (YAML is optional)
config = load_config()  # Tries YAML, falls back to defaults

# Delete default.yml, system still works
```

**✅ Deep Immutability:**
```python
# Configuration is deeply immutable (nested containers are frozen)
config = load_config()

# Shallow frozen (dataclass fields)
config.dlp.mode = "block"  # ❌ Raises error

# Deep frozen (nested dicts/lists converted to immutable)
# All nested containers use MappingProxyType/tuple
```

### 4. NoOp Engines Follow Module Implementation

**✅ Architecture:**
```
failcore/core/guards/dlp/
  ├── engine.py      # RealDlpEngine + NoOpDlpEngine
  ├── types.py       # DlpResult (unified return type)
  └── ...

failcore/core/runtime/builder.py  # config.enabled → Real/NoOp
```

**Key points:**
- NoOp engines are in module directories (not config/)
- Both Real and NoOp return same type (e.g., `DlpResult`)
- NoOp sets `reason="disabled"` (for observability only)
- Runtime never sees Optional - always has an engine instance

### 5. RuntimeServices as Capability Bundle

**✅ Builder returns capability bundle:**
```python
from failcore.core.runtime.builder import build_runtime_services

# Build services (startup only)
services = build_runtime_services(config)

# Runtime uses services directly
result = services.dlp.scan(payload)
verdict = services.semantic.check(tool_name, params)

# Capabilities for observability
print(services.capabilities)  # Read-only view
```

## Architecture

### File Locations

**Configuration (config/):**
- `failcore/config/modules/`: Module configuration classes (DLPConfig, SemanticConfig, etc.)
- `failcore/config/loader.py`: Configuration loader (YAML + defaults)
- `failcore/config/validator.py`: Configuration validation (ConfigIssue)

**Runtime (core/):**
- `failcore/core/guards/dlp/engine.py`: RealDlpEngine + NoOpDlpEngine
- `failcore/core/guards/dlp/types.py`: DlpResult type
- `failcore/core/runtime/builder.py`: Assembles RuntimeServices from config
- `failcore/core/runtime/capability.py`: Runtime capabilities (from registry)

**Key Principle:** Config defines desired state, Runtime provides factual state.

### Module Structure

Each module has:
- `types.py`: Unified result types (Real and NoOp return same type)
- `engine.py`: Real and NoOp engine implementations
- Other module-specific files

### Builder Pattern

```
config (startup)
  ↓
builder.py (config.enabled → Real/NoOp)
  ↓
RuntimeServices (capability bundle)
  ↓
runtime code (uses engines directly, no config checks)
```

### Type Safety

All engines implement same interface:
- `DlpEngine.scan(payload) -> DlpResult`
- `SemanticEngine.check(tool, params) -> SemanticResult`
- `EffectsEngine.detect(tool, params) -> EffectsResult`
- `TaintEngine.check_sink(sink, data) -> TaintResult`
- `DriftEngine.detect_drift(current, baseline) -> DriftResult`

NoOp engines return same types with `reason="disabled"`.

## Usage Examples

### Basic Configuration

```python
from failcore.config import load_config, FailCoreConfig

# Load from YAML (optional)
config = load_config()

# Or use defaults
config = FailCoreConfig.default()

# Access module configs
print(config.dlp.enabled)  # False (default)
print(config.dlp.mode)      # "warn" (default)
```

### Building Runtime Services

```python
from failcore.core.runtime.builder import build_runtime_services
from failcore.config import load_config

# Load config
config = load_config()

# Build services (startup only - config.enabled checked here)
services = build_runtime_services(config)

# Runtime: Use engines directly (no config checks)
dlp_result = services.dlp.scan("test payload")
semantic_result = services.semantic.check("test_tool", {"param": "value"})

# Check if disabled (OBSERVABILITY ONLY - not for logic control)
# ✅ CORRECT: Use for logging/UI
if dlp_result.is_disabled:
    logger.debug("DLP is disabled (NoOp engine)")
else:
    logger.info(f"DLP found {dlp_result.match_count} matches")

# ❌ WRONG: Using is_disabled to change runtime behavior
# if result.is_disabled:
#     return  # DON'T DO THIS - violates principle #1
```

### Runtime Code Pattern

```python
# ✅ CORRECT: Runtime code
def process_tool_call(tool_name: str, params: dict, services: RuntimeServices):
    # No config checks - just use engines
    dlp_result = services.dlp.scan(params)
    semantic_result = services.semantic.check(tool_name, params)
    effects_result = services.effects.detect(tool_name, params)
    
    # Handle results based on engine output, not config
    if dlp_result.has_matches and dlp_result.max_severity >= 8:
        # Handle high-severity DLP match
        pass
    
    if semantic_result.is_blocked:
        # Handle semantic block
        pass
```

### Capabilities for Observability

```python
# Get capabilities (read-only, for UI/reports/audit)
# Capabilities come from engines/registry (factual state), not config (desired state)
capabilities = services.capabilities

print(capabilities)
# DLP: enabled (warn) [15 rules]
# Semantic: disabled
# Effects: enabled (strict_enforced) [0 rules]  # Note: enabled but rules=0
# Taint: disabled
# Drift: enabled (analysis_only)

# As dictionary
cap_dict = capabilities.to_dict()

# Key distinction:
# - "enabled=true, rules=0" = Module enabled but no rules loaded (Real engine, empty registry)
# - "enabled=false" = Module not registered (NoOp engine)
```

**Critical Constraint:**
```python
# capabilities.status MUST reflect factual runtime state (engine/registry),
# NOT config.enabled (desired state).

# Status is determined by:
# - Engine type: isinstance(engine, NoOpXxxEngine) → "disabled"
# - Registry state: rules loaded successfully → "enabled"
# NOT by: config.enabled (that's desired state, not factual)
```

**Note:** Capabilities are defined in `failcore/core/runtime/capability.py` and come from engine instances and rule registry (factual state), not from config (desired state).

### Configuration Validation

```python
# Validate config for illegal combinations
issues = config.validate()

for issue in issues:
    print(issue)
    # ⚠️  [modules.dlp.mode] mode='block' has no effect when enabled=false
    #    Hint: Set modules.dlp.enabled=true to enable DLP blocking

# Issues have structured fields
for issue in issues:
    if issue.level == "error":
        # Handle error (invalid value domain)
        print(f"ERROR: {issue.path} - {issue.message}")
    elif issue.level == "warn":
        # Handle warning (misleading but valid)
        print(f"WARNING: {issue.path} - {issue.message}")
        if issue.hint:
            print(f"  Hint: {issue.hint}")
```

**Issue Structure:**
- `level`: "warn" or "error"
- `path`: Configuration path (e.g., "modules.dlp.mode")
- `message`: Issue description
- `hint`: Optional fix suggestion

## Module-Specific Configuration

**Important:** These config values are used in `builder.py` to construct engines. Runtime code does NOT read config.

### DLP

```python
# In builder.py (startup)
dlp_engine = RealDlpEngine(
    mode=config.dlp.mode,  # "block", "sanitize", or "warn"
    redact=config.dlp.redact,
    max_scan_chars=config.dlp.max_scan_chars,
)

# In runtime (no config access)
result = services.dlp.scan(payload)
# Engine behavior determined by mode set during construction
```

### Semantic

```python
# In builder.py (startup)
semantic_engine = RealSemanticEngine(
    min_severity=config.semantic.min_severity,  # Determines which rules are active
    enabled_categories=config.semantic.enabled_categories,
)

# In runtime (no config access)
verdict = services.semantic.check(tool_name, params)
```

### Effects

```python
# In builder.py (startup)
boundary = get_boundary(config.effects.boundary_preset)
effects_engine = RealEffectsEngine(boundary=boundary)

# In runtime (no config access)
effects_result = services.effects.detect(tool_name, params)
```

### Taint

```python
# In builder.py (startup)
taint_engine = RealTaintEngine(
    propagation_mode=config.taint.propagation_mode,  # "whole" or "paths"
    max_path_depth=config.taint.max_path_depth,
)

# In runtime (no config access)
taint_result = services.taint.check_sink(sink, data)
```

### Drift

```python
# In builder.py (startup)
drift_engine = RealDriftEngine(
    analysis_only=config.drift.analysis_only,  # If True, only analyze (never block)
    magnitude_threshold_medium=config.drift.magnitude_threshold_medium,
    magnitude_threshold_high=config.drift.magnitude_threshold_high,
)

# In runtime (no config access)
drift_result = services.drift.detect_drift(current, baseline)
```

## Configuration Files

### config.yml.example (Example Configuration)

**Important:** This is an **example file**, not the source of truth. Code defaults are the truth.

```yaml
# Example configuration file (rename to config.yml to use)
# All values have code defaults - this file is optional

modules:
  dlp:
    enabled: false
    mode: "warn"
    redact: true
    max_scan_chars: 65536
  
  semantic:
    enabled: false
    min_severity: "high"
    enabled_categories: null
  
  effects:
    enabled: false
    boundary_preset: "none"
    enforce_boundary: false
  
  taint:
    enabled: false
    propagation_mode: "whole"
    max_path_depth: 3
  
  drift:
    enabled: true
    analysis_only: true
    magnitude_threshold_medium: 2.0
    magnitude_threshold_high: 5.0
```

**Key Points:**
- **Code = Truth**: All defaults are in code (`FailCoreConfig.default()`)
- **YAML = Input Parameters**: This file only overrides code defaults
- **Delete this file**: System still works with code defaults
- **Not "default.yml"**: Avoid naming it "default.yml" to prevent confusion about source of truth

## Migration Guide

### Old Code (Deprecated)

```python
# OLD: Runtime checks
if not semantic_enabled:
    return

# OLD: Unified strict_mode
if strict_mode:
    # What does this mean?

# OLD: Optional engines
if dlp_engine:
    result = dlp_engine.scan(payload)
```

### New Code

```python
# NEW: Startup registration (in builder)
if config.semantic.enabled:
    engine = RealSemanticEngine(...)
else:
    engine = NoOpSemanticEngine()

# NEW: Module-specific config
if config.semantic.min_severity == RuleSeverity.CRITICAL:
    # Clear semantic

# NEW: Always have engine (never Optional)
result = services.dlp.scan(payload)  # Always works

# NEW: is_disabled is observability-only (NOT for logic control)
# ✅ CORRECT: Use for logging/UI
if result.is_disabled:
    logger.debug("DLP disabled (NoOp)")

# ❌ WRONG: Using is_disabled to change behavior
# if result.is_disabled:
#     return  # DON'T DO THIS - violates principle #1
```

**Contract:** `is_disabled` is observability-only. Using it to change runtime behavior is a bug.

## Key Takeaways

1. **config.enabled** only appears in `builder.py` (startup)
2. **Runtime** never checks config or enabled flags
3. **NoOp engines** return same types with `reason="disabled"`
4. **RuntimeServices** bundles all engines and capabilities
5. **Types** ensure interface consistency (Real/NoOp)
6. **Capabilities** come from `failcore/core/runtime/capability.py` (registry factual state), not config
7. **Configuration** is deeply immutable (nested containers frozen)
8. **Validation** returns structured `ConfigIssue` with level, path, message, hint
