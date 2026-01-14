# Taint Tracking Module

## Overview

The Taint Tracking module provides lightweight data flow tracking across tool boundaries. It tracks where sensitive data originates and how it flows through tool calls, enabling DLP policies to make informed decisions about data leakage risks.

## Purpose

Taint tracking answers the question:

> "Where did this data come from, and what is its sensitivity level?"

The module is designed to be:
- **Lightweight**: Minimal overhead, not full program analysis
- **Tool-boundary focused**: Tracks data flow between tools (A → B), not within tool execution
- **Context provider**: Provides taint context for DLP policy enforcement
- **Optional validator**: Can emit warnings for high-risk flows, but primarily serves as a context provider

## Core Concepts

### 1. Taint Tag

A **TaintTag** represents the sensitivity and origin of data:

- **Source**: Where data originated (USER, MODEL, TOOL, SYSTEM)
- **Sensitivity**: Data sensitivity level (PUBLIC, INTERNAL, CONFIDENTIAL, PII, SECRET)
- **Source tool**: Tool that produced the tainted data
- **Source step**: Step ID where taint was marked

### 2. Taint Context

The **TaintContext** manages taint state across a run:

- Tracks tainted data per step
- Classifies tools as sources (produce sensitive data) or sinks (consume sensitive data)
- Detects tainted inputs in tool parameters
- Provides taint information to DLP validators

### 3. Taint Flow Tracking

The **TaintFlowTracker** tracks data flow across tool boundaries:

- **Taint edges**: Records flow from source_step → sink_step
- **Flow chains**: Tracks multi-hop flows (A → B → C)
- **Field-level tracking**: Optional JSON path tracking (e.g., `user.email`)
- **Auto-detection**: Heuristic field_path detection with confidence levels

### 4. Binding Confidence

When field_path is auto-detected, a confidence level is assigned:

- **High**: Explicit field_path provided, or step_id reference found
- **Medium**: Common field name match (input, content, data, etc.) or nested structure match
- **Low**: Weak match or no match found

## Architecture

### Middleware vs Validator

The taint system has two components:

1. **TaintMiddleware** (`guards/taint/middleware.py`):
   - Marks data sources as tainted
   - Tracks taint propagation
   - Provides taint context to DLP middleware
   - **Does NOT enforce DLP policies** (that's DLPMiddleware's job)

2. **TaintFlowValidator** (`validate/builtin/taint_flow.py`):
   - Optional validator for policy-driven taint flow detection
   - Emits WARN decisions (not blocking) for high-risk flows
   - Reads taint context from `Context.state["taint_context"]`

### Integration Flow

```
TaintMiddleware (mark) → DLPMiddleware (enforce policy) → TaintFlowValidator (optional audit)
```

1. `TaintMiddleware.on_call_success`: Mark source tool outputs as tainted
2. `DLPMiddleware.on_call_start`: Use taint context to detect leakage risks
3. `TaintFlowValidator.evaluate`: Optionally emit warnings for audit

## Key Features

### 1. Context Provider

Taint context is provided via `Context.state["taint_context"]`, making it available to all validators without tight coupling.

**Usage**:
```python
# In validator
taint_context = context.state.get("taint_context")
if taint_context:
    taint_tags = taint_context.detect_tainted_inputs(params, dependencies)
```

### 2. Auto-Detection with Confidence

Taint flow tracking can auto-detect field paths using heuristics:

- **Step ID references**: If a parameter value contains a step_id, that field is the path (high confidence)
- **Common field names**: Fields like `input`, `content`, `data`, `value`, `text` (medium confidence)
- **Nested structures**: Traverses nested dicts/lists looking for step_id references (medium confidence)

**Evidence includes**:
- `binding_confidence`: "high", "medium", or "low"
- `field_path`: Detected or explicit path
- `taint_chain`: Complete flow chain from source to sink

### 3. Flow Chain Tracking

`TaintFlowTracker` can generate complete flow chains:

```python
tracker = TaintFlowTracker()
chain = tracker.get_flow_chain(sink_step_id, max_depth=10)
# Returns: [TaintEdge(source -> intermediate), TaintEdge(intermediate -> sink)]
```

This enables:
- Data lineage visualization
- Audit reports showing complete data flow
- Explaining why data is considered sensitive

### 4. Policy-Driven Validator

`TaintFlowValidator` can be enabled/disabled via policy:

```yaml
validators:
  taint_flow:
    enabled: true
    enforcement: warn  # Always warns, never blocks
    config:
      min_sensitivity: confidential
      high_risk_sinks:
        - send_email
        - http_post
```

## Configuration

### TaintFlowValidator Config

```yaml
validators:
  taint_flow:
    enabled: true
    enforcement: warn
    config:
      min_sensitivity: confidential  # Minimum sensitivity to report
      high_risk_sinks: []  # Explicit sink list (empty = use TaintContext defaults)
      require_explicit_sinks: false  # Only check explicit list
```

### TaintContext Configuration

TaintContext is typically configured by the execution system, not via policy. It includes:

- Source tool classification (which tools produce sensitive data)
- Sink tool classification (which tools consume sensitive data)
- Tool dependencies (which tools use outputs from other tools)

## Evidence Structure

Taint flow decisions include:

```json
{
  "tool": "send_email",
  "sink_type": "high_risk",
  "sensitivity": "secret",
  "taint_sources": ["user", "tool"],
  "taint_count": 2,
  "source_tools": ["read_file", "get_api_key"],
  "source_step_ids": ["step_1", "step_3"],
  "binding_confidence": "high",
  "field_path": "body",
  "taint_chain": [
    {
      "source_step_id": "step_1",
      "source_tool": "read_file",
      "sink_step_id": "step_5",
      "sink_tool": "send_email",
      "field_path": "body"
    }
  ]
}
```

## Integration with DLP

DLP validators use taint context to:

1. **Detect tainted inputs**: Check if tool parameters contain tainted data
2. **Determine sensitivity**: Use max sensitivity from taint tags
3. **Apply policies**: Make BLOCK/SANITIZE/WARN decisions based on sensitivity
4. **Generate evidence**: Include taint sources and flow chains in decisions

**Example**:
```python
# In DLPGuardValidator
taint_context = self._get_taint_context(context)
taint_tags = taint_context.detect_tainted_inputs(params, dependencies)
max_sensitivity = self._get_max_sensitivity(taint_tags, pattern_matches)
policy = policy_matrix.get_policy(max_sensitivity)
```

## Best Practices

1. **Enable TaintMiddleware first**: Mark taint before DLP checks
2. **Use TaintFlowValidator for audit**: Enable for post-run analysis, not blocking
3. **Filter low-confidence flows**: In explain output, show only high/medium confidence flows
4. **Provide explicit field_paths**: When possible, provide explicit paths for higher confidence
5. **Use TaintContext from state**: Read from `Context.state["taint_context"]` for loose coupling

## Relationship to Other Systems

- **DLP**: Uses taint context to detect leakage risks
- **Semantic**: Independent (does not use taint)
- **Security Validators**: Independent (path traversal, SSRF don't use taint)
- **Drift**: Independent (post-run analysis, not runtime)

Taint tracking is a **foundational capability** that enables other validators (especially DLP) to make better decisions.
