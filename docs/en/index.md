# FailCore

**FailCore is an execution-time safety runtime for AI agents.**

It does not analyze prompts.  
It does not debug reasoning.  
It does not rewrite tool calls.

FailCore answers only one question:

> **Should this action be allowed to execute — right now?**

---

## Why FailCore Exists

Modern AI agents often fail **not in reasoning**, but **at execution time**.

Even when an agent produces a seemingly correct plan, it can still:
- hallucinate a filesystem path
- send a network request to an internal IP
- leak secrets through streaming output
- enter an infinite tool loop and burn cost

These failures happen **after planning**, at the exact moment an action is executed.

FailCore exists to close this execution-time gap.

---

## What FailCore Does

FailCore sits between **agent intent** and **side effects**.

It enforces deterministic, policy-driven boundaries on actions such as:

- **Filesystem access**  
  Prevent destructive or out-of-scope reads/writes.
- **Network calls**  
  Block SSRF, internal IP access, and data exfiltration.
- **Tool execution**  
  Validate parameters before a tool is allowed to run.
- **Cost & resource usage**  
  Stop runaway loops and uncontrolled spending.
- **Streaming output**  
  Detect violations during live token streams.

All decisions are recorded with **traceable evidence** for audit and replay.

---

## What FailCore Is NOT

FailCore is **not**:
- a prompt engineering framework
- an agent planner or reasoning debugger
- a sandbox replacement (Docker / VM)
- a policy language for model behavior

FailCore does **not** tell agents *what to think*.  
It decides **whether an action is allowed to execute**.

---

## When You Should Use FailCore

FailCore is designed for:

- AI agents that can perform real-world side effects
- long-running or autonomous workflows
- tools that touch filesystem, network, or external APIs
- environments where failures must be explainable and auditable

If an agent can cause damage, FailCore should be in the execution path.

---

## Getting Started

If you want to see FailCore in action in under 3 minutes:

👉 **[Getting Started](getting-started.md)**

---

## Project Status

FailCore is under active development and focuses on:
- deterministic execution
- fail-fast behavior
- minimal, enforceable guarantees

APIs may evolve, but the execution model is intentionally conservative.

---

## License

FailCore is released under the Apache-2.0 license.
