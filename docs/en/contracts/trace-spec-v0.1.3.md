# FailCore Trace Specification v0.1.33

This document defines the **semantic and behavioral contract** of the FailCore Trace
format beyond what is structurally validated by JSON Schema.

> **JSON Schema defines _what is valid_.**
> **This specification defines _what it means_ and how producers and consumers must behave.**

This document is **normative** unless explicitly marked as **Non-normative**.

---

## 1. Scope and Philosophy

FailCore Trace is a **deterministic execution record** for AI agent systems, designed for:

- **Auditability**: every critical decision and failure must be explainable.
- **Replayability**: executions should be reproducible without re-running irreversible side effects.
- **Governance**: contract and policy enforcement must be explicit and machine-readable.
- **Protocol Stability**: traces are long-lived artifacts and must remain interpretable.

FailCore Trace is **not** a logging format.  
It is a **protocol-level execution trace**.

---

## 2. Schema vs Specification

### 2.1 JSON Schema (Structural Contract)

- Defines required fields, data types, and allowed object shapes.
- Enforced by validators, CI, and ingestion pipelines.
- Identified by the `schema` field (e.g. `failcore.trace.v0.1.3`).

### 2.2 Trace Specification (Semantic Contract)

- Defines semantic meaning and behavioral expectations.
- Defines what producers and consumers **MUST**, **SHOULD**, and **MUST NOT** do.
- Schema compliance alone does **not** guarantee semantic correctness.

---

## 3. Versioning and Compatibility

### 3.1 Specification Identification

Every trace **MUST** declare its schema identifier via the `schema` field.

Consumers **MUST** select interpretation rules based on this value.

### 3.2 Stability Guarantees

- `v0.1.x` guarantees backward compatibility.
- New fields and events may be added but must be optional.
- Breaking semantic changes require `v0.2.0`.

### 3.3 Extension Points

The following locations are reserved extension points and **MUST remain open**:

- `event.data`
- `event.step.meta`
- `run.tags`
- `run.flags`

Producers **MUST NOT** introduce protocol-level fields outside these locations.

---

## 4. Core Event Model

Each trace entry represents a single ordered event with:

- Monotonic sequence number (`seq`)
- Timestamp (`ts`)
- Event type and optional severity
- Optional step context
- Optional event-specific data

Traces represent **what happened**, not **why it was decided**.

---

## 5. Step Semantics

### 5.1 STEP_START / STEP_END

- `STEP_START` marks the beginning of a step execution.
- `STEP_END` marks completion and **MUST** include a result status.

Result statuses include:
- `OK`
- `ERROR`
- `BLOCKED`
- `TIMEOUT`

### 5.2 Attempt Identity

Each step may include an `attempt` counter.
Attempts are strictly ordered and scoped to the step.

---

## 6. Fingerprint and Replay Semantics

### 6.1 FINGERPRINT_COMPUTED

Represents the authoritative moment when a replay fingerprint is finalized.

Rules:
- The event **MUST** include `step.fingerprint.hash`.
- Consumers **MUST** treat this as ground truth for replay matching.

### 6.2 Canonicalization (Normative)

All data participating in fingerprint computation **MUST** be deterministic and canonicalized.

Implementations **SHOULD** follow RFC 8785 (JSON Canonicalization Scheme).

Non-deterministic inputs (timestamps, randomness, host IDs) **MUST NOT** participate
unless explicitly configured.

### 6.3 REPLAY_HIT / REPLAY_MISS

These events indicate replay cache behavior.

Rules:
- `data.replay.hit_key` **MUST** uniquely identify the cache entry.
- `data.replay.cache_source` **MUST** identify the cache origin.

---

## 7. Contract, Validation, and Policy Events

### 7.1 CONTRACT_DRIFT

Indicates deviation from declared contracts.

- `severity=warn`: informational drift
- `severity=block`: execution must halt

### 7.2 VALIDATION_FAILED

Indicates schema or validation errors.

These events **MUST NOT** be silently ignored.

### 7.3 POLICY_DENIED

Represents a hard governance decision.

Rules:
- `severity` **MUST** be `block`
- This event is terminal for the step or run.

---

## 8. Timeout Semantics

### 8.1 STEP_TIMEOUT

Represents timeout enforcement at execution time.

Severity determines whether execution was terminated or allowed to continue.

### 8.2 TIMEOUT_CLAMPED

Represents timeout normalization or clamping due to policy or environment limits.

---

## 9. Side Effects and Artifacts

`ARTIFACT_WRITTEN`, `SIDE_EFFECT_APPLIED`, and `EGRESS_EVENT` represent irreversible effects.

The schema intentionally allows flexible payloads.

**Non-normative recommendation**:
Include stable identifiers (path, host, hash) to support audit and replay reasoning.

---

## 10. Usage and Cost Semantics

Usage and billing fields are **informational**.

Rules:
- Cost fields **MUST NOT** be used as authoritative billing records.
- Estimated cost **MUST** be clearly marked as such.

---

## 11. Non-Goals

FailCore Trace does **not** define:

- Planner or reasoning logic
- Prompt structure
- Tool semantics
- Model behavior or intent

It records **what happened**, not **how decisions were made**.

---

## 12. Determinism Guarantee

Given identical trace input and specification version, two independent consumers
**MUST** derive identical interpretations.

Anything that violates this principle is considered out of scope.

---

## 13. Summary

FailCore Trace is a **protocol**, not a convenience log.

Correct implementations must:

- Validate structure via JSON Schema
- Interpret behavior via this specification
- Respect versioning, determinism, and extension rules
