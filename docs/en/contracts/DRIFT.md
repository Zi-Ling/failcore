# Parameter Drift Engine (Deterministic)

## Purpose

The Parameter Drift Engine detects **deterministic behavioral deviation** in tool execution parameters over time.

It does **not** attempt to predict failures, infer intent, or apply statistical / ML-based anomaly detection.

Its sole purpose is to answer the question:

> “Did this agent start doing something *different* from what it was previously doing, based on facts?”

This engine operates entirely on execution-time traces and produces evidence suitable for audit, replay, and human review.

---

## Non-Goals

To keep the system minimal, explainable, and auditable, the Drift Engine explicitly does **not**:

- Perform statistical anomaly detection
- Learn from historical runs across agents
- Predict future behavior
- Infer agent intent or reasoning
- Apply probabilistic or ML-based models

All outputs must be reproducible from the same trace input.

---

## Core Concepts

The Drift Engine is defined around four core concepts only.

### 1. Baseline

A **Baseline** represents the agent’s initial or stable parameter behavior for a given tool.

- Derived from early steps in a run
- Deterministically computed from observed parameters
- Tool-scoped (each tool has its own baseline)
- Immutable once established for a run

The baseline answers:

> “What did this agent originally do when invoking this tool?”

---

### 2. Drift

**Drift** is any deviation of tool parameters from the established baseline.

Drift is defined by **structural or semantic change**, not by frequency or probability.

Examples:
- Path change: `/tmp` → `/etc`
- Flag change: `recursive=false` → `recursive=true`
- Scope expansion: single file → wildcard

Drift does not imply a policy violation by itself.  
It represents movement into a **gray zone**.

---

### 3. Drift Score

The **Drift Score** is a deterministic numeric representation of how far a parameter set deviates from its baseline.

- Computed via direct comparison (diff-based)
- No normalization across runs
- No learning or adaptive weighting

The score exists solely to:
- Rank drift severity within a run
- Enable visual emphasis in replay UI

It must always be explainable in terms of concrete parameter differences.

---

### 4. Inflection Point

An **Inflection Point** is the first step where drift is detected.

- Defined as the earliest step where `drift_score > 0`
- Marks the transition from “baseline behavior” to “deviating behavior”

This point is critical for incident analysis, as it often precedes:
- Policy violations
- Side-effect boundary crossings
- Cost explosions

---

### 5. Annotations

**Annotations** are human-readable markers emitted by the Drift Engine for replay and UI rendering.

Annotations may include:
- Drift detected
- Fields changed
- Baseline vs current value
- Inflection point marker

Annotations do not enforce policy and do not block execution.

They exist to support:
- Incident replay
- Human-in-the-loop review
- Post-mortem analysis

---

## Scope of Operation

The Drift Engine operates:

- Per run
- Per tool
- On execution-time trace data only

It consumes:
- Tool name
- Parameter payload
- Execution sequence / timestamp

It produces:
- No side effects
- No blocking decisions
- No persistent state outside the run context

---

## Relationship to Other Systems

- **Policy Engine**: Drift is informational; policy decides enforcement.
- **Side-Effect Auditor**: Drift may precede boundary violations but does not replace them.
- **Replay System**: Drift annotations are rendered as part of the incident timeline.

The Drift Engine is intentionally positioned as a **signal generator**, not an authority.

---

## Design Principle

> Determinism over intelligence  
> Evidence over inference  
> Explainability over sophistication

If two engineers replay the same trace, they must observe the same drift results.

Anything that violates this principle is considered out of scope.

---

## Integration with Validation System

### PostRunDriftValidator

The drift engine is integrated into the validation system via `PostRunDriftValidator` (`validate/builtin/drift.py`):

- **Post-run validator**: Processes trace after execution (not runtime gate)
- **Policy-driven**: Configuration from Policy
- **Unified output**: Returns `DecisionV1` objects compatible with validation engine
- **Evidence-rich**: Includes drift scores, change details, inflection reasons

### Input Standardization

The validator accepts trace input via `Context.state`:

- **trace_source**: Enum ("path", "events", "auto") determines input priority
- **trace_path**: File path to trace (used if trace_source="path" or auto-detected)
- **trace_events**: List of trace events (used if trace_source="events" or auto-detected)
- **trace_completeness**: Validation status ("complete", "partial", "unknown")

**Priority**:
1. `trace_source` setting (if "path" or "events")
2. `trace_path` (if present)
3. `trace_events` (if present)
4. Fallback: try both

### Evidence Structure

Drift decisions include:

```json
{
  "tool": "post_run_analysis",
  "code": "FC_DRIFT_INFLECTION_POINT",
  "message": "Drift inflection point detected at step 5",
  "risk_level": "medium",
  "evidence": {
    "seq": 5,
    "tool": "file_write",
    "timestamp": "2024-01-01T12:00:00Z",
    "drift_delta": 15.5,
    "prev_drift_delta": 2.1,
    "reason": "path_changed",
    "trace_source": "path",
    "trace_completeness": "complete",
    "baseline_strategy": "median",
    "baseline_window": [1, 10]
  }
}
```

---

## Baseline Strategies

The drift engine supports multiple baseline strategies for robustness:

### 1. FIRST_OCCURRENCE (Default)

- Uses first occurrence as baseline
- Simple and fast
- Vulnerable to outlier contamination

### 2. MEDIAN

- Uses median value across baseline window
- Robust to outliers
- Good for numeric parameters

### 3. PERCENTILE

- Uses percentile value (configurable, default: 50th)
- Configurable robustness
- Good for skewed distributions

### 4. SEGMENTED

- Builds baselines per segment
- Auto-segments by inflection points or fixed window
- Good for multi-phase runs

**Configuration**:
```yaml
validators:
  post_run_drift:
    config:
      baseline_strategy: median  # first_occurrence, median, percentile, segmented
      baseline_percentile: 50.0  # For percentile strategy
      baseline_segment_window: 20  # For segmented strategy
```

---

## Configuration

### PostRunDriftValidator Config

```yaml
validators:
  post_run_drift:
    enabled: true
    enforcement: warn  # Always warns, never blocks
    config:
      drift_threshold: 0.1
      report_inflection_points: true
      report_all_drift: false
      baseline_strategy: median
      baseline_percentile: 50.0
      baseline_segment_window: 20
```

### DriftConfig

The underlying `DriftConfig` supports:

- **ignore_fields**: Fields to ignore during normalization
- **tool_ignore_fields**: Tool-specific ignore fields
- **unordered_set_fields**: Fields treated as unordered sets
- **normalize_paths**: Path normalization (default: true)
- **magnitude_thresholds**: Thresholds for magnitude changes
- **baseline_strategy**: Baseline generation strategy
- **baseline_percentile**: Percentile for percentile baseline
- **baseline_segment_window**: Window size for segmented baseline

---

## Usage

### Post-Run Analysis

```python
# After run completion
from failcore.core.validate.contracts import Context
from failcore.core.validate.bootstrap import auto_register
from failcore.core.validate.engine import ValidationEngine
from failcore.core.validate.loader import load_merged_policy

auto_register()
policy = load_merged_policy()
engine = ValidationEngine(policy=policy)

context = Context(
    tool="post_run_analysis",
    params={},
    state={
        "trace_source": "path",
        "trace_path": "path/to/trace.jsonl",
    },
)

decisions = engine.evaluate(context)
# Returns DecisionV1 objects for inflection points and high drift points
```

### CLI Usage

```bash
# Drift is analyzed as part of post-run validation
failcore validate --trace path/to/trace.jsonl
```

---

## Best Practices

1. **Use median/percentile baselines**: More robust than first_occurrence
2. **Enable inflection point reporting**: Most useful for incident analysis
3. **Provide trace_source explicitly**: Prevents ambiguity in input selection
4. **Check trace_completeness**: Ensure complete traces for reliable analysis
5. **Review inflection points**: Often precede policy violations or cost explosions

## Relationship to Other Systems

- **Policy Engine**: Drift is informational; policy decides enforcement
- **Validation System**: Drift validator outputs DecisionV1 for audit
- **Replay System**: Drift annotations rendered as part of incident timeline
- **DLP/Semantic/Taint**: Independent (drift is post-run analysis, not runtime)

Drift detection is a **post-run analysis tool** that helps identify behavioral changes for audit and incident analysis.