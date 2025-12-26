# FailCore

**When your agent breaks, you don't need better prompts — you need to know what it actually did.**

FailCore is a **minimal execution tracing and failure analysis toolkit** for LLM agents.

It doesn't care how agents "think" — it cares about: **what was executed, why it failed, and can we replay it.**

> ⚠️ **Beta (0.1.2)** — core execution model, CLI, and trace format are stable; minor APIs may evolve.

---

## ✨ What's New in v0.1.2

- 🛡️ **Tool Metadata (Optional)** — Attach risk and side-effect hints to tools
- 🔒 **Improved Security Checks** — Path traversal detection and basic sandbox enforcement
- 📊 **Audit Reports** — HTML execution reports with failure and threat context
- 🎯 **Semantic Status** — Clear distinction: `BLOCKED` (prevented) vs `FAIL` (error)
- 🗄️ **Optional SQLite Ingestion** — Persist and query traces after execution

---

## Why FailCore?

**Traditional Agent Frameworks:**
- ❌ No visibility into which tool call failed
- ❌ Can't track agent permission violations
- ❌ LLM output drift (text instead of JSON) goes undetected
- ❌ Can't replay execution for root cause analysis

**FailCore Solution:**
- ✅ **Auto-tracing** — Every tool call logged to `.jsonl` trace
- ✅ **Security-aware execution** — Invalid or unsafe operations can be blocked before execution
- ✅ **Contract validation** — Detect output type drift (TEXT vs JSON)
- ✅ **Blackbox replay** — Audit execution without re-running LLM
- ✅ **Readable reports** — HTML reports for post-run inspection

---

## Quick Start

### Install (PyPI)

```bash
pip install failcore
```

> Pre-releases (TestPyPI):
> ```bash
> pip install -i https://test.pypi.org/simple \
>   --extra-index-url https://pypi.org/simple \
>   failcore
> ```

### Try the Demo

```bash
failcore sample
failcore show
```

### Minimal API

```python
from failcore import Session, presets

# Enable strict security mode (SSRF & Sandbox protection ON)
session = Session(validator=presets.fs_safe(strict=True))

@session.register
def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)

# --- Simulation: LLM tries to attack ---
# 1. Path Traversal Attack -> BLOCKED
result = session.call("write_file", path="../etc/passwd", content="hack")
print(f"Status: {result.status}")  # Output: BLOCKED
print(f"Error: {result.error.message}") # Output: Path traversal detected

# 2. SSRF Attack -> BLOCKED
# (If you have network tools registered)
```

---

## View Execution Records

```bash
failcore list
failcore show                 # last run
failcore report               # generate HTML audit report
failcore replay run <trace>   # replay/mock
failcore replay diff <trace>
failcore report <trace>  # generate HTML report
```

---

## LangChain Integration (Optional)

```bash
pip install "failcore[langchain]"
```

```python
from failcore.adapters.langchain import create_langchain_toolkit

toolkit = create_langchain_toolkit(session)
# All agent tool calls are traced by FailCore
```

---

## Who Is This For?

- 🔧 Building production-grade agent systems
- 🐛 Debugging multi-step execution chains
- 🔒 Enforcing execution and permission boundaries
- 📊 Offline failure analysis and auditing

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
