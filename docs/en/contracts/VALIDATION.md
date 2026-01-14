# FailCore Validation Architecture (Revised)

This document defines the **validation architecture of FailCore** with an explicit
focus on **real-world operability, long-term evolution, and failure handling**.

FailCore validation is not designed for idealized agents or perfect policies.
It is designed for **imperfect agents, partial policies, and production failures**.

---

## 1. What Validation Means in FailCore

Validation in FailCore is an **execution-time control system**.

Its purpose is to:
- Prevent unsafe or irreversible side-effects
- Provide clear, explainable decisions
- Enable controlled degradation instead of catastrophic failure

> **FailCore does not aim to make agents correct.  
> It aims to make agent failures survivable, explainable, and recoverable.**

---

## 2. Core Assumptions (Explicitly Non-Ideal)

FailCore is built on the following *realistic* assumptions:

- Most users **cannot write high-quality policies**
- Most policies will be **incomplete or overly strict**
- Validation rules will **block legitimate behavior at some point**
- Emergency overrides will be needed in production
- Policies will evolve continuously, not stabilize

These assumptions directly shape the validation architecture.

---

## 3. Validation Scope: Execution-Time Side-Effects

FailCore validation is intentionally limited to **deterministic, enforceable side-effects**.

### 3.1 Security
Local destructive or privileged actions:
- File system access and deletion
- Command execution
- Process creation and control

### 3.2 Network
Outbound communication and model interaction:
- Domain and CIDR restrictions
- SSRF and metadata endpoint blocking
- Retry and fallback control

### 3.3 Resource
Finite execution budgets:
- Token and cost limits
- Runtime and retry caps
- Concurrency constraints

### 3.4 Contract
Structural correctness:
- Tool schemas and argument validation
- Payload size limits
- Semantic consistency checks

> These four domains form a **complete set of enforceable execution boundaries**.
> They do **not** attempt to encode intent, business logic, or high-level correctness.

---

## 4. Policy as Data — With Explicit Limits

FailCore uses **Policy-as-Data** as a baseline, not as a universal solution.

### 4.1 Why Policy-as-Data Exists
- Human-readable and reviewable
- Diff-friendly (GitHub, code review)
- Deterministic evaluation
- Portable across runtimes

### 4.2 Where Policy-as-Data Breaks Down
- Complex conditional logic
- Context-dependent decisions
- Multi-step correlations
- Long-term risk accumulation

FailCore **does not pretend** these problems disappear.

> Policy-as-Data is a **floor**, not a ceiling.

---

## 5. Multi-Layer Policy Expression Model

FailCore explicitly supports **multiple expression layers**, even if only the first
is implemented initially.

### Layer 1: Declarative Policy (Required)
- YAML / JSON
- Covers ~60–70% of practical enforcement needs
- Used by default

### Layer 2: Embedded Expressions (Planned)
- Lightweight expression engines (e.g. CEL)
- Context-aware conditions
- Still compiled into deterministic policy evaluation

### Layer 3: Advanced Evaluators (Optional, Future)
- WASM-based pure evaluators
- Sandboxed, side-effect free
- Used only when necessary

> **Policy JSON remains the single source of truth.  
> Expressions and DSLs compile into policy, never replace it.**

---

## 6. Decision Model (Designed for Evolution)

FailCore decisions are **structured, extensible, and explainable**.

### 6.1 Core Decision Fields (Stable)
- `decision`: allow | warn | block
- `code`: stable, referenceable identifier
- `message`: human-readable explanation
- `evidence`: structured audit data

### 6.2 Reserved Extension Fields (Not Required Initially)
- `risk_level`: critical | high | medium | low
- `confidence`: match certainty
- `overrideable`: boolean
- `requires_approval`: boolean
- `tags`: audit and compliance markers

> The decision model is intentionally **over-provisioned** to avoid breaking
> audits, UIs, or reports in later versions.

---

## 7. Explainability and Debuggability (First-Class)

Every blocked or warned action **must be explainable**.

FailCore guarantees:
- Which rule triggered
- Why it triggered
- What evidence was used
- Whether an override was possible
- How to remediate or relax the policy

A validation system that cannot explain itself
**will be disabled in production**.

---

## 8. Escape Hatches and Progressive Enforcement

FailCore assumes that **overly strict rules are inevitable**.

### 8.1 Progressive Enforcement
Policies may be deployed in stages:
- Shadow (observe only)
- Warn
- Block

### 8.2 Emergency Overrides (Break-Glass)
- Explicit override tokens
- Time-limited bypasses
- Fully audited usage

### 8.3 Scoped Overrides
- Per deployment
- Per team
- Per workflow
- Per time window

> **There is no silent bypass.  
> Every override leaves a trace.**

---


## 9. Contract Stability Guarantees (Critical)

To enable future engine replacement (WASM, Rust core, mobile runtimes)
without breaking users or policies, FailCore treats the following contracts
as **strictly stable**.

### 9.1 Validation Context (ContextV1)
- The validation context **must be language-agnostic and serializable**
- No runtime-specific objects (functions, file handles, stack frames)
  may appear in the context
- All platforms (SDK, Proxy, future mobile or embedded runtimes)
  must map their local data into this canonical context model

### 9.2 Decision Model (DecisionV1)
- Decision fields are **append-only**
- Existing fields must never change semantic meaning
- Decision codes are **immutable once published**
- New behaviors require new codes or new optional fields

### 9.3 Policy Representation (PolicyV1)
- Policy data has a **canonical normalized form**
- YAML, JSON, TOML, DSLs, or UI editors must all compile into this form
- The canonical policy is the **only source of truth** for evaluation
- Policy evolution is handled via explicit versioning, not implicit changes


---


## 10. Engine and Portability Strategy

FailCore separates **contracts** from **implementations**.

### Stable Contracts (Must Not Break)
- Policy schema (versioned)
- Validation context model
- Decision model

### Replaceable Engines
- Python engine (current)
- Rust core engine (future)
- Hybrid or WASM-assisted engines

This allows FailCore to migrate across platforms
(desktop, server, mobile) without rewriting policies or tooling.


---

## 11. Community Contribution Reality

FailCore does not rely on community members to write complex policies.

Instead, community contribution focuses on:
- Policy examples and templates
- Rule feedback and incident reports
- Test cases and edge scenarios

High-quality default rules are **platform responsibility**, not user burden.

---

## 12. Non-Goals (Explicit)

FailCore validation does not aim to:
- Replace agent reasoning
- Encode business intent
- Predict future behavior
- Eliminate all failures

Its goal is **controlled failure**, not perfect behavior.

---

## 12. Summary

FailCore validation is designed as a **long-lived execution control plane**
that prioritizes:
- Realistic usage
- Operational safety
- Explainability
- Future portability

> **Implementations will change.  
> Contracts, assumptions, and failure paths must not.**
