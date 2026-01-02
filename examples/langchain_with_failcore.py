"""
Example 2: LangChain + FailCore Integration (Thin Adapter)

Using: FailCore v0.1.2 Trace Schema
- Enhanced provenance tracking
- Resource usage monitoring
- Contract drift detection
- Granular severity levels (ok/warn/block)

Advantages:
1. Clear error types (PRECONDITION_FAILED)
2. Complete trace recording (analyzable, replayable)
3. Errors are rejected at the Validate layer, no need to wait for execution
4. All steps have execution records
5. Thin adapter - only translates, no execution logic
"""

from langchain_core.tools import tool
from failcore import Session, StepStatus
from failcore.adapters.integrations.langchain import map_langchain_tool
import os


@tool
def write_file(path: str, content: str) -> str:
    """Write file"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"Wrote {len(content)} bytes to {path}"


@tool
def read_file(path: str) -> str:
    """Read file"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def main():
    print("=" * 60)
    print("Example 2: LangChain + FailCore (Thin Adapter)")
    print("Using Trace Schema: v0.1.2")
    print("=" * 60)
    
    # Clean up old trace
    trace_path = ".failcore/examples/langchain_demo.jsonl"
    os.makedirs(os.path.dirname(trace_path), exist_ok=True)
    if os.path.exists(trace_path):
        os.remove(trace_path)
    
    # 1. Create FailCore Session with strict security mode
    from failcore.presets.validators import fs_safe as fs_safe_direct
    
    session = Session(
        trace=trace_path,
        validator=fs_safe_direct(strict=True),  # v0.1.2+: strict mode enables path traversal defense
        run_id="langchain_demo_run"
    )
    
    # 2. Translate LangChain tools to ToolSpec (thin adapter layer)
    write_spec = map_langchain_tool(write_file)
    read_spec = map_langchain_tool(read_file)
    
    # 3. Register with invoker
    session.invoker.register_spec(write_spec)
    session.invoker.register_spec(read_spec)
    
    # 4. Execute via ToolInvoker (unified execution)
    try:
        # Step 1: Write file
        print("\n[Step 1] Write file...")
        result1 = session.invoker.invoke("write_file", path="temp_data.txt", content="Hello!")
        if result1.status == StepStatus.OK:
            print(f"[OK] {result1.output.value}")
        else:
            error_msg = result1.error.message if result1.error else "Unknown error"
            print(f"[ERROR] {error_msg}")
        
        # Step 2: Read non-existent file (validator will reject)
        print("\n[Step 2] Read non-existent file...")
        result2 = session.invoker.invoke("read_file", path="missing.txt")
        if result2.status == StepStatus.OK:
            print(f"[OK] {result2.output.value}")
        else:
            error_code = result2.error.error_code if result2.error else "UNKNOWN"
            error_msg = result2.error.message if result2.error else "Unknown error"
            print(f"[FAIL] {error_msg}")
            print(f"   -> Error code: {error_code}")
            print(f"   -> Rejected at Validate layer (before execution)")
        
        # Step 3: Read existing file
        print("\n[Step 3] Read existing file...")
        result3 = session.invoker.invoke("read_file", path="temp_data.txt")
        if result3.status == StepStatus.OK:
            print(f"[OK] {result3.output.value}")
        else:
            error_msg = result3.error.message if result3.error else "Unknown error"
            print(f"[ERROR] {error_msg}")
        
        # Step 4: Attempt path traversal attack (validator will block)
        print("\n[Step 4] Attempt path traversal (../ attack)...")
        result4 = session.invoker.invoke("write_file", path="../sensitive.txt", content="hack")
        if result4.status == StepStatus.FAIL:
            error_code = result4.error.error_code if result4.error else "UNKNOWN"
            error_msg = result4.error.message if result4.error else "Unknown error"
            if error_code == "PATH_TRAVERSAL":
                print(f"[BLOCKED] Path traversal detected (as expected)")
                print(f"   -> Error code: {error_code}")
                print(f"   -> {error_msg}")
                print(f"   -> Blocked at validation gate (strict mode)")
            else:
                print(f"[FAIL] Error code: {error_code}")
                print(f"   -> {error_msg}")
        elif result4.status == StepStatus.OK:
            print(f"[WARNING] Path traversal should have been blocked!")
        else:
            error_msg = result4.error.message if result4.error else "Unknown error"
            print(f"[ERROR] {error_msg}")
        
        print("\n" + "=" * 60)
        print("Architecture Advantages:")
        print("=" * 60)
        print("[OK] 1. Thin adapter - only translates LangChain → ToolSpec")
        print("[OK] 2. Execution in core - validation, policy, trace all work")
        print("[OK] 3. Structured error codes - PATH_TRAVERSAL, FILE_NOT_FOUND")
        print("[OK] 4. Framework-agnostic - easy to add other frameworks")
        print("[OK] 5. All 4 steps traced with complete execution records")
        print("[OK] 6. Security validation - path traversal defense (strict mode)")
        
        print("\n" + "=" * 60)
        print("Trace Analysis")
        print("=" * 60)
        print(f"Trace saved to: {trace_path}")
        print("\nWhat this demo proves:")
        print("  ✓ Complete execution tracing - all 4 steps recorded")
        print("  ✓ Structured error codes - PATH_TRAVERSAL, FILE_NOT_FOUND")
        print("  ✓ Path traversal defense - ../ attack blocked at validation gate")
        print("  ✓ Fail-fast validation - errors caught before tool execution")
        print("  ✓ Framework-agnostic design - LangChain tools wrapped cleanly")
        print("\nTrace events generated (current implementation):")
        print("  • STEP_START / STEP_END - tool invocations with status/phase/error_code")
        print("  • POLICY_DENIED - policy violations (if any)")
        print("  • Error codes embedded in STEP_END events")
        print("\nView trace:")
        print(f"  failcore show")
        print(f"  failcore list")
        
    finally:
        # Clean up
        if os.path.exists("temp_data.txt"):
            os.remove("temp_data.txt")
    
    print("=" * 60)


if __name__ == "__main__":
    main()

