# FailCore Trace Specification v0.1.2

This document defines the **semantic and behavioral contract** of the FailCore
Trace format, beyond structural validation enforced by JSON Schema.

> **JSON Schema defines _what is valid_.**
> **This specification defines _what it means_.**

This document is normative unless explicitly stated otherwise.

---

## 1. Scope and Philosophy

FailCore Trace is designed as a **deterministic execution record** for AI agent
systems, with a focus on:

- **Auditability**: every critical decision and failure must be explainable.
- **Replayability**: executions should be resumable without re-running side effects.
- **Governance**: policy and contract violations must be explicit and machine-readable.
- **Protocol Stability**: traces are long-lived artifacts and must remain interpretable.

FailCore Trace **is not** a logging format.
It is a **protocol-level execution trace**.

---

## 2. Relationship Between Schema and Specification

FailCore Trace consists of two layers:

### 2.1 JSON Schema (Structural Contract)

- Defines required fields, types, and allowed structures.
- Enforced by validators, CI, and tooling.
- Located under `trace/*.schema.json`.

### 2.2 Trace Specification (This Document)

- Defines **semantic meaning**, **behavioral expectations**, and **compatibility rules**.
- Defines what producers and consumers **must**, **should**, or **must not** do.
- Located under `docs/`.

Schema compliance **does not guarantee semantic correctness**.
Consumers must interpret traces according to this specification.

---

## 3. Versioning and Compatibility

### 3.1 Trace Version Identification

Every trace **MUST** declare its specification version:

```json
{
  "run": {
    "version": {
      "spec": "v0.1.2"
    }
  }
}
```

Consumers **MUST** select the appropriate validator and interpretation rules
based on this version.

### 3.2 Schema Closure and Extension Points

FailCore Trace uses `additionalProperties: false` on most protocol-level objects
to enforce **schema closure**.

This means:

- Unknown fields at protocol level are treated as errors in strict validation.
- New protocol fields require a new trace specification version.

#### Approved Extension Points (Always Allowed)

The following locations are explicitly reserved for extensions and **must remain open**:

- `event.data`
- `event.step.meta`
- `run.tags`
- `run.flags`

Producers **MUST NOT** introduce new fields outside these extension points.

### 3.3 Strict vs Non-Strict Parsing

Implementations **SHOULD** provide two parsing modes:

- **Strict mode**: full schema validation (CI, production, audit).
- **Non-strict mode**: tolerant parsing for migration and inspection.

---

## 4. Event Semantics

### 4.1 Execution Steps

- `STEP_START` and `STEP_END` represent step lifecycle.
- `event.step.id` and `event.step.tool` identify a step uniquely.

### 4.2 FINGERPRINT_COMPUTED

Represents the **authoritative moment** when a replay fingerprint is finalized.

Rules:

- The event **MUST** include `event.step.fingerprint`.
- Consumers **SHOULD** treat this as the ground truth for replay.

---

## 5. Fingerprint Canonicalization (Critical)

### 5.1 Canonicalization Requirement

All data participating in fingerprint computation **MUST** be canonicalized
before hashing.

### 5.2 Recommended Canonicalization

Implementations **SHOULD** follow **RFC 8785 (JSON Canonicalization Scheme)**.

At minimum, implementations **MUST** ensure:

- Lexicographically sorted object keys
- Normalized numeric representations
- UTF-8 encoding
- No NaN or Infinity values
- Stable serialization

### 5.3 Deterministic Inputs Only

Non-deterministic data **MUST NOT** participate unless explicitly configured.

Examples:

- Timestamps
- Random values
- Host-specific identifiers

The `fingerprint.components` field **SHOULD** list included components explicitly.

---

## 6. Replay Semantics

### 6.1 REPLAY_HIT / REPLAY_MISS

Indicate whether execution avoided re-running side effects.

Rules:

- `data.replay` **MUST** be present.
- `data.replay.hit_key` **MUST** uniquely identify the replay entry.
- `data.replay.cache_source` **MUST** indicate the cache source.

Optional metrics:

- `saved_tokens`
- `saved_ms`

---

## 7. Contract and Validation

### 7.1 CONTRACT_DRIFT

Represents deviation from declared contracts.

- `severity=warn`: soft drift
- `severity=block`: execution must halt

### 7.2 VALIDATION_FAILED

Represents validation failures such as:

- Schema violations
- Parse errors
- Missing required parameters

This event **MUST NOT** be silently ignored.

---

## 8. Policy Enforcement

### 8.1 POLICY_DENIED

Represents a hard governance decision.

Rules:

- `severity` **MUST** be `block`
- `category=OTHER` **REQUIRES** `category_detail`

This event is terminal.

---

## 9. Artifacts and Side Effects

`ARTIFACT_WRITTEN` and `SIDE_EFFECT_APPLIED` represent irreversible effects.

No fixed payload structure is enforced in v0.1.2.

Recommended (non-normative):

```json
{
  "artifact": {
    "kind": "file | db | http | other",
    "ref": "...",
    "hash": "sha256:..."
  }
}
```

---

## 10. Non-Goals

FailCore Trace does **not** define:

- Planner logic
- Prompt structure
- Tool semantics
- LLM behavior

It records **what happened**, not **how it was decided**.

---

## 11. Stability Guarantee

- `failcore.trace.v0.1.2` is intended to remain stable.
- v0.1.x only adds optional fields/events.
- Breaking changes require v0.2.0.

---

## 12. Summary

FailCore Trace is a **protocol**, not a convenience log.

Correct implementations must:

- Validate structure via JSON Schema
- Interpret semantics via this specification
- Respect versioning and canonicalization rules
