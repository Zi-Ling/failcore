# FailCore

**When your agent breaks, you don't need better prompts — you need to know what it actually did.**

FailCore is a **minimal execution tracing and failure analysis toolkit** for LLM agents.

It doesn't care how agents "think" — it cares about: **what was executed, why it failed, and can we replay it.**

> ⚠️ **Beta (0.1.x)** — core CLI & trace format are stable; minor APIs may change.

---

## Why FailCore?

**Traditional Agent Frameworks:**
- ❌ No visibility into which tool call failed
- ❌ Can't track agent permission violations
- ❌ LLM output drift (text instead of JSON) goes undetected
- ❌ Can't replay execution for root cause analysis

**FailCore Solution:**
- ✅ **Auto-tracing** — Every tool call logged to `.jsonl` trace
- ✅ **Policy enforcement** — Agents can't escape sandbox boundaries
- ✅ **Contract validation** — Auto-detect output type drift (TEXT vs JSON)
- ✅ **Blackbox replay** — Audit execution without re-running LLM

---

## Quick Start

### Install (PyPI)

```bash
pip install failcore
```

> Pre-releases (TestPyPI):
> ```bash
> pip install -i https://test.pypi.org/simple >   --extra-index-url https://pypi.org/simple >   failcore
> ```

### Try the Demo (Recommended)

```bash
failcore sample
failcore show
```

### Minimal API

```python
from failcore import Session

with Session() as session:
    session.register("divide", lambda a, b: a / b)
    r = session.call("divide", a=6, b=0)

print(r.status.value)
print(r.error.message if r.error else None)
```

### View Execution Records

```bash
failcore list
failcore show                 # last run
failcore replay run <trace>    # report/mock
failcore replay diff <trace>
```

---

## Three Core Capabilities

### 1. Sandbox Policy (Permission Boundaries)

```python
from failcore import Session, presets
import os

with Session(policy=presets.read_only()) as session:
    session.register("delete_cache", os.remove)
    result = session.call("delete_cache", path="/tmp/cache.db")
    # ❌ Blocked by policy — never executes
```

### 2. Contract Validation (Output Drift Detection)

```python
from failcore import Session

with Session() as session:
    @session.tool
    def fetch_user() -> dict:  # Expected: dict
        return "Here is the data: {name: 'Alice'}"  # ❌ Returned text

    r = session.call("fetch_user")
    # Auto-detected: r.output.kind == "TEXT" (expected JSON)
```

### 3. Trace Replay (Forensic Analysis)

```bash
# Offline audit — no LLM re-run needed
failcore replay run <trace> --mode report

# Compare historical vs current rules/outputs
failcore replay diff <trace>
```

---

## LangChain Integration (Optional)

Install with LangChain support:

```bash
pip install "failcore[langchain]"
```

```python
from failcore.adapters.langchain import create_langchain_toolkit

toolkit = create_langchain_toolkit(session)
# All agent tool calls auto-logged to trace
```

---

## Who Is This For?

- 🔧 Building production-grade agent systems
- 🐛 Debugging complex multi-step execution chains
- 🔒 Enforcing agent permission boundaries
- 📊 Offline failure root cause analysis

---

## License

MIT
