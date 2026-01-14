# FailCore API: run() vs Session

## Overview

FailCore provides two APIs for tool execution:

1. **`run()` + `@guard()`** - Modern, recommended API
2. **`Session`** - Legacy API for backward compatibility

## Key Differences

### run() API (Recommended)

**Design Philosophy:**
- Context manager based (`with run(...) as ctx:`)
- Exception-based error handling (raises `FailCoreError` on failure)
- Decorator-friendly with `@guard()`
- Unified configuration across all tools

**Usage:**

```python
from failcore import run, guard

# Method 1: Explicit tool registration
with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
    ctx.tool(write_file)
    result = ctx.call("write_file", path="a.txt", content="hi")
    # Returns direct value or raises FailCoreError

# Method 2: Decorator style (recommended)
with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    write_file(path="a.txt", content="hi")  # Direct call
    # Returns direct value or raises FailCoreError
```

**Key Features:**
- ✅ Clean, Pythonic API
- ✅ Exception-based error handling
- ✅ Decorator support
- ✅ Automatic context management
- ✅ Type-safe (returns actual values, not wrapper objects)

### Session API (Legacy)

**Design Philosophy:**
- Object-oriented session management
- Result-based error handling (returns `StepResult`)
- Explicit method calls
- More verbose but more explicit

**Usage:**

```python
from failcore import Session

session = Session(trace="trace.jsonl")
session.register("divide", lambda a, b: a / b)
result = session.call("divide", a=6, b=2)

# Must check result status
if result.status == "ok":
    print(result.output.value)
else:
    print(result.error)

session.close()
```

**Key Features:**
- ✅ Backward compatible
- ✅ Explicit error handling
- ✅ No exceptions on tool failure
- ⚠️ More verbose
- ⚠️ Requires manual result checking

## When to Use Which?

### Use `run()` API if:
- ✅ Starting a new project
- ✅ You want clean, modern Python code
- ✅ You prefer exception-based error handling
- ✅ You want to use decorators

### Use `Session` API if:
- ✅ Maintaining existing codebase
- ✅ You need backward compatibility
- ✅ You prefer explicit result objects
- ✅ You want to avoid exceptions

## Technical Details

### Under the Hood

Both APIs share the same core components:
- Same `Executor` for tool execution
- Same `TraceRecorder` for tracing
- Same `ValidatorRegistry` for validation
- Same `Policy` for access control

The main difference is the **user-facing interface**:

```
run() API:
  with run() as ctx        → RunCtx wrapper
    ctx.call()             → Raises exceptions
    @guard()               → Auto-registers + calls

Session API:
  session = Session()      → Direct Session object
    session.call()         → Returns StepResult
```

### No Conflict

`run()` and `Session` do **not** conflict:
- They are **independent** entry points
- They can be used **side by side** in the same codebase
- They share the same core but have different interfaces

### Context Manager Behavior

**`run()` API:**
```python
with run(...) as ctx:
    # ctx is a RunCtx object
    # Automatically manages resources
    # Sets global context for @guard()
    pass
# Auto-closes on exit
```

**`Session` API:**
```python
with Session(...) as session:
    # session is a Session object
    # Automatically manages resources
    # No global context (no @guard() support)
    pass
# Auto-closes on exit
```

Both support context managers, but:
- `run()` also sets a **global context** for `@guard()`
- `Session` does **not** set global context

## Migration Guide

### From Session to run()

**Before (Session):**
```python
from failcore import Session

session = Session(trace="trace.jsonl")
session.register("divide", lambda a, b: a / b)
result = session.call("divide", a=6, b=2)

if result.status == "ok":
    print(result.output.value)
else:
    raise Exception(result.error["message"])

session.close()
```

**After (run):**
```python
from failcore import run

with run(trace="trace.jsonl") as ctx:
    ctx.tool(lambda a, b: a / b)
    ctx._tools.register("divide", lambda a, b: a / b)
    
    try:
        result = ctx.call("divide", a=6, b=2)
        print(result)
    except Exception as e:
        print(e)
```

**After (run + guard):**
```python
from failcore import run, guard

with run(trace="trace.jsonl") as ctx:
    @guard()
    def divide(a, b):
        return a / b
    
    try:
        result = divide(a=6, b=2)
        print(result)
    except Exception as e:
        print(e)
```

## Recommendation

**For new projects:** Use `run()` + `@guard()` API
- Cleaner code
- Better ergonomics
- Modern Python conventions

**For existing projects:** Keep using `Session` API
- No need to migrate
- Fully backward compatible
- Both APIs will be maintained

## Summary

| Feature | run() API | Session API |
|---------|-----------|-------------|
| Style | Context manager | Object-oriented |
| Error handling | Exceptions | Result objects |
| Decorator support | ✅ Yes (@guard) | ❌ No |
| Global context | ✅ Yes | ❌ No |
| Verbosity | Low | High |
| Type safety | High | Medium |
| Backward compat | N/A (new) | ✅ Yes |
| Recommended for | New projects | Legacy code |

**Bottom line:** `run()` and `Session` are **two different interfaces** to the same engine. Use whichever fits your needs better. There is **no conflict** - they coexist peacefully.
