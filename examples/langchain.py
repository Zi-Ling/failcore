"""
Example 1: Pure LangChain Approach (Baseline)

Demonstrates issues compared to FailCore v0.1.2:
1. Errors are Python exceptions, not business error codes
2. No trace recording - cannot analyze or replay
3. Hard to locate which step failed
4. No resource usage tracking (tokens/cost)
5. No provenance - can't trace where decisions came from
6. No validation before execution
7. No policy enforcement
"""

from langchain_core.tools import tool
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
    print("Example 1: Pure LangChain Approach")
    print("=" * 60)
    
    # Simulate a simple Agent workflow
    try:
        # Step 1: Write file
        print("\n[Step 1] Write file...")
        result1 = write_file.invoke({"path": "temp_data.txt", "content": "Hello FailCore"})
        print(f"[OK] Success: {result1}")
        
        # Step 2: Read non-existent file (will fail)
        print("\n[Step 2] Read non-existent file...")
        result2 = read_file.invoke({"path": "missing.txt"})
        print(f"[OK] Success: {result2}")
        
        # Step 3: Read existing file
        print("\n[Step 3] Read existing file...")
        result3 = read_file.invoke({"path": "temp_data.txt"})
        print(f"[OK] Success: {result3}")
        
    except FileNotFoundError as e:
        print(f"\n[ERROR] Python Exception: {e}")
        print("\nProblem Analysis:")
        print("  1. Don't know which step failed (need to check stack trace)")
        print("  2. Error type is Python exception, not business error code")
        print("  3. No trace, cannot replay and analyze")
        print("  4. Previous successful steps are not recorded")
        
    except Exception as e:
        print(f"\n[ERROR] Unknown Exception: {type(e).__name__}: {e}")
    
    finally:
        # Clean up
        if os.path.exists("temp_data.txt"):
            os.remove("temp_data.txt")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

