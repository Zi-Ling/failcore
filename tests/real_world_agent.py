#!/usr/bin/env python3
"""
FailCore v0.1.2 Example - Real-world Agent Security

Scenario: An AI data analyst agent that:
- Reads local CSV files
- Fetches external API data
- Writes analysis reports

This example demonstrates:
1. Tool metadata and risk classification
2. Automatic security validation (SSRF, path traversal)
3. Clear semantic status (BLOCKED vs FAIL)
4. HTML audit report generation
"""

from pathlib import Path
import tempfile
from failcore import Session
from failcore.core.tools.metadata import ToolMetadata, RiskLevel, SideEffect, DefaultAction


def setup_test_environment():
    """Create a temporary workspace with sample data"""
    workspace = Path(tempfile.mkdtemp(prefix="failcore_demo_"))
    
    # Create sample data file
    data_file = workspace / "sales_data.csv"
    data_file.write_text("date,amount\n2024-01-01,1000\n2024-01-02,1500\n")
    
    # Create reports directory
    reports_dir = workspace / "reports"
    reports_dir.mkdir()
    
    print(f"✓ Test workspace created: {workspace}")
    return workspace


def register_agent_tools(session: Session, workspace: Path):
    """Register tools with v0.1.2 security metadata"""
    
    # Tool 1: Read CSV file (Medium risk - read operation)
    # The auto-assembler will add path traversal checks based on side_effect=READ
    def read_csv(file_path: str) -> str:
        """Read CSV file and return contents"""
        full_path = workspace / file_path
        return full_path.read_text()
    
    session.register(
        "read_csv",
        read_csv,
        metadata=ToolMetadata(
            risk_level=RiskLevel.MEDIUM,
            side_effect=SideEffect.FS,
            default_action=DefaultAction.ALLOW
        )
    )
    
    # Tool 2: Fetch API data (High risk - network operation)
    # The auto-assembler will add SSRF protection based on side_effect=NETWORK
    # Note: Basic SSRF checks (internal IPs, private networks) are auto-added.
    # For domain allowlisting, use Session(validator=net_safe(allowed_domains=[...]))
    def fetch_api(url: str) -> str:
        """Simulate fetching data from external API"""
        # In real scenario, use requests library
        return f"{{\"data\": \"mock response from {url}\"}}"
    
    session.register(
        "fetch_api",
        fetch_api,
        metadata=ToolMetadata(
            risk_level=RiskLevel.HIGH,
            side_effect=SideEffect.NETWORK,
            default_action=DefaultAction.BLOCK
        )
    )
    
    # Tool 3: Write report (High risk - write operation)
    # The auto-assembler will add path traversal checks based on side_effect=WRITE
    def write_report(filename: str, content: str) -> str:
        """Write analysis report to file"""
        report_path = workspace / "reports" / filename
        report_path.write_text(content)
        return f"Report written: {filename}"
    
    session.register(
        "write_report",
        write_report,
        metadata=ToolMetadata(
            risk_level=RiskLevel.HIGH,
            side_effect=SideEffect.FS,
            default_action=DefaultAction.BLOCK
        )
    )
    
    print("✓ Agent tools registered with security metadata")
    print("  (Auto-assembled: path traversal checks, SSRF protection)")


def simulate_agent_workflow(session: Session):
    """Simulate AI agent performing data analysis tasks"""
    
    print("\n" + "="*70)
    print("SIMULATING AI AGENT WORKFLOW")
    print("="*70)
    
    # ==========================================
    # Scenario 1: Normal operation (should succeed)
    # ==========================================
    print("\n[1] Agent reads local data file...")
    result = session.call("read_csv", file_path="sales_data.csv")
    print(f"    Status: {result.status.value}")
    if result.output:
        lines = result.output.value.split('\n')
        print(f"    Output: {lines[0]} (and {len(lines)-1} more lines)")
    
    # ==========================================
    # Scenario 2: Path traversal attack (should be BLOCKED)
    # ==========================================
    print("\n[2] Agent attempts path traversal attack...")
    print("    Action: read_csv(file_path='../../../etc/passwd')")
    result = session.call("read_csv", file_path="../../../etc/passwd")
    print(f"    Status: {result.status.value} 🛡️")  # BLOCKED
    if result.error:
        print(f"    Threat: {result.error.error_code}")
        print(f"    Message: {result.error.message}")
    
    # ==========================================
    # Scenario 3: SSRF attack (should be BLOCKED)
    # ==========================================
    print("\n[3] Agent attempts SSRF attack on internal network...")
    print("    Action: fetch_api(url='http://127.0.0.1:8080/admin')")
    result = session.call("fetch_api", url="http://127.0.0.1:8080/admin")
    print(f"    Status: {result.status.value} 🛡️")  # BLOCKED
    if result.error:
        print(f"    Threat: {result.error.error_code}")
        print(f"    Message: {result.error.message}")
    
    # ==========================================
    # Scenario 4: External API call (no domain filtering in this demo)
    # ==========================================
    print("\n[4] Agent fetches from external API...")
    print("    Action: fetch_api(url='https://api.example.com/stats')")
    print("    Note: Domain allowlisting requires Session(validator=net_safe(...))")
    result = session.call("fetch_api", url="https://api.example.com/stats")
    print(f"    Status: {result.status.value}")
    if result.output:
        print(f"    Output: {result.output.value[:50]}...")
    
    # ==========================================
    # Scenario 5: Write report (should succeed)
    # ==========================================
    print("\n[5] Agent writes analysis report...")
    result = session.call(
        "write_report",
        filename="analysis_2024.txt",
        content="Sales Analysis Report\n\nTotal: $2500\n"
    )
    print(f"    Status: {result.status.value}")
    if result.output:
        print(f"    Output: {result.output.value}")
    
    # ==========================================
    # Scenario 6: Sandbox escape attempt (should be BLOCKED)
    # ==========================================
    print("\n[6] Agent attempts to write outside sandbox...")
    print("    Action: write_report(filename='../../etc/cron.d/backdoor', ...)")
    result = session.call(
        "write_report",
        filename="../../etc/cron.d/backdoor",
        content="* * * * * malicious command"
    )
    print(f"    Status: {result.status.value} 🛡️")  # BLOCKED
    if result.error:
        print(f"    Threat: {result.error.error_code}")
        print(f"    Message: {result.error.message}")


def print_summary(session: Session):
    """Print execution summary"""
    print("\n" + "="*70)
    print("EXECUTION SUMMARY")
    print("="*70)
    
    # Note: In real usage, you would query the trace file or session state
    print("\n✓ Trace recorded to:", session.trace_path if hasattr(session, 'trace_path') else "auto")
    print("\nTo view the security audit report:")
    print("  $ failcore report")
    print("\nTo view execution details:")
    print("  $ failcore show")


def main():
    """Main execution flow"""
    print("="*70)
    print("FailCore v0.1.2 - Real-world Agent Security Example")
    print("="*70)
    
    # Setup
    workspace = setup_test_environment()
    
    try:
        # Create session with tracing enabled
        with Session(
            trace="failcore_demo_trace.jsonl",
            sandbox=str(workspace)
        ) as session:
            
            # Register agent tools with security metadata
            register_agent_tools(session, workspace)
            
            # Simulate agent workflow (mix of safe and malicious actions)
            simulate_agent_workflow(session)
            
            # Print summary
            print_summary(session)
            
            print("\n" + "="*70)
            print("KEY TAKEAWAYS (v0.1.2 Features)")
            print("="*70)
            print("1. 🛡️  Tool Metadata: Attach risk_level, side_effect, default_action")
            print("2. 🔒 Auto-assembly: Path traversal/SSRF checks added based on side_effect")
            print("3. 🎯 Semantic Status: BLOCKED = prevented, FAIL = error, OK = success")
            print("4. 📊 audit Report: Run 'failcore report' for HTML security analysis")
            print("5. ✅ Simple API: session.register(name, fn, metadata=ToolMetadata(...))")
            
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(workspace, ignore_errors=True)
        print("\n✓ Workspace cleaned up")


if __name__ == "__main__":
    main()
