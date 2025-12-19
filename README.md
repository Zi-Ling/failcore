# FailCore — A Deterministic Execution Runtime for AI Agents

> *“Success has many fathers, but failure has its own core.”*

## FailCore is a Fail-Fast execution runtime for AI agents.

It is designed to stop unsafe or invalid actions early, preserve execution state, and make failures auditable.

FailCore is a lightweight, production-grade execution runtime for AI Agents.  
It does **not** aim to make agents smarter — it makes them **reliable**.

Most agent frameworks focus on planning and reasoning. FailCore focuses on what happens **after** a plan is generated: execution correctness, persistence, auditability, and safe recovery from failure.

By introducing **trace-based persistence** (append-only, replayable execution logs) and **fail-fast validation** at the atomic tool-calling level, FailCore enables breakpoint-resume execution for complex, long-running LLM workflows.

---

## Why FailCore?

Most AI agent systems today operate in a fragile “best-effort” mode:

- **Expensive retries**  
  If a 10-step task fails at step 9, the entire workflow restarts, wasting time and tokens.

- **Opaque state**  
  When an agent hallucinates or crashes, it is difficult to reconstruct the exact execution context that caused the failure.

- **Uncontrolled execution**  
  Granting agents permission to perform sensitive actions is risky without an atomic interceptor and an auditable trail.

FailCore acts as the **Black Box** (flight data recorder) and **Airbag** for AI agent execution.

---

## Core Features

- **Instant Rehydration (Breakpoint Resume)**  
  Smart replay based on a deterministic fingerprint (e.g., `input_hash`). If a step succeeded previously, FailCore replays the result instantly and skips redundant execution.

- **Audit-Grade Tracing**  
  Records every tool call’s inputs, outputs, latency, and environment snapshot in an append-only JSONL trace.

- **Execution Guardrails (Policy Gate)**  
  Validates inputs and blocks risky operations before they touch production systems.

- **Framework-Agnostic Integration**  
  Designed to be embedded beneath LangChain, AutoGen, CrewAI, or custom Python runtimes.

- **Cost Attribution**  
  Computes time/token savings gained from replay and early failure detection.

---

## Quick Start

### 1) Install

    uv venv
    uv pip install -e .

---

## Architecture: The “Black Box” Protocol

FailCore follows a strict **Verify-then-Run** lifecycle:

1. **Resolve** — generate a unique fingerprint for the current step.
2. **Validate** — check inputs against policies and invariants.
3. **Execute** — call the tool only if no successful record exists in the trace.
4. **Commit** — append the result to the persistent trace and flush to disk.

This design ensures deterministic execution, replayability, and auditability.

---

## Engineering Value

- **Debug faster**  
  Stop re-running long chains to reproduce bugs. Inspect and replay directly at the point of failure.

- **Reduce token and time costs**  
  Avoid redundant tool calls and repeated LLM work by replaying cached outputs.

- **Compliance-ready auditing**  
  Provide an immutable execution trail suitable for enterprise safety and governance.

---

## What FailCore is not

FailCore is intentionally *not* a planner, memory system, or agent framework.  
It does not generate plans — it ensures that executing plans is safe, deterministic, and observable.

---

## Contributing

PRs and issues are welcome. If you’re building agent systems that need stronger execution guarantees, we’d love your feedback.

---

## License

FailCore is released under the MIT License.

