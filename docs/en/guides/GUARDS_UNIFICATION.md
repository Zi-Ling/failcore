# Guards Unification Guide

This guide documents the unification of FailCore's guard modules (DLP, Semantic, Taint, Drift) into a cohesive, production-ready validation system. It covers the implementation steps, optimizations, and key features of each module.

## Table of Contents

1. [Overview](#overview)
2. [Implementation Steps](#implementation-steps)
3. [Optimizations](#optimizations)
4. [Additional Enhancements](#additional-enhancements)
5. [Summary](#summary)

---

## Overview

The Guards Unification project unified four independent guard modules into a single, policy-driven validation system:

- **DLP (Data Loss Prevention)**: Detects and prevents sensitive data leakage
- **Semantic Intent Guard**: High-confidence detection of malicious patterns
- **Taint Tracking**: Lightweight data flow tracking across tool boundaries
- **Drift Detection**: Post-run analysis of behavioral changes

### Key Achievements

- ✅ Unified decision model: All guards output `DecisionV1` objects
- ✅ Policy-driven: All validators read configuration from Policy
- ✅ Single source of truth: Rules defined in `rules/`, guards import from there
- ✅ Clear boundaries: DLP vs Semantic vs Security validators
- ✅ Context-aware: Taint context available via `Context.state`
- ✅ Post-run support: Drift validator for audit/replay analysis
- ✅ Production-ready: Robust baselines, structured redaction, high-confidence detection

---

## Implementation Steps

### Step 1: Unify System Boundaries (Cross-module Foundation)

#### Step 1.1: Unified Decision Model & Evidence Structure ✅

**Status**: ✅ Completed

**Implementation**:
- Created `failcore/core/guards/convert.py` with unified conversion functions:
  - `dlp_action_to_decision_outcome()`: Convert DLPAction to DecisionOutcome
  - `verdict_action_to_decision_outcome()`: Convert VerdictAction to DecisionOutcome
  - `data_sensitivity_to_risk_level()`: Convert DataSensitivity to RiskLevel
  - `dlp_policy_to_decision()`: Convert DLPPolicy to DecisionV1
  - `semantic_verdict_to_decision()`: Convert SemanticVerdict to List[DecisionV1]

**Key Features**:
- All guard-specific verdicts/decisions can now be converted to unified DecisionV1 format
- Supports evidence mapping (pattern_id, sensitivity, risk_level_source, etc.)
- Handles requires_approval, remediation, tags

**Files Created**:
- `failcore/core/guards/convert.py`

---

#### Step 1.2: Unified Naming & Responsibilities ✅

**Status**: ✅ Completed

**Implementation**:
- Renamed `DLPMiddleware` in `failcore/core/guards/taint/middleware.py` to `TaintMiddleware`
- Added backward compatibility alias: `DLPMiddleware = TaintMiddleware`
- Updated docstrings to clarify responsibilities:
  - `TaintMiddleware`: ONLY for marking data sources and tracking taint propagation
  - `DLPMiddleware` (in `guards.dlp.middleware`): For policy enforcement (block/sanitize/warn)
- Updated `failcore/core/guards/taint/__init__.py` to export `TaintMiddleware`

**Key Changes**:
- `taint/middleware.py`: `DLPMiddleware` → `TaintMiddleware` (with backward compat alias)
- Clarified call order: `TaintMiddleware` (mark) → `DLPMiddleware` (enforce policy)
- Added documentation on responsibility boundaries

**Files Modified**:
- `failcore/core/guards/taint/middleware.py`
- `failcore/core/guards/taint/__init__.py`

---

#### Step 1.3: Migrate Rule Definitions to rules/ and Establish Single Registry ✅

**Status**: ✅ Completed

**Implementation**:
- Moved all pattern definitions from `guards/dlp/patterns.py` to `rules/dlp.py`
- Moved all rule definitions from `guards/semantic/rules.py` to `rules/semantic.py`
- Updated `guards/dlp/patterns.py` and `guards/semantic/rules.py` to re-export from `rules/`
- Updated all `guards/*` modules to import from `rules/*`
- Added version/source tracking to registries:
  - `SensitivePattern`: Added `source`, `version`, `metadata`, `signature`, `trust_level`
  - `SemanticRule`: Added `source`, `version`, `metadata`, `signature`, `trust_level`
  - `DLPPatternRegistry`: Added `get_patterns_by_source()` method
  - `RuleRegistry`: Added `get_by_source()` method

**Key Features**:
- `rules/` is now the single source of truth (SSOT) for all rule/pattern definitions
- All guards and enrichers import from `rules/`
- Backward compatibility maintained via re-exports in `guards/*`
- Version and source tracking enables future community rules, diff, audit, signing

**Files Modified**:
- `failcore/core/rules/dlp.py` (migrated from `guards/dlp/patterns.py`)
- `failcore/core/rules/semantic.py` (migrated from `guards/semantic/rules.py`)
- `failcore/core/guards/dlp/patterns.py` (now re-exports from `rules/`)
- `failcore/core/guards/semantic/rules.py` (now re-exports from `rules/`)
- `failcore/core/guards/semantic/__init__.py`
- `failcore/core/guards/semantic/middleware.py`
- `failcore/core/guards/semantic/detectors.py`

---

### Step 2: Integrate with New Validation System

#### Step 2.1: Convert DLP to BaseValidator ✅

**Status**: ✅ Completed

**Implementation**:
- Created `DLPGuardValidator` in `failcore/core/validate/builtin/dlp.py`
- Implements `BaseValidator` interface
- Reads DLP configuration from Policy
- Integrates with taint tracking system
- Scans parameters for sensitive patterns using `DLPPatternRegistry`
- Applies DLP policy via `PolicyMatrix`
- Converts to unified `Decision` objects
- Registered in `bootstrap.py`

**Key Features**:
- Policy-driven: Configuration comes from Policy, not hardcoded
- Taint-aware: Uses taint tracking when available
- Pattern-based: Scans for sensitive patterns in parameters
- Unified output: Returns `DecisionV1` objects compatible with validation engine
- Supports active/shadow/breakglass enforcement modes
- Structured sanitization: Full integration with `StructuredSanitizer`

**Files Created**:
- `failcore/core/validate/builtin/dlp.py`

**Files Modified**:
- `failcore/core/validate/bootstrap.py` (registered DLPGuardValidator)

---

#### Step 2.2: Convert Semantic to BaseValidator ✅

**Status**: ✅ Completed

**Implementation**:
- Created `SemanticIntentValidator` in `failcore/core/validate/builtin/semantic.py`
- Implements `BaseValidator` interface
- Clarified responsibility boundaries:
  - **Semantic**: Intent-based/combinatorial risks (dangerous command combos, param pollution, injection payloads)
  - **DLP**: Sensitive data leakage
  - **Security validators**: Path traversal, SSRF
- Wraps `SemanticDetector` as validator
- Supports category-based enable/disable via policy
- Supports severity-based filtering
- Converts `SemanticVerdict` to unified `Decision` objects
- Registered in `bootstrap.py`

**Key Features**:
- Policy-driven: Configuration from Policy
- Category-based filtering: Enable/disable specific rule categories
- Unified output: Returns `DecisionV1` objects
- Clear boundaries: Focuses on intent/combinatorial risks, not data leakage
- Deterministic parsing: Integrates parsers for structured evaluation

**Files Created**:
- `failcore/core/validate/builtin/semantic.py`

**Files Modified**:
- `failcore/core/validate/bootstrap.py` (registered SemanticIntentValidator)

---

#### Step 2.3: Convert Taint to Context Provider + Optional Validator ✅

**Status**: ✅ Completed

**Implementation**:
- Created `TaintFlowValidator` in `failcore/core/validate/builtin/taint_flow.py`
- Taint context is provided via `Context.state["taint_context"]` (run-level state)
- Lightweight validator that only emits decisions when violations detected
- Detects "sensitive data flows to high-risk sink"
- Configurable via policy
- Always emits WARN decisions (not blocking) for taint flow violations
- DLP validator can depend on taint info from context state
- Registered in `bootstrap.py`

**Key Features**:
- Context provider: TaintContext available via `Context.state`
- Optional validator: Only enabled when needed via policy
- Policy-driven: Configuration from Policy
- Non-blocking: Emits WARN decisions for audit, not BLOCK
- Evidence-rich: Includes source tools, step IDs, sensitivity levels
- Auto-detection: Heuristic field_path detection with confidence levels

**Files Created**:
- `failcore/core/validate/builtin/taint_flow.py`

**Files Modified**:
- `failcore/core/validate/bootstrap.py` (registered TaintFlowValidator)

---

#### Step 2.4: Integrate Drift into Audit/Validation Chain ✅

**Status**: ✅ Completed

**Implementation**:
- Created `PostRunDriftValidator` in `failcore/core/validate/builtin/drift.py`
- Post-run validator (not runtime gate)
- Accepts trace via `Context.state["trace_path"]` or `Context.state["trace_events"]`
- Uses `compute_drift()` from `replay.drift` module
- Outputs decisions for inflection points and high drift points
- Converts drift analysis to unified `Decision` objects
- Provides drift score, inflection points, annotations in evidence
- Registered in `bootstrap.py`

**Key Features**:
- Post-run: Processes trace after execution
- Policy-driven: Configuration from Policy
- Unified output: Returns `DecisionV1` objects compatible with validation engine
- Evidence-rich: Includes drift scores, change details, inflection reasons
- Audit-ready: Decisions can be written to audit report
- Input standardization: `trace_source` enum and `trace_completeness` checking

**Files Created**:
- `failcore/core/validate/builtin/drift.py`

**Files Modified**:
- `failcore/core/validate/bootstrap.py` (registered PostRunDriftValidator)

---

### Step 3: Fill Critical Capability Gaps (Make Them More Trustworthy/Usable)

#### Step 3.1: Drift - Upgrade Baseline Strategy ✅

**Status**: ✅ Completed

**Implementation**:
- Enhanced `baseline.py` with multiple baseline strategies:
  - `FIRST_OCCURRENCE`: Use first occurrence (default, simple)
  - `MEDIAN`: Use median value (robust to outliers)
  - `PERCENTILE`: Use percentile value (configurable)
  - `SEGMENTED`: Build baselines per segment (auto-segment by inflection points or fixed window)
- Added baseline configuration to `DriftConfig`
- Updated `compute_drift()` to support two-pass approach for segmented baselines
- Baseline metadata now includes strategy and window information

**Key Features**:
- Robust baselines: Median/percentile strategies resist outlier contamination
- Segmented baselines: Auto-segment by inflection points or fixed windows
- Configurable: All strategies exposed via `DriftConfig`
- Metadata-rich: Baseline strategy and window included in output for explainability

**Files Modified**:
- `failcore/core/replay/drift/baseline.py` - Enhanced with multiple strategies
- `failcore/core/replay/drift/config.py` - Added baseline strategy configuration
- `failcore/core/replay/drift/__init__.py` - Updated to support two-pass baseline building

---

#### Step 3.2: DLP - Structured Redaction ✅

**Status**: ✅ Completed

**Implementation**:
- Created `StructuredSanitizer` in `failcore/core/guards/dlp/sanitizer.py`
- Separated evidence summaries from output sanitization
- Structured path-based redaction (JSON key paths)
- Category-specific masking (email, payment card, API keys, etc.)
- Usability-preserving options (preserve domain, preserve last4)
- Irreversible sanitization: Full redaction mode completely masks data

**Key Features**:
- Evidence-safe: Summaries never contain full sensitive data
- Structured: JSON path-based redaction for precise control
- Category-aware: Different masking strategies per data type
- Usability-preserving: Optional preservation of partial data for tool functionality
- Irreversible: Full redaction mode ensures data cannot be recovered

**Files Created**:
- `failcore/core/guards/dlp/sanitizer.py` - Structured sanitizer implementation

**Integration Points**:
- Fully integrated into `DLPGuardValidator` for policy-driven sanitization
- Evidence summaries used in `Decision.evidence` without exposing sensitive data

---

#### Step 3.3: Semantic - High-Confidence Combinator ✅

**Status**: ✅ Completed

**Implementation**:
- Created deterministic parsers in `failcore/core/guards/semantic/parsers.py`:
  - **ShellParser**: Shell command tokenization using `shlex`
  - **SQLParser**: SQL keyword extraction and structure analysis
  - **URLParser**: URL normalization and internal host detection
  - **PathParser**: Path normalization and traversal detection
  - **PayloadParser**: Structured payload parsing (JSON)
- Two-layer approach: Deterministic parsing → Rule evaluation
- Reduces false positives: Structured parsing eliminates regex-only matching issues

**Key Features**:
- Deterministic parsing: Shell tokenization, SQL keyword extraction, URL/Path normalization
- Structured evaluation: Rules operate on parsed structures, not raw strings
- High confidence: Reduces false positives compared to regex-only matching
- Extensible: New parsers can be added for other payload types

**Files Created**:
- `failcore/core/guards/semantic/parsers.py` - Deterministic parsers

**Integration Points**:
- Integrated into `SemanticIntentValidator` for high-confidence detection
- Rules can use parsed structures instead of raw string matching

---

#### Step 3.4: Taint - Minimal Propagation Model & Flow Chain ✅

**Status**: ✅ Completed

**Implementation**:
- Created `TaintFlowTracker` in `failcore/core/guards/taint/flow.py`
- Minimal propagation model: Tracks taint flow edges (source_step_id -> sink_step_id)
- Flow chain tracking: `get_flow_chain()` for complete flow chains
- Evidence generation: Includes taint tags, flow chains, source steps, field paths
- Auto-detection: Heuristic field_path detection with confidence levels

**Key Features**:
- Cross-tool boundary tracking: Tracks data flow from tool A to tool B
- Flow chain visibility: Shows complete data lineage
- Field-level tracking: Optional JSON path tracking for structured data
- Evidence-rich: Provides complete flow information for DLP explanations
- Minimal overhead: Lightweight model, not full program analysis
- Confidence-aware: Auto-detection with high/medium/low confidence levels

**Files Created**:
- `failcore/core/guards/taint/flow.py` - Taint flow tracking

**Integration Points**:
- Can be integrated into `TaintContext` or `TaintStore` for automatic flow tracking
- Evidence can be included in `Decision.evidence` to show taint flow chains
- UI can display data lineage/graph using flow chain information

---

### Step 4: Make Them Production-Ready (Usability, Not Just Features)

#### Step 4.1: Unified Policy Explain Simulation Entry ✅

**Status**: ✅ Completed

**Implementation**:
- Enhanced `DecisionExplanation` class in `failcore/core/validate/explain.py`:
  - Added `triggered_validators` tracking
  - Added `enforcement_mode` property (shows effective enforcement after policy merge)
  - Added `get_validator_details()` method
  - Added `get_rule_evidence()` method
  - Enhanced `get_summary()` with hierarchical output (concise/verbose)
- Updated `explain()` CLI command in `failcore/cli/commands/policy_cmd.py`:
  - Uses merged policy (active + shadow + breakglass)
  - Creates enhanced explanation with policy and triggered validators
  - Displays comprehensive summary with all details
  - Shows which validators would trigger before running agent
  - Shows evidence for each rule
  - Shows final enforcement mode after policy merge

**Key Features**:
- Pre-run simulation: Users can test tool calls before running agent
- Comprehensive output: Lists validators, rules, evidence, enforcement
- Policy-aware: Shows effective enforcement after merge
- Shareable: Output can be pasted into issues/PRs for discussion
- Reduces trial friction: Users see risks upfront
- Hierarchical output: Summary → Details → Evidence (with `--verbose` flag)

**Files Modified**:
- `failcore/core/validate/explain.py` - Enhanced with validator details and enforcement mode
- `failcore/cli/commands/policy_cmd.py` - Updated explain command to use enhanced explanation

---

#### Step 4.2: Gate and Enricher Scan Deduplication ✅

**Status**: ✅ Completed

**Implementation**:
- Created `ScanCache` in `failcore/core/guards/scan_cache.py`:
  - Hash-based deduplication: Computes SHA256 hash of payload
  - Result storage: Stores scan results with hash key
  - Step association: Links scan results to step_id for trace
  - Scanner type filtering: Supports multiple scanner types (dlp, semantic, taint)
  - Run-scoped isolation: Supports `run_id` for proper isolation
  - TTL and LRU eviction: Controls memory usage
- Updated `DLPGuardValidator` and `DLPEnricher` to use scan cache

**Key Features**:
- Deduplication: Same payload scanned only once
- Consistency: Gate and enricher use same results
- Performance: Reduces redundant regex scanning
- Audit trail: Scan hash in evidence for traceability
- Evidence channel: Results stored in trace for enricher reuse
- Run-scoped: Prevents cross-run contamination

**Files Created**:
- `failcore/core/guards/scan_cache.py` - Scan cache implementation

**Files Modified**:
- `failcore/core/validate/builtin/dlp.py` - Uses scan cache for parameter scanning
- `failcore/core/egress/enrichers/dlp.py` - Uses scan cache for evidence scanning

---

## Optimizations

### 1. Unified DecisionV1 as Single Source of Truth ✅

**Problem**: Multiple verdict types (SemanticVerdict, DLPPolicy) were still used in internal flows, creating dual-track systems.

**Solution**: 
- All validators now output DecisionV1 exclusively
- Convert functions in `convert.py` ensure all guard outputs are standardized
- Middleware/enricher boundaries enforce conversion to DecisionV1
- Old verdict types are now internal-only intermediate states

**Impact**: Eliminates dual-track confusion, ensures consistent decision format across all systems.

---

### 2. Decision Deduplication and Domain Priority ✅

**Problem**: Multiple validators (DLP, Semantic, Security) could detect the same issue, leading to duplicate alerts.

**Solution**:
- Created `deduplication.py` module with domain priority system
- Priority order: security (100) > dlp (80) > semantic (60) > taint_flow (40) > drift (20)
- Engine automatically deduplicates decisions after validation
- Lower-priority duplicates are marked with suppression metadata

**Files Created**:
- `failcore/core/validate/deduplication.py` - Deduplication logic

**Files Modified**:
- `failcore/core/validate/engine.py` - Calls deduplication after validation

**Impact**: Users see one clear decision per issue, not multiple confusing duplicates.

---

### 3. ScanCache Lifecycle and Isolation ✅

**Problem**: Global cache could cause cross-run contamination and unbounded memory growth.

**Solution**:
- ScanCache now supports run-scoped instances via `run_id`
- Added TTL support and LRU eviction
- `get_or_create_cache()` prioritizes context-based cache over global
- Cache stored in `Context.state["scan_cache"]` for proper isolation

**Files Modified**:
- `failcore/core/guards/scan_cache.py` - Added run_id, TTL, LRU eviction
- `failcore/core/validate/builtin/dlp.py` - Uses run-scoped cache
- `failcore/core/egress/enrichers/dlp.py` - Uses run-scoped cache

**Impact**: Prevents cross-run contamination, controls memory usage, ensures proper isolation.

---

### 4. PostRunDriftValidator Input Standardization ✅

**Problem**: Drift validator accepted both `trace_path` and `trace_events` without clear priority.

**Solution**:
- Added `trace_source` enum in context state: "path", "events", "auto"
- Explicit priority: `trace_source` setting > explicit path > explicit events
- Trace completeness checking: "complete", "partial", "unknown"
- All decisions include `trace_source` and `trace_completeness` in evidence

**Files Modified**:
- `failcore/core/validate/builtin/drift.py` - Standardized input handling

**Impact**: Audit results are now self-documenting and trustworthy, with clear trace provenance.

---

### 5. StructuredSanitizer Integration with DLPGuardValidator ✅

**Problem**: StructuredSanitizer was implemented but not fully integrated.

**Solution**:
- DLPGuardValidator now uses StructuredSanitizer when policy requires SANITIZE action
- Sanitization config in policy: `sanitize.enabled`, `sanitize.mode`, `sanitize.paths`
- Evidence records sanitization: `sanitization_performed`, `redaction_mode`, `paths_sanitized`
- Sanitized params stored in decision evidence for audit

**Files Modified**:
- `failcore/core/validate/builtin/dlp.py` - Full sanitizer integration

**Impact**: Sanitization is now policy-driven and fully functional, with clear audit trail.

---

### 6. TaintFlowTracker Auto-Detection Strategy ✅

**Problem**: Taint flow tracking required explicit field_path, causing frequent chain breaks.

**Solution**:
- Added `_auto_detect_field_path_with_confidence()` with heuristics:
  - Fields containing step_id references (high confidence)
  - Common field names (medium confidence)
  - Nested structure traversal (medium confidence)
- `track_flow()` now accepts optional `params` for auto-detection
- Evidence includes `binding_confidence` (high/medium/low)

**Files Modified**:
- `failcore/core/guards/taint/flow.py` - Auto-detection heuristics

**Impact**: Taint flow chains are more stable and useful in production scenarios.

---

### 7. SemanticIntentValidator Parser Integration ✅

**Problem**: Parsers were implemented but not used by SemanticDetector.

**Solution**:
- SemanticIntentValidator now parses parameters deterministically
- Creates unified AST: `shell_ast`, `sql_features`, `url_norm`, `path_norm`, `payload`
- Parsed structures added to decision evidence
- Rules can evaluate structured data instead of raw strings

**Files Modified**:
- `failcore/core/validate/builtin/semantic.py` - Parser integration

**Impact**: Semantic detection is more accurate and less prone to false positives.

---

### 8. Hierarchical Explain Output ✅

**Problem**: Explain output was too verbose, overwhelming users with information.

**Solution**:
- Three-tier output: Summary (concise) → Details (per-validator) → Evidence (full)
- Default CLI output shows summary + top 3 reasons
- `--verbose` flag shows full details
- UI can use collapsible panels for each tier

**Files Modified**:
- `failcore/core/validate/explain.py` - Hierarchical output methods
- `failcore/cli/commands/policy_cmd.py` - Added `--verbose` flag

**Impact**: Explain is now readable and useful, not overwhelming.

---

### 9. Breakglass Audit Trail ✅

**Problem**: Breakglass activation lacked audit trail, making it a "hidden backdoor" in audits.

**Solution**:
- Created `audit.py` module with `BreakglassAuditRecord`
- Records: who, when, why, TTL, token used, affected decisions
- Explain output shows breakglass status and audit info
- Audit logger tracks all breakglass activations

**Files Created**:
- `failcore/core/validate/audit.py` - Audit trail system

**Files Modified**:
- `failcore/core/validate/explain.py` - Shows breakglass audit info

**Impact**: Breakglass is now fully auditable and transparent, not a hidden backdoor.

---

### 10. Registry Signature and Trust Level ✅

**Problem**: No way to verify rule/pattern source or trust level, blocking community rules adoption.

**Solution**:
- Added `signature` field (SHA256 checksum) to `SensitivePattern` and `SemanticRule`
- Added `trust_level` field: "trusted", "untrusted", "unknown"
- Source field already exists: "builtin", "community", "local"
- UI/CLI can display trust indicators

**Files Modified**:
- `failcore/core/rules/dlp.py` - Added signature and trust_level
- `failcore/core/rules/semantic.py` - Added signature and trust_level

**Impact**: Enables safe adoption of community rules with clear trust indicators.

---

## Additional Enhancements

### 1. Decision Deduplication Explanatory Metadata ✅

**Implementation**:
- Added `suppressed_by` field: References the primary decision code that suppressed this one
- Added `suppression_reason`: "duplicate_domain_lower_priority" (structured reason)
- Added `suppression_explanation`: Human-readable explanation with domain priority comparison
- Maintained backward compatibility with `duplicate_of` field

**Impact**: Users can now clearly see why a decision was suppressed: "not detected, but absorbed by higher priority domain"

---

### 3. Taint Auto-Detection Confidence Feedback Loop ✅

**Implementation**:
- Added `binding_confidence` field: "high" (explicit field_path), "medium" (heuristic match), "low" (weak match)
- `_auto_detect_field_path_with_confidence()` returns both path and confidence
- Evidence includes `binding_confidence` for all taint flow decisions
- Explain concise view filters out low-confidence flows (shown in verbose only)

**Impact**: Users see only high/medium confidence flows by default, avoiding "scary but uncertain" false positives. Future enhancements (schema-aware, adapter-aware) can use the same confidence interface.

---

### 5. Breakglass Impact Assessment ✅

**Implementation**:
- Created `BreakglassImpact` class to assess breakglass effects
- Tracks affected validators and downgraded decisions
- `get_explain_text()` provides human-readable impact summary
- Explain output shows: affected validators, downgraded decision count, impact summary

**Files Created**:
- `failcore/core/validate/breakglass_impact.py` - Impact assessment module

**Impact**: Users can now see exactly what breakglass affected: "X BLOCK decisions downgraded to WARN", making breakglass usage transparent and auditable.

---

## Summary

All implementation steps and optimizations have been completed, transforming the guards system from independent modules into a unified, production-ready validation framework.

### New Validators Created

1. **DLPGuardValidator** (`builtin/dlp.py`): DLP policy enforcement
2. **SemanticIntentValidator** (`builtin/semantic.py`): Intent-based security validation
3. **TaintFlowValidator** (`builtin/taint_flow.py`): Taint flow detection
4. **PostRunDriftValidator** (`builtin/drift.py`): Post-run drift analysis

### Key Features

- ✅ Unified decision model: All guards output `DecisionV1` objects
- ✅ Policy-driven: All validators read configuration from Policy
- ✅ Single source of truth: Rules defined in `rules/`, guards import from there
- ✅ Clear boundaries: DLP vs Semantic vs Security validators
- ✅ Context-aware: Taint context available via `Context.state`
- ✅ Post-run support: Drift validator for audit/replay analysis
- ✅ Robust baselines: Multiple baseline strategies (median, percentile, segmented)
- ✅ Structured redaction: Evidence-safe summaries + path-based sanitization
- ✅ High-confidence detection: Deterministic parsing + structured rule evaluation
- ✅ Flow tracking: Cross-tool boundary taint propagation with evidence chains
- ✅ Pre-run simulation: Policy explain shows risks before agent execution
- ✅ Scan deduplication: Gate and enricher share results, no duplicate scanning
- ✅ Decision deduplication: Domain priority system prevents duplicate alerts
- ✅ Explainability: Hierarchical output, suppression metadata, breakglass impact

### Integration Points

- All validators registered in `bootstrap.py`
- Support active/shadow/breakglass enforcement modes
- Compatible with `ValidationEngine` and `failcore policy` CLI
- Evidence structure unified for UI/report/audit consumption

For detailed information on each module, see:
- [DLP Module Documentation](../contracts/DLP.md)
- [Semantic Module Documentation](../contracts/SEMANTIC.md)
- [Taint Module Documentation](../contracts/TAINT.md)
- [Drift Module Documentation](../contracts/DRIFT.md)
