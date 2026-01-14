# What is FailCore

FailCore is an **execution-time safety runtime** for AI agents.

It does not analyze prompts.  
It does not debug reasoning.  
It does not rewrite tool calls.

FailCore answers only one question:

> **Should this operation be allowed to execute right now?**

---

## Core Positioning

FailCore sits between **agent intent** and **side effects**.

When an AI agent generates tool calls, FailCore validates them before execution:

- ✅ **Execution-time enforcement** — block unsafe actions before they run
- ✅ **Structured tracing** — every action recorded as evidence
- ✅ **Clear outcomes** — `BLOCKED` vs `FAIL` clearly distinguished
- ✅ **Forensic reports** — inspect incidents offline
- ✅ **Proxy-first design** — observe real traffic, not demos

---

## How It Works

FailCore acts as a **runtime safety layer** between:

- LLM frameworks / SDKs  
- and the real world (filesystem, network, processes)

It is **not** an agent framework.  
It is a **guardrail, recorder, and black box**.

---

## Problems It Solves

Modern AI agents often fail **not in reasoning**, but **at execution time**.

Even when an agent produces a seemingly correct plan, it can still:

- ❌ Generate incorrect filesystem paths
- ❌ Send network requests to internal IPs
- ❌ Leak secrets through streaming output
- ❌ Enter infinite tool loops and consume costs

These failures happen **after planning**, at the exact moment operations are executed.

FailCore exists to close this execution-time gap.

---

## Key Features

FailCore enforces deterministic, policy-driven boundaries on operations:

### Filesystem Access
Prevent destructive or out-of-scope reads/writes.

### Network Calls
Block SSRF, internal IP access, and data exfiltration.

### Tool Execution
Validate parameters before allowing tools to run.

### Cost and Resource Usage
Stop runaway loops and uncontrolled spending.

### Streaming Output
Detect violations in real-time token streams.

All decisions are recorded with **traceable evidence** for audit and replay.

---

## What FailCore Is NOT

FailCore is **not**:

- a prompt engineering framework
- an agent planner or reasoning debugger
- a sandbox replacement (Docker / VM)
- a policy language for model behavior

FailCore does **not** tell agents *what to think*.  
It decides **whether operations are allowed to execute**.

---

## Project Status

FailCore is under active development (0.1.x pre-release).

APIs, CLI commands, and report formats may change.

Currently focused on:
- Deterministic execution
- Fail-fast behavior
- Minimal, enforceable guarantees

---

## Next Steps

- [Installation Guide](../getting-started/install.md)
- [Quick Start](../getting-started/first-run.md)
- [Core Concepts](../concepts/execution-boundary.md)
