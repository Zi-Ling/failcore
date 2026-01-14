# FailCore Architecture - Directory Structure

This document provides a complete overview of FailCore's directory structure, with each module's purpose and responsibility.

## Table of Contents

- [Project Root](#project-root)
- [Core Modules](#core-modules)
- [CLI & UI](#cli-ui)
- [Infrastructure](#infrastructure)
- [Adapters](#adapters)
- [Other Components](#other-components)

---

## Project Root

```
failcore/
├── api/          # Public API surface for SDK integration
├── core/         # Core execution engine and safety systems
├── cli/          # Command-line interface
├── infra/        # Infrastructure layer (storage, logging, observability)
├── adapters/     # Framework integrations (LangChain, MCP, etc.)
├── hooks/        # Runtime patches for stdlib interception
├── presets/      # Pre-configured tool packs and policies
├── utils/        # Shared utilities
└── web/          # Web UI and API server
```

---

## Core Modules

The `core/` directory contains the heart of FailCore's execution engine, safety systems, and observability primitives.

### Core Overview

**Purpose**: FailCore's execution engine combines tool orchestration, multi-layer safety gates, cost control, and evidence collection into a unified runtime. It enables observable, replayable, and policy-governed tool execution with zero-code integration through proxy mode.

**Key Design Principles**:
1. **Dual Boundary Model**: Preflight gate (tool boundary) + Egress gate (proxy boundary)
2. **Evidence-First**: All decisions produce auditable trace events
3. **Fail-Open Default**: System degrades gracefully, never blocks on internal errors
4. **Homogeneous Events**: Same event schema regardless of entry point

```
core/
├── rules/           # Neutral rule definitions (shared by gates & enrichers)
├── events/          # Unified event model (ATTEMPT/EGRESS)
├── gate/            # Abstract gate interface (decision authority)
├── guards/          # Preflight guards (tool boundary protection)
├── egress/          # Post-execution egress system (evidence collection)
├── executor/        # Tool execution pipeline
├── cost/            # Cost tracking and budget enforcement
├── replay/          # Blackbox replay engine
├── policy/          # Policy engine (permission boundaries)
├── contract/        # Contract validation
├── audit/           # Audit analysis
├── validate/        # Schema validation
├── proxy/           # Proxy server components
├── trace/           # Trace management
├── tools/           # Built-in tool implementations
└── [other modules]
```

---

### core/rules/ - Neutral Rule Definitions

**Purpose**: Shared rule layer that provides pattern definitions, semantic rules, and side-effect types. This layer sits below both guards (active defense) and enrichers (passive evidence), ensuring consistent rule interpretation across decision and audit boundaries.

**Architecture Constraint**: Rules are dependency-neutral declarative data. Both gates and enrichers import from this layer, never from each other.

```
rules/
├── __init__.py      # Unified rule exports
├── dlp.py          # DLP pattern definitions (re-exported from guards)
├── semantic.py     # Semantic rule definitions (re-exported from guards)
├── effects.py      # Side-effect type definitions (re-exported from guards)
└── schemas.py      # Unified field schemas (TargetSchema, VerdictSchema, EvidenceSchema)
```

**Key Components**:
- `DLPPatternRegistry`: Centralized sensitive data patterns (API keys, PII, secrets)
- `SemanticRule`: High-confidence malicious pattern definitions
- `SideEffectType`: Filesystem/network/execution effect types
- `TargetSchema`: Unified target schema with `inferred` (pre-execution) and `observed` (post-execution)
- `VerdictSchema`: Gate decision structure
- `EvidenceSchema`: Enricher finding structure

---

### core/events/ - Unified Event Model

**Purpose**: Canonical event types that ensure homogeneous trace structure across both preflight gate (tool boundary) and egress gate (proxy boundary). Solves "audit trail断裂" problem by guaranteeing all execution attempts are recorded regardless of verdict.

**Architecture Constraint**: Every execution attempt MUST have stable `attempt_id`. Verdict is inlined in ATTEMPT event (not separate event) for deterministic correlation.

```
events/
├── __init__.py      # Event model exports
├── attempt.py       # ATTEMPT event (pre-execution, written by gates)
├── egress.py        # EGRESS event (post-execution, written after execution)
└── envelope.py      # Trace envelope wrapper (schema: failcore.trace.v0.2.0)
```

**Key Components**:
- `AttemptEvent`: Pre-execution event written by gates BEFORE execution (includes verdict inline)
- `EgressEvent`: Post-execution event written after execution completes (includes enricher evidence)
- `TraceEnvelope`: Consistent wrapper for all trace events
- `EventType`: Event type enum (ATTEMPT, EGRESS, RUN_START, RUN_END, etc.)

**Event Lifecycle**:
- **Preflight mode**: `ATTEMPT_START` → [execution] → `EGRESS`
- **Egress mode**: `ATTEMPT` (combined) → `EGRESS`

---

### core/gate/ - Abstract Gate Interface

**Purpose**: Elevates decision authority from implementation layer (guards) to abstract role (Gate). Solves "proxy mode losing blocking capability" by providing unified gate interface for both preflight (tool boundary) and egress (proxy boundary).

**Architecture Constraint**: Gate is the ONLY entity allowed to write VERDICT. Both gate types share same decision semantics and produce homogeneous ATTEMPT events.

```
gate/
├── __init__.py      # Gate interface exports
├── interface.py     # Abstract Gate protocol (what all gates must implement)
├── preflight.py     # Preflight gate implementation (tool call boundary)
└── egress.py        # Egress gate implementation (proxy boundary)
```

**Key Components**:
- `Gate`: Abstract protocol defining gate contract
- `GateContext`: Context passed to gate for decision making
- `GateVerdict`: Gate decision result (ALLOW/BLOCK/SANITIZE/WARN)
- `PreflightGate`: Tool boundary gate (wraps existing guards)
- `EgressGate`: Proxy boundary gate (provides blocking capability for drop-in mode)

---

### core/guards/ - Preflight Guards

**Purpose**: Active defense at tool call boundary. Intercepts tool calls before execution to enforce policies, detect malicious patterns, prevent data leakage, and check boundary violations.

**Note**: Guards implement preflight gate. For unified gate interface, use `core/gate/PreflightGate`.

```
guards/
├── dlp/             # Data Loss Prevention
│   ├── __init__.py
│   ├── patterns.py  # Pattern definitions (migrating to core/rules)
│   ├── policies.py  # DLP policy matrix (ALLOW/BLOCK/SANITIZE/WARN_APPROVAL_NEEDED)
│   └── middleware.py # DLP middleware for tool calls
├── semantic/        # Semantic intent validation
│   ├── __init__.py
│   ├── rules.py     # Semantic rule definitions (migrating to core/rules)
│   ├── detectors.py # Pattern detectors
│   ├── verdict.py   # Verdict models
│   └── middleware.py # Semantic guard middleware
├── effects/         # Side-effect boundary enforcement
│   ├── __init__.py
│   ├── boundary.py  # Boundary definitions
│   ├── detection.py # Side-effect detection heuristics
│   ├── events.py    # Side-effect event models
│   ├── gate.py      # Boundary gate
│   ├── side_effect_auditor.py # Crossing detection
│   └── side_effects.py # Side-effect types (migrating to core/rules)
└── taint/           # Data tainting and tracking
    ├── __init__.py
    ├── tag.py       # Taint tag models (TaintSource, DataSensitivity)
    ├── context.py   # Taint tracking context
    ├── store.py     # Taint storage
    └── sanitizer.py # Data sanitization
```

**Key Responsibilities**:
- **DLP**: Block/sanitize sensitive data (API keys, PII, secrets) from leaving system
- **Semantic**: Detect high-confidence malicious patterns (secret leakage, parameter pollution)
- **Effects**: Enforce side-effect boundaries (filesystem scope, network egress, execution limits)
- **Taint**: Track data origins for attribution (user/model/tool/system)

**Architecture Notes**:
- Guards write VERDICT to ATTEMPT events
- Guards NEVER write EVIDENCE (that's enrichers' job)
- DLP `REQUIRE_APPROVAL` downgraded to `WARN_APPROVAL_NEEDED` (no control plane yet)

---

### core/egress/ - Egress System

**Purpose**: Post-execution egress pipeline that collects evidence, enriches events, and writes to trace sinks. Provides unified observation point for all tool executions regardless of how they were invoked.

**Architecture Constraint**: Enrichers write EVIDENCE ONLY, never VERDICT. Evidence is supplementary information for audit and does not influence gates (gates already decided).

```
egress/
├── __init__.py
├── engine.py        # Egress engine orchestrator
├── adapters.py      # Adapter for various event sources
├── policy.py        # Egress policies
├── types.py         # Egress event types
├── enrichers/       # Evidence enrichers (post-execution analysis)
│   ├── __init__.py
│   ├── dlp.py       # DLP scanning (pattern detection + redaction)
│   ├── taint.py     # Taint attribution (data source inference)
│   ├── semantic.py  # Semantic pattern annotation
│   ├── effects.py   # Side-effect annotation (type/target/category)
│   └── usage.py     # Usage tracking (tokens, cost, duration)
└── sinks/           # Trace output destinations
    ├── __init__.py
    ├── trace.py     # JSONL trace sink
    └── types.py     # Sink types
```

**Enrichers**:
- **DLP Enricher**: Scans for sensitive patterns, adds findings to evidence, optionally redacts secrets
- **Taint Enricher**: Infers data source (user/model/tool/system) for attribution
- **Semantic Enricher**: Annotates semantic anomaly patterns for audit
- **Effects Enricher**: Annotates side-effect metadata (type, observed target, category)
- **Usage Enricher**: Tracks token usage, cost, duration

**Key Difference from Guards**:
- Guards: Active defense, write VERDICT, can BLOCK
- Enrichers: Passive analysis, write EVIDENCE, never BLOCK

---

### core/executor/ - Tool Execution Pipeline

**Purpose**: Orchestrates tool execution through multi-stage pipeline with failure handling, resource management, validation, and output normalization.

```
executor/
├── __init__.py
├── executor.py      # Main executor entry point
├── pipeline.py      # Execution pipeline orchestrator
├── runner.py        # Tool runner
├── state.py         # Execution state management
├── failure.py       # Failure handling
├── output.py        # Output normalization
├── process.py       # Process execution
├── resources.py     # Resource limits (memory, CPU, disk)
├── validation.py    # Input/output validation
└── stages/          # Pipeline stages
    ├── __init__.py
    ├── preflight.py # Pre-execution checks
    ├── prepare.py   # Parameter preparation
    ├── execute.py   # Core execution
    ├── normalize.py # Output normalization
    ├── postflight.py # Post-execution validation
    ├── contract.py  # Contract checking
    ├── egress.py    # Egress event emission
    └── cleanup.py   # Resource cleanup
```

**Execution Stages**:
1. **Preflight**: Policy checks, cost estimates, boundary validation
2. **Prepare**: Parameter validation and transformation
3. **Execute**: Actual tool invocation with resource limits
4. **Normalize**: Output standardization
5. **Postflight**: Result validation
6. **Contract**: Contract compliance check
7. **Egress**: Event emission to egress engine
8. **Cleanup**: Resource cleanup

---

### core/cost/ - Cost Control System

**Purpose**: Comprehensive cost tracking, estimation, budget enforcement, and usage monitoring for LLM API calls. Provides cost-aware execution with configurable limits and alerts.

```
cost/
├── __init__.py
├── models.py        # Cost data models
├── schemas.py       # Cost schemas
├── pricing.py       # Pricing data for LLM providers
├── registry.py      # Provider registry
├── providers.py     # Provider-specific cost logic
├── estimator.py     # Cost estimation (pre-execution)
├── tracker.py       # Cost tracking (post-execution)
├── guardian.py      # Budget enforcement
├── middleware.py    # Cost middleware
├── execution.py     # Execution cost tracking
├── pipeline.py      # Cost pipeline
├── streaming.py     # Streaming cost tracking
├── ratelimit.py     # Rate limiting
├── alerts.py        # Cost alerts
├── usage.py         # Usage aggregation
└── metadata.py      # Cost metadata
```

**Key Features**:
- Pre-execution cost estimation
- Real-time cost tracking (including streaming)
- Budget enforcement with configurable limits
- Cost alerts and notifications
- Per-run, per-tool, per-model cost breakdown
- Rate limiting

---

### core/replay/ - Blackbox Replay Engine

**Purpose**: Deterministic replay of tool executions from trace for debugging, testing, policy validation, and incident investigation. Supports diff mode, mutation testing, and policy replay.

```
replay/
├── __init__.py
├── engine.py        # Replay engine
├── loader.py        # Trace loading
├── matcher.py       # Fingerprint matching
├── mutator.py       # Replay mutation
├── runner.py        # Replay runner
├── state.py         # Replay state
├── diff.py          # Diff computation
├── policy.py        # Policy replay
├── validator.py     # Replay validation
├── context.py       # Replay context
├── fingerprint.py   # Fingerprint computation
├── models.py        # Replay models
├── normalization.py # Input normalization
├── registry.py      # Replay registry
├── snapshot.py      # State snapshots
├── session.py       # Replay session
├── strategies.py    # Replay strategies
└── types.py         # Replay types
```

**Replay Modes**:
- **Exact replay**: Replay with same inputs, expect same outputs
- **Diff mode**: Compare original vs replay execution
- **Mutation testing**: Replay with input mutations
- **Policy replay**: Re-evaluate policies on historical traces

---

### core/policy/ - Policy Engine

**Purpose**: Permission boundary enforcement using path-based allow/deny rules. Defines what tools can access and prevents out-of-scope operations.

```
policy/
├── __init__.py
├── engine.py        # Policy engine
├── model.py         # Policy models
├── patterns.py      # Path pattern matching
└── verdict.py       # Policy verdicts
```

---

### core/contract/ - Contract Validation

**Purpose**: Input/output schema validation to ensure tool calls conform to declared contracts. Prevents type errors and schema violations.

```
contract/
├── __init__.py
├── model.py         # Contract models
├── checkers.py      # Contract checkers
└── types.py         # Contract types
```

---

### core/audit/ - Audit Analysis

**Purpose**: Analyzes trace events to produce audit reports with risk assessment, policy violations, cost analysis, and evidence summary.

```
audit/
├── analyzer.py      # Audit analyzer
├── model.py         # Audit models
└── taxonomy.py      # Risk taxonomy
```

---

### core/proxy/ - Proxy Server

**Purpose**: HTTP proxy server for zero-code integration. Intercepts LLM API calls, applies gates, and forwards to upstream providers. Enables drop-in replacement via `OPENAI_BASE_URL` environment variable.

```
proxy/
├── __init__.py
├── server.py        # Proxy server (ASGI app)
├── pipeline.py      # Request processing pipeline
├── upstream.py      # Upstream HTTP client
├── stream.py        # Streaming handler
├── app.py           # Proxy application
└── [config in core/config/proxy.py]
```

**Key Features**:
- ASGI-based HTTP server
- Streaming support
- Egress gate integration (blocking capability)
- Transparent forwarding
- Provider detection

---

### core/trace/ - Trace Management

**Purpose**: Trace event collection, writing, and lifecycle management. Ensures all execution attempts produce auditable trace records.

```
trace/
├── __init__.py
├── writer.py        # Trace writer
├── collector.py     # Event collector
├── lifecycle.py     # Trace lifecycle
├── models.py        # Trace models
├── parsing.py       # Trace parsing
├── schema.py        # Trace schema
├── serialization.py # Event serialization
├── streaming.py     # Streaming trace
└── types.py         # Trace types
```

---

### core/tools/ - Built-in Tools

**Purpose**: Standard tool implementations (filesystem, network, execution, etc.) with safety wrappers and observability hooks.

```
tools/
├── __init__.py
├── base.py          # Tool base classes
├── registry.py      # Tool registry
├── [20+ tool implementations]
```

---

### Other Core Modules

```
core/
├── approval/        # Human approval workflow (state: stored, timeout handling)
├── bootstrap/       # System initialization
├── config/          # Configuration models (cost, proxy, guards, boundaries, limits)
├── errors/          # Error codes and exception hierarchy
├── optimizer/       # Cost optimization strategies
├── presets/         # Pre-configured tool packs
├── process/         # Process management
├── receipt/         # Execution receipts
├── retry/           # Retry logic
├── schemas/         # JSON schemas
├── types/           # Type definitions
└── validate/        # Schema validators
```

---

## CLI & UI

### cli/ - Command-Line Interface

**Purpose**: User-facing CLI for running tools, viewing traces, generating reports, and managing FailCore.

```
cli/
├── main.py          # CLI entry point
├── commands/        # CLI commands
│   ├── proxy_cmd.py    # Start proxy server
│   ├── run_cmd.py      # Run tool with policy
│   ├── trace_cmd.py    # Trace operations (ingest, list, show)
│   ├── replay_cmd.py   # Replay traces
│   ├── audit_cmd.py    # Generate audit reports
│   ├── report_cmd.py   # Generate HTML reports
│   ├── show_cmd.py     # Show trace details
│   ├── list_cmd.py     # List runs
│   ├── validate_cmd.py # Validate policies/contracts
│   ├── ui_cmd.py       # Start web UI
│   ├── service_cmd.py  # Service management
│   └── analyze_cmd.py  # Trace analysis
├── renderers/       # Output renderers
│   ├── html/           # HTML renderer (reports, audit)
│   ├── text.py         # Text renderer
│   └── json.py         # JSON renderer
├── views/           # View models
│   ├── trace_report.py # Trace report view
│   ├── audit_report.py # Audit report view
│   ├── trace_show.py   # Trace detail view
│   ├── replay_run.py   # Replay run view
│   └── replay_diff.py  # Replay diff view
└── trace_viewer.py  # Interactive trace viewer
```

### web/ - Web UI

**Purpose**: Web-based UI for visualizing traces, managing policies, reviewing audit reports, and system monitoring.

```
web/
├── app.py           # Web application entry
├── routes/          # HTTP routes (17 route handlers)
├── services/        # Business logic services (19 services)
├── static/          # Static assets (JS, CSS)
├── templates/       # HTML templates (17 templates)
└── view/            # View helpers
```

---

## Infrastructure

### infra/ - Infrastructure Layer

**Purpose**: Cross-cutting infrastructure concerns including storage, logging, observability, and lifecycle management.

```
infra/
├── storage/         # Persistence layer
│   ├── sqlite_store.py  # SQLite database (runs, steps, events)
│   ├── ingest.py        # Trace ingestion
│   ├── trace_writer.py  # Trace file writer
│   └── cost_tables.py   # Cost tables
├── audit/           # Audit output
│   └── writer.py        # Audit JSONL writer
├── observability/   # Observability integration
│   └── otel/            # OpenTelemetry integration
│       ├── configure.py # OTEL configuration
│       ├── mapping.py   # Event mapping
│       └── writer.py    # OTEL writer
├── lifecycle/       # Lifecycle management
│   └── janitor.py       # Cleanup and maintenance
└── logging/         # Logging configuration
```

---

## Adapters

### adapters/ - Framework Integrations

**Purpose**: Integration adapters for popular frameworks, enabling FailCore to work with existing codebases.

```
adapters/
├── langchain/       # LangChain integration
│   ├── wrapper.py      # Tool wrapper
│   ├── detector.py     # LangChain tool detection
│   └── mapper.py       # Event mapping
├── mcp/             # Model Context Protocol integration
│   ├── transport.py    # MCP transport
│   ├── codec.py        # Message encoding/decoding
│   ├── session.py      # Session management
│   ├── security.py     # Security hooks
│   └── egress_integration.py # Egress integration
├── proxy/           # Proxy adapter
│   └── transport.py    # Proxy transport
└── sdk/             # SDK integration
```

---

## Other Components

### api/ - Public API

**Purpose**: High-level Python API for SDK usage. User-facing functions for tool execution, guards, and context management.

```
api/
├── run.py           # Main run() function
├── guard.py         # Guard decorators
├── context.py       # Execution context
├── session.py       # Session management
├── result.py        # Result types
└── presets.py       # Preset configurations
```

### hooks/ - Runtime Patches

**Purpose**: Monkey patches for stdlib to intercept filesystem, network, and process operations for automatic side-effect detection.

```
hooks/
├── httpx_patch.py      # httpx interception
├── requests_patch.py   # requests interception
├── subprocess_patch.py # subprocess interception
└── os_patch.py         # os module interception
```

### presets/ - Presets

**Purpose**: Pre-configured tool packs, policies, and validators for common use cases.

```
presets/
├── tools.py         # Tool presets
├── policies.py      # Policy presets
└── validators.py    # Validator presets
```

### utils/ - Utilities

**Purpose**: Shared utilities for path resolution, process management, and timeouts.

```
utils/
├── paths.py         # Path utilities (.failcore structure)
├── path_resolver.py # Path resolution
├── process.py       # Process helpers
└── timeout.py       # Timeout utilities
```

---

## Architecture Decision Records

### Key Architectural Constraints

1. **Dual Gate Model**: Preflight gate (tool boundary) + Egress gate (proxy boundary) provide unified decision semantics
2. **Verdict vs Evidence**: VERDICT written only by gates, EVIDENCE written only by enrichers (hard boundary)
3. **ATTEMPT Events**: All execution attempts recorded BEFORE execution (solves audit trail gap)
4. **Homogeneous Events**: Same event schema regardless of entry point (framework vs proxy)
5. **Target Duality**: `inferred` (pre-execution) + `observed` (post-execution) with priority: observed > inferred
6. **Neutral Rules**: Rules defined in `core/rules/`, shared by gates and enrichers (no circular dependency)
7. **Fail-Open Default**: System never blocks on internal errors (graceful degradation)

### Migration Notes

- **REQUIRE_APPROVAL** downgraded to **WARN_APPROVAL_NEEDED** (no control plane yet)
- **DLP patterns** migrating from `guards/dlp/patterns` to `core/rules/dlp`
- **Semantic rules** migrating from `guards/semantic/rules` to `core/rules/semantic`
- **Side-effect types** migrating from `guards/effects/side_effects` to `core/rules/effects`

---

## Version History

- **v0.2.0**: Unified event model (ATTEMPT/EGRESS), gate abstraction, rules layer
- **v0.1.3**: Previous trace schema
- **v0.1.2**: Legacy trace schema

---

**Document Status**: Living document, updated as architecture evolves.

**Last Updated**: 2026-01-09
