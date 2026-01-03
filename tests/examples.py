"""
FailCore Usage Example - Real-world scenarios

This demonstrates how users would actually use FailCore in their projects.
"""

import json
import tempfile
from pathlib import Path


def example_1_simple_agent_tools():
    """
    Example 1: Building a simple agent with file and calculation tools.
    
    A user wants to create an agent that can:
    - Read/write files
    - Perform calculations
    - Have all actions traced for debugging
    """
    from failcore import Session, presets
    import sys
    
    print("\n" + "="*70)
    print("Example 1: Simple Agent with File & Calculation Tools")
    print("="*70 + "\n")
    
    # Create a session with auto trace
    with Session() as session:
        # Register calculation tools
        @session.tool
        def calculate_total(items: list) -> float:
            """Calculate total price of items"""
            return sum(item.get('price', 0) for item in items)
        
        @session.tool
        def apply_discount(amount: float, discount_percent: float) -> float:
            """Apply discount to amount"""
            return amount * (1 - discount_percent / 100)
        
        # Register file tools
        @session.tool
        def save_report(data: dict, filename: str) -> str:
            """Save report to file"""
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            return f"Report saved to {filename}"
        
        # Simulate agent workflow
        print("Agent Task: Calculate order total with discount and save report\n")
        
        # Step 1: Calculate total
        order_items = [
            {"name": "Widget A", "price": 29.99},
            {"name": "Widget B", "price": 49.99},
            {"name": "Widget C", "price": 19.99}
        ]
        
        result = session.call("calculate_total", items=order_items)
        total = result.output.value
        print(f"Step 1: Calculate total")
        print(f"  Result: ${total:.2f}")
        print(f"  Status: {result.status.value}\n")
        
        # Step 2: Apply discount
        result = session.call("apply_discount", amount=total, discount_percent=15)
        final_amount = result.output.value
        print(f"Step 2: Apply 15% discount")
        print(f"  Result: ${final_amount:.2f}")
        print(f"  Status: {result.status.value}\n")
        
        # Step 3: Save report
        report = {
            "order_items": order_items,
            "subtotal": total,
            "discount": "15%",
            "final_amount": final_amount
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report_path = f.name
        
        result = session.call("save_report", data=report, filename=report_path)
        print(f"Step 3: Save report")
        print(f"  Result: {result.output.value}")
        print(f"  Status: {result.status.value}\n")
        
        run_id = session.run_id
        trace_path = session._trace_path
        
        print(f"✓ All steps completed!")
        print(f"✓ Trace saved to: .failcore/runs/{run_id}_*/trace.jsonl")
        print(f"✓ Auto-ingested to database: .failcore/failcore.db")
        print(f"  Use 'failcore show --last' to view execution details")
    
    # Debug: Check if trace file exists after session closes
    print(f"Debug: Trace file exists after close: {Path(trace_path).exists()}", file=sys.stderr)
    print()
    
    # Cleanup
    Path(report_path).unlink(missing_ok=True)


def example_2_safe_file_operations():
    """
    Example 2: Safe file operations with validation.
    
    A user wants to ensure file operations are safe:
    - Read operations check file exists
    - Write operations validate paths
    - All operations are traced
    """
    from failcore import Session, presets
    
    print("\n" + "="*70)
    print("Example 2: Safe File Operations with Validation")
    print("="*70 + "\n")
    
    # Create test directory
    test_dir = Path(tempfile.mkdtemp())
    test_file = test_dir / "data.txt"
    test_file.write_text("Hello, FailCore!")
    
    # Session with file system safety validator
    with Session(validator=presets.fs_safe()) as session:
        @session.tool
        def read_file(path: str) -> str:
            """Read file content"""
            return Path(path).read_text()
        
        @session.tool
        def write_file(path: str, content: str) -> str:
            """Write content to file"""
            Path(path).write_text(content)
            return f"Written {len(content)} bytes to {path}"
        
        print("Task: Read and process file safely\n")
        
        # Safe operation: Read existing file
        print(f"1. Reading existing file: {test_file.name}")
        result = session.call("read_file", path=str(test_file))
        if result.status.value == "ok":
            print(f"   ✓ Content: {result.output.value}")
        else:
            print(f"   ✗ Failed: {result.error.message if result.error else 'Unknown'}")
        
        # Unsafe operation: Read non-existent file (validator will catch this)
        print(f"\n2. Attempting to read non-existent file")
        result = session.call("read_file", path=str(test_dir / "missing.txt"))
        if result.status.value == "ok":
            print(f"   ✓ Success")
        else:
            print(f"   ✗ Blocked by validator: {result.error.message if result.error else 'Validation failed'}")
        
        # Safe operation: Write to new file
        print(f"\n3. Writing to new file")
        new_file = test_dir / "output.txt"
        result = session.call("write_file", path=str(new_file), content="Processed data")
        if result.status.value == "ok":
            print(f"   ✓ {result.output.value}")
        else:
            print(f"   ✗ Failed: {result.error.message if result.error else 'Unknown'}")
        
        print(f"\n✓ File operations completed with safety checks")
        print(f"✓ Validator prevented unsafe operations automatically\n")
    
    # Cleanup
    for f in test_dir.glob("*"):
        f.unlink()
    test_dir.rmdir()


def example_3_controlled_agent():
    """
    Example 3: Agent with policy restrictions.
    
    A user wants an agent that can only perform read operations,
    no write/delete actions allowed.
    """
    from failcore import Session, presets
    
    print("\n" + "="*70)
    print("Example 3: Read-Only Agent with Policy Control")
    print("="*70 + "\n")
    
    # Session with read-only policy
    with Session(policy=presets.read_only()) as session:
        @session.tool
        def fetch_data(source: str) -> dict:
            """Fetch data from source"""
            # Simulate data fetching
            return {"source": source, "data": [1, 2, 3, 4, 5]}
        
        @session.tool
        def analyze_data(numbers: list) -> dict:
            """Analyze numbers"""
            return {
                "count": len(numbers),
                "sum": sum(numbers),
                "average": sum(numbers) / len(numbers) if numbers else 0
            }
        
        @session.tool
        def delete_cache(path: str) -> str:
            """Delete cache file (dangerous operation)"""
            return f"Deleted {path}"
        
        print("Agent Task: Fetch and analyze data (read-only mode)\n")
        
        # Allowed: Read operations
        print("1. Fetching data (allowed)")
        result = session.call("fetch_data", source="database")
        if result.status.value == "ok":
            data = result.output.value
            print(f"   ✓ Fetched: {data}")
        
        print("\n2. Analyzing data (allowed)")
        result = session.call("analyze_data", numbers=data['data'])
        if result.status.value == "ok":
            print(f"   ✓ Analysis: {result.output.value}")
        
        # Blocked: Write/delete operations
        print("\n3. Attempting to delete cache (blocked by policy)")
        result = session.call("delete_cache", path="/tmp/cache.db")
        if result.status.value == "ok":
            print(f"   ✓ Success: {result.output.value}")
        else:
            print(f"   ✗ Policy blocked: {result.error.message if result.error else 'Unknown'}")
        
        print(f"\n✓ Agent stayed within read-only boundaries")
        print(f"✓ Policy enforcement prevents dangerous operations\n")


def example_4_debugging_with_trace():
    """
    Example 4: Using trace for debugging agent behavior.
    
    When things go wrong, trace helps understand what happened.
    """
    from failcore import Session
    
    print("\n" + "="*70)
    print("Example 4: Debugging Agent with Trace")
    print("="*70 + "\n")
    
    with Session() as session:
        @session.tool
        def process_data(value: int) -> int:
            """Process data value"""
            if value < 0:
                raise ValueError("Value must be positive")
            return value * 2
        
        @session.tool
        def format_output(value: int) -> str:
            """Format output"""
            return f"Result: {value}"
        
        print("Workflow: Process and format values\n")
        
        values = [10, 20, -5, 30]  # One invalid value
        
        for i, val in enumerate(values, 1):
            print(f"{i}. Processing value: {val}")
            result = session.call("process_data", value=val)
            
            if result.status.value == "ok":
                formatted = session.call("format_output", value=result.output.value)
                print(f"   ✓ {formatted.output.value}")
            else:
                print(f"   ✗ Failed: {result.error.message if result.error else 'Unknown error'}")
                print(f"   → Step ID: {result.step_id} (check trace for details)")
        
        print(f"\n✓ Workflow completed with errors")
        print(f"✓ Failed steps recorded in trace and database")
        print(f"  - Trace file: .failcore/runs/{session.run_id}_*/trace.jsonl")
        print(f"  - Database: .failcore/failcore.db (auto-ingested)")
        print(f"\n  Debug commands:")
        print(f"    failcore show --last          # View execution summary")
        print(f"    failcore show --last --errors # View only errors")
        print()


def example_5_production_agent():
    """
    Example 5: Production-ready agent with all features.
    
    Combining policy, validator, and trace for production use.
    """
    from failcore import Session, presets
    
    print("\n" + "="*70)
    print("Example 5: Production Agent with Full Protection")
    print("="*70 + "\n")
    
    # Production-grade session
    with Session(
        validator=presets.fs_safe(),    # File safety
        policy=presets.read_only(),     # Read-only mode
        tags={"env": "production", "version": "1.0"}
    ) as session:
        # Register demo tools for this example
        for name, fn in presets.demo_tools().items():
            session.register(name, fn)
        
        @session.tool
        def get_user_info(user_id: str) -> dict:
            """Get user information"""
            return {"user_id": user_id, "name": "Alice", "role": "admin"}
        
        print("Production Agent: Safe execution with multiple protections\n")
        
        # Safe operations
        print("1. Getting user info")
        result = session.call("get_user_info", user_id="123")
        print(f"   Status: {result.status.value}")
        
        print("\n2. Using demo calculation")
        result = session.call("demo.divide", a=100, b=4)
        print(f"   Result: {result.output.value if result.status.value == 'ok' else 'Failed'}")
        
        print("\n3. Echoing message")
        result = session.call("demo.echo", text="Production system running")
        print(f"   Message: {result.output.value if result.status.value == 'ok' else 'Failed'}")
        
        print(f"\n✓ Production agent executed safely")
        print(f"✓ All operations traced, validated, and auto-ingested to database")
        print(f"✓ Run ID: {session.run_id}\n")


def main():
    """Run all usage examples."""
    print("\n" + "="*70)
    print("  FailCore - Real-World Usage Examples")
    print("  Version: 0.1.0a2")
    print("="*70)
    
    example_1_simple_agent_tools()
    example_2_safe_file_operations()
    example_3_controlled_agent()
    example_4_debugging_with_trace()
    example_5_production_agent()
    
    print("="*70)
    print("  All examples completed!")
    print("  ")
    print("  ✓ All traces automatically ingested to .failcore/failcore.db")
    print("  ")
    print("  Next steps:")
    print("    - Run 'failcore list' to see all runs")
    print("    - Run 'failcore show --last' for details")
    print("    - Check .failcore/runs/ for trace files")
    print("  ")
    print("  Note: No need to run 'failcore trace ingest' - it's automatic!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
