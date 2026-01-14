# Getting Started

This guide shows how FailCore blocks a dangerous action **at execution time**.

The example demonstrates a common agent failure:

> A model-generated tool call that deletes the wrong directory.

---

## Install

```bash
pip install failcore
```

---

## The Problem: Path Hallucination

Consider a simple tool that deletes a directory:

```python
import shutil

def delete_path(path: str):
    shutil.rmtree(path)
```

An AI agent might *intend* to delete a temporary folder, but hallucinate the path:

```text
"/project"
```

Without protection, this executes immediately — and destructively.

---

## Protect the Action with FailCore

Wrap the execution with a FailCore session and policy:

```python
from failcore import run, guard

with run(policy="fs_safe", strict=True) as ctx:
    @guard
    def delete_path(path: str):
        import shutil
        shutil.rmtree(path)
    
    delete_path("/project")
```

**Alternative style** (explicit tool registration):

```python
from failcore import run

def delete_path(path: str):
    import shutil
    shutil.rmtree(path)

with run(policy="fs_safe", strict=True) as ctx:
    ctx.tool(delete_path)
    ctx.call("delete_path", path="/project")
```

---

## What Happens

Instead of deleting the directory, FailCore blocks the action:

- ❌ Execution is denied
- 📛 A violation is raised
- 🧾 Evidence is recorded in the trace

FailCore validates the action **before** it runs.

---

## Why This Matters

- The model's reasoning may look correct
- The plan may be logically sound
- But execution-time values can still be wrong

FailCore enforces **last-line-of-defense guarantees**.

---

## What You Get

When a violation occurs, FailCore provides:

- the exact tool call and parameters
- the violated policy rule
- a structured trace for audit or replay

This makes failures explainable — not mysterious.

---

## Next Steps

- Explore different policy presets (`fs_safe`, `net_safe`, `safe`)
- Inspect execution traces
- Manage policies with `failcore policy init` and `failcore policy explain`
- Integrate FailCore into agent runtimes or proxies

For deeper design details, see the architecture documents.
