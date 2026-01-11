# FailCore

**When your agent breaks, you don't need better prompts — you need to know what it actually did.**

FailCore is an **execution-time tracing and safety runtime** for LLM systems.

It does not care how agents *reason* or *plan*.  
It focuses on **what was actually executed**, **what was blocked**, and **how to audit it after the fact**.

> ⚠️ **Pre-release (0.1.x)**  
> FailCore is under active development. APIs, CLI commands, and report formats may change.

---

## Why FailCore?

Most agent frameworks focus on *decision making*.  
FailCore focuses on the **moment actions touch the real world**.

**Without FailCore:**
- ❌ Tool failures are buried in logs
- ❌ Unsafe side effects are only discovered after damage
- ❌ No execution-level audit trail
- ❌ Debugging requires re-running expensive agents

**With FailCore:**
- ✅ **Execution-time enforcement** — block unsafe actions before they run
- ✅ **Structured tracing** — every action recorded as evidence
- ✅ **Clear outcomes** — `BLOCKED` vs `FAIL`
- ✅ **Forensic reports** — inspect incidents offline
- ✅ **Proxy-first design** — observe real traffic, not demos

---

## Core Concept

FailCore acts as a **runtime safety layer** between:
- LLM frameworks / SDKs  
- and the real world (filesystem, network, processes)

It is **not** an agent framework.  
It is a **guardrail, recorder, and black box**.

---

## Installation

```bash
pip install failcore
```

> ⚠️ Intended for evaluation and experimentation.

---

## Proxy-First Usage (Recommended)

FailCore is primarily designed to run as a **local proxy** in front of LLM SDKs.

```bash
pip install "failcore[proxy]"
```

```bash
failcore proxy
```

Configure your LLM client to route requests through FailCore.
All tool calls, streaming output, and side effects are traced and audited.

---

## Minimal Runtime API

FailCore no longer exposes session-style APIs.

The core primitives are:

```python
from failcore import run, guard
```

Example (filesystem protection):

```python
from failcore import run, guard

with run(policy="fs_safe", strict=True) as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    write_file("../etc/passwd", "hack")
```

Result:
- Execution is **blocked**
- Evidence is recorded
- Trace is persisted for inspection

---

## Inspect Traces

```bash
failcore list
failcore show
failcore report
failcore replay run <trace>
failcore replay diff <trace>
```

---

## Optional Integrations

### LangChain

```bash
pip install "failcore[langchain]"
```

FailCore can wrap LangChain tools to enforce execution-time safety and tracing.

---

## Who Is This For?

- 🔒 Developers running LLMs with real side effects
- 🐛 Debugging agent failures and hallucinated actions
- 📊 Auditing and post-mortem analysis
- 🧯 Adding a safety airbag to agent systems

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
