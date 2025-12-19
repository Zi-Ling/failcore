> Note: This is an early TestPyPI build. CLI commands and outputs may change.

# FailCore

FailCore is a **minimal execution tracing and failure analysis toolkit** for LLM agents.

It focuses on **what actually goes wrong during execution**, not on planning or intelligence.

> ⚠️ Status: **Alpha (TestPyPI)**  
> APIs and formats may change without notice.

---

## Install (TestPyPI)

```bash
pip install -i https://test.pypi.org/simple \
  --extra-index-url https://pypi.org/simple \
  failcore==0.1.0a1
```

---

## Quick Start

### 1. Initialize a sample trace

```bash
failcore init
```

This creates a sample `trace.jsonl` in the current directory.

---

### 2. Analyze the trace

```bash
failcore analyze trace.jsonl
```

Example output:

```text
File: trace.jsonl
Events: 12
Steps: 2
Failures: 1
Top failure: PARAM_INCOMPLETE
Last error: Missing required field: formula_template
```

---

## Commands

- `failcore init`  
  Generate a minimal example `trace.jsonl`.

- `failcore analyze <path>`  
  Analyze a trace file in JSONL format.

---

## What is a Trace?

A trace is a **JSONL (JSON Lines)** file describing agent execution events.

Each line represents one event (step, tool call, validation error, etc.).

Example:

```json
{"type": "step", "id": "s1", "tool": "excel.write", "status": "ok"}
{"type": "step", "id": "s2", "tool": "excel.add_formula", "status": "error", "error": "Missing required field: formula_template"}
```

---

## License

MIT
