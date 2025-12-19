# LangChain Adapter

This directory provides a thin adapter that allows LangChain tools to be executed
through FailCore’s execution layer.

Scope: tool execution only  
Non-goals: planning, agent loops, retries, or intelligence

---

## What this adapter does

When a LangChain tool is invoked, this adapter:

1. Intercepts the tool call
2. Passes the call to FailCore for:
   - input validation
   - policy checks
   - execution
   - trace recording
3. Returns the result (or a structured failure) back to LangChain

In short:

LangChain decides what to call.  
FailCore decides whether and how it is executed.

---

## What this adapter does NOT do

This adapter intentionally does NOT:

- plan tasks or decompose goals
- run agent loops or workflows
- retry failed calls
- auto-fix parameters
- provide a tool library
- add intelligence or heuristics

FailCore remains a strict execution runtime, not an agent framework.

---

## Key concepts

### Tool runner

The core integration point is the tool runner.

Instead of calling a tool function directly, LangChain tools are wrapped so that
each invocation goes through FailCore’s execution pipeline:

Validate → Policy → Execute → Trace

This guarantees that every tool call is deterministic, auditable, replayable,
and fail-fast.

---

### Tool schema and versioning

Each tool is described by:

- a name
- a parameter schema
- a version string

The version is not used for routing or intelligence.
It exists to prevent unsafe replay when tool parameters change over time.

---

### Failure semantics

Failures are returned as explicit error types, not raw Python exceptions
(for example: PRECONDITION_FAILED, POLICY_DENIED, TOOL_RAISED).

LangChain or the host application decides how to react:
- re-plan
- request permissions
- stop execution

FailCore never retries or recovers automatically.

---

## Minimal usage pattern

1. Define your business function
2. Describe its parameter schema
3. Wrap it as a LangChain tool via this adapter
4. Inject a FailCore-backed tool runner
5. Use the tool normally in LangChain

The adapter ensures FailCore sits under LangChain tools,
without modifying LangChain’s core behavior.

---

## Design principles

- Minimal insertion point  
  Only tool execution is intercepted.

- Clear responsibility split  
  LangChain plans and decides.  
  FailCore executes and records.

- Fail fast, never guess  
  Invalid or unsafe calls are rejected before side effects occur.

- No silent behavior  
  Every execution outcome is written to a trace.

---

## Status

This adapter is intentionally small and conservative.

It is designed to be embedded inside larger systems and may evolve,
but its non-goals are considered stable.
