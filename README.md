# FailCore

**When your agent breaks, you don't need better prompts — you need to know what it actually did.**

FailCore is a **minimal execution tracing and failure analysis toolkit** for LLM agents.

It doesn't care how agents "think" — it cares about: **what was executed, why it failed, and can we replay it.**

> ⚠️ **Alpha Stage** - APIs may change | [TestPyPI](https://test.pypi.org/project/failcore/)

---

## Why FailCore?

**Traditional Agent Frameworks:**
- ❌ No visibility into which tool call failed
- ❌ Can't track agent permission violations
- ❌ LLM output drift (text instead of JSON) goes undetected
- ❌ Can't replay execution for root cause analysis

**FailCore Solution:**
- ✅ **Auto-tracing** - Every tool call logged to `.jsonl` trace
- ✅ **Policy enforcement** - Agents can't escape sandbox boundaries
- ✅ **Contract validation** - Auto-detect output type drift (TEXT vs JSON)
- ✅ **Blackbox replay** - Audit execution without re-running LLM

---

## Quick Start

### Install

```bash
pip install -i https://test.pypi.org/simple \
  --extra-index-url https://pypi.org/simple \
  failcore==0.1.0a1
```

### 3 Lines of Code

```python
from failcore import Session

with Session(trace="trace.jsonl") as session:
    session.register("divide", lambda a, b: a / b)
    result = session.call("divide", a=6, b=0)  # Auto-captures failure
    
print(result.status)  # "error"
print(result.error.message)  # "division by zero"
```

### View Execution Records

```bash
failcore show --last              # View last run
failcore replay run trace.jsonl  # Replay execution
```

---

## Three Core Capabilities

### 1. Sandbox Policy (Permission Boundaries)

```python
from failcore import Session, presets

session = Session(
    policy=presets.read_only()  # Deny write operations
)

session.register("delete_file", os.remove)
result = session.call("delete_file", path="/etc/passwd")
# ❌ Blocked by policy - never executes
```

### 2. Contract Validation (Output Drift Detection)

```python
@session.tool
def fetch_user() -> dict:  # Expected: dict
    return "Here is the data: {name: 'Alice'}"  # ❌ LLM returned text

result = session.call("fetch_user")
# Auto-detected: result.output.kind == "TEXT" (expected JSON)
```

### 3. Trace Replay (Forensic Analysis)

```bash
# Offline audit - no LLM re-run needed
failcore replay run trace.jsonl --mode report

# Compare expected vs actual outputs
failcore replay diff trace.jsonl
```

---

## LangChain Integration

```python
from failcore.adapters.langchain import create_langchain_toolkit

# Connect existing LangChain tools to FailCore tracing
toolkit = create_langchain_toolkit(session)
agent = create_react_agent(llm, toolkit, prompt)
# All agent tool calls auto-logged to trace.jsonl
```

---

## Try the Demo

Run the full three-act demonstration (Policy/Contract/Replay):

```bash
failcore sample
```

---

## Who Is This For?

- 🔧 Building production-grade agent systems
- 🐛 Need to debug complex multi-step execution chains
- 🔒 Need to control agent permission boundaries
- 📊 Need offline failure root cause analysis

---

## License

MIT
