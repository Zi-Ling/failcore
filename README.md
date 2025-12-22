English | [中文](README_ZH.md)
# FailCore — A Deterministic Execution Runtime for AI Agents

> **Status:** Beta (0.1.x) · PyPI available · CLI included  
> Install: `pip install failcore` · Try: `failcore sample`

> *“Success has many fathers, but failure has its own core.”*

FailCore is a **fail-fast execution runtime** for AI agents.

It does not try to make agents smarter — it makes them **reliable**.

Most agent frameworks focus on planning and reasoning.  
FailCore focuses on what happens **after a plan is generated**:
execution correctness, persistence, auditability, and safe recovery from failure.

---

## Why FailCore?

Modern AI agent systems often run in a fragile, best-effort mode:

- **Expensive retries**  
  If a 10-step workflow fails at step 9, the entire chain restarts.

- **Opaque state**  
  When an agent hallucinates or crashes, it is hard to reconstruct *what actually happened*.

- **Uncontrolled execution**  
  Granting agents real permissions without guardrails is dangerous.

FailCore acts as the **Black Box (flight data recorder)** and **Airbag** for AI agent execution.

---

## Quick Start

### Install

```bash
pip install failcore
```

### Try the built-in demo

```bash
failcore sample
failcore show
```

The demo showcases:
- Policy interception (permission boundaries)
- Output contract drift detection (TEXT vs JSON)
- Offline replay from execution trace

---

## A Concrete Failure Scenario

A 10-step agent workflow fails at step 9.

**Without FailCore**
- The entire workflow restarts
- All previous tool calls are re-executed
- Root cause is difficult to reproduce

**With FailCore**
- Steps 1–8 are replayed instantly from trace
- Only the failing step is re-executed
- Full inputs/outputs are inspectable offline

---

## Core Features

- **Deterministic Replay (Breakpoint Resume)**  
  Previously successful steps are replayed instantly using execution fingerprints.

- **Audit-Grade Tracing**  
  Append-only JSONL traces capture inputs, outputs, latency, and failure reasons.

- **Execution Guardrails (Policy Gate)**  
  Unsafe or invalid actions are blocked before execution.

- **Framework-Agnostic Design**  
  Can be embedded beneath LangChain, AutoGen, CrewAI, or custom runtimes.

- **Cost Attribution (experimental)**  
  Lays the groundwork for measuring time and execution savings from replay.

---

## Architecture: The "Black Box" Protocol

FailCore follows a strict **Verify-then-Run** lifecycle:

1. **Resolve** — Generate a deterministic fingerprint for the step  
2. **Validate** — Check inputs against policies and invariants  
3. **Execute** — Run only if no successful record exists  
4. **Commit** — Append results to the persistent execution trace  

This design enables deterministic execution, replayability, and auditability.

---

## What FailCore Is Not

FailCore is intentionally *not*:
- A planner
- A memory system
- An agent framework

It does not generate plans — it ensures executing plans is safe, observable, and recoverable.

---

## Contributing

Contributions are welcome.  
If you are building agent systems that need stronger execution guarantees, we would love your feedback.

---

## License

This project is licensed under the **Apache License 2.0**.  
See the [LICENSE](LICENSE) file for details.

Copyright © 2025 ZiLing
