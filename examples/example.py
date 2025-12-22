"""
FailCore Basic Usage Example

This example demonstrates:
1. Creating a session with automatic tracing
2. Registering tools (functions)
3. Calling tools and handling results
4. Viewing success and failure cases
"""

from failcore import Session


def main():
    print("=" * 60)
    print("FailCore Basic Example")
    print("=" * 60)
    
    # Create a session with automatic trace recording
    with Session() as session:
        
        # ===== Example 1: Register and call a simple tool =====
        print("\n📌 Example 1: Simple calculation (success case)")
        print("-" * 60)
        
        session.register("add", lambda a, b: a + b)
        result = session.call("add", a=10, b=20)
        
        print(f"Status: {result.status.value}")
        print(f"Output: {result.output.value}")
        
        
        # ===== Example 2: Handle errors gracefully =====
        print("\n📌 Example 2: Division by zero (error case)")
        print("-" * 60)
        
        session.register("divide", lambda a, b: a / b)
        result = session.call("divide", a=10, b=0)
        
        print(f"Status: {result.status.value}")
        if result.error:
            print(f"Error Code: {result.error.error_code}")
            print(f"Error Message: {result.error.message}")
        
        
        # ===== Example 3: Register tool with decorator =====
        print("\n📌 Example 3: Using decorator to register tool")
        print("-" * 60)
        
        @session.tool
        def multiply(x: int, y: int) -> int:
            """Multiply two numbers"""
            return x * y
        
        result = session.call("multiply", x=7, y=6)
        print(f"Status: {result.status.value}")
        print(f"Output: {result.output.value}")
        
        
        # ===== Example 4: Tool with complex return type =====
        print("\n📌 Example 4: Tool returning dictionary")
        print("-" * 60)
        
        @session.tool
        def get_user_info(user_id: int) -> dict:
            """Get user information"""
            return {
                "id": user_id,
                "name": "Alice",
                "role": "admin"
            }
        
        result = session.call("get_user_info", user_id=123)
        print(f"Status: {result.status.value}")
        print(f"Output: {result.output.value}")
        print(f"Output Kind: {result.output.kind}")
    
    
    # After session ends, trace is automatically saved
    print("\n" + "=" * 60)
    print("✅ Session completed! Trace saved automatically.")
    print("=" * 60)
    print("\nTo view the trace, run:")
    print("  failcore show")
    print("\nTo list all traces, run:")
    print("  failcore list")
    print()


if __name__ == "__main__":
    main()

