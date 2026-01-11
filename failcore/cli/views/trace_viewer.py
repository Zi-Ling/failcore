"""
P1-3: Trace Viewer (CLI first, Web later)

Read-only trace viewer for debugging and analysis
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter


class TraceViewer:
    """
    CLI trace viewer for FailCore execution traces
    
    Reads JSONL trace files and provides analysis
    """
    
    def __init__(self, trace_dir: str = "./.failcore/traces"):
        self.trace_dir = Path(trace_dir)
    
    def list_traces(self) -> List[Dict[str, Any]]:
        """List all available traces"""
        if not self.trace_dir.exists():
            return []
        
        traces = []
        for trace_file in self.trace_dir.rglob("*.jsonl"):
            traces.append({
                "file": str(trace_file),
                "name": trace_file.stem,
                "size": trace_file.stat().st_size,
            })
        
        return sorted(traces, key=lambda t: t["name"], reverse=True)
    
    def read_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Read a trace by ID"""
        # Try to find trace file
        for trace_file in self.trace_dir.rglob(f"*{trace_id}*.jsonl"):
            return self._read_jsonl(trace_file)
        
        return []
    
    def _read_jsonl(self, filepath: Path) -> List[Dict[str, Any]]:
        """Read JSONL file"""
        events = []
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events
    
    def display_trace(self, trace_id: str):
        """Display trace timeline"""
        events = self.read_trace(trace_id)
        
        if not events:
            print(f"Trace {trace_id} not found")
            return
        
        print("\n" + "="*70)
        print(f"Trace: {trace_id}")
        print("="*70)
        
        # Group by step
        steps = defaultdict(list)
        for event in events:
            step_id = event.get("step_id", "unknown")
            steps[step_id].append(event)
        
        # Display timeline
        print("\n[Timeline]")
        for step_id, step_events in steps.items():
            self._display_step(step_id, step_events)
        
        # Display summary
        self._display_summary(events)
    
    def _display_step(self, step_id: str, events: List[Dict]):
        """Display a single step"""
        start_event = next((e for e in events if e.get("type") == "STEP_START"), None)
        end_event = next((e for e in events if e.get("type") == "STEP_END"), None)
        
        if not start_event:
            return
        
        tool = start_event.get("tool", "unknown")
        status = end_event.get("status", "UNKNOWN") if end_event else "RUNNING"
        
        print(f"\n  [{step_id}] {tool}")
        print(f"    Status: {status}")
        
        if end_event:
            duration = end_event.get("duration_ms", 0)
            print(f"    Duration: {duration}ms")
            
            if status in ["FAIL", "BLOCKED"]:
                error = end_event.get("error", {})
                if error:
                    print(f"    Error: [{error.get('code')}] {error.get('message', '')[:60]}")
    
    def _display_summary(self, events: List[Dict]):
        """Display summary statistics"""
        print("\n" + "="*70)
        print("Summary")
        print("="*70)
        
        # Count by status
        status_counts = Counter()
        tool_counts = Counter()
        error_codes = Counter()
        
        for event in events:
            if event.get("type") == "STEP_END":
                status = event.get("status", "UNKNOWN")
                status_counts[status] += 1
                
                tool = event.get("tool")
                if tool:
                    tool_counts[tool] += 1
                
                error = event.get("error", {})
                if error:
                    code = error.get("code")
                    if code:
                        error_codes[code] += 1
        
        print(f"\nTotal Steps: {sum(status_counts.values())}")
        print(f"  Success: {status_counts.get('SUCCESS', 0)}")
        print(f"  Failed: {status_counts.get('FAIL', 0)}")
        print(f"  Blocked: {status_counts.get('BLOCKED', 0)}")
        
        if tool_counts:
            print(f"\nTop Tools:")
            for tool, count in tool_counts.most_common(5):
                print(f"  {tool}: {count}")
        
        if error_codes:
            print(f"\nError Codes:")
            for code, count in error_codes.most_common(5):
                print(f"  {code}: {count}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all traces"""
        all_traces = self.list_traces()
        
        total_steps = 0
        success_count = 0
        fail_count = 0
        blocked_count = 0
        error_codes = Counter()
        tool_counts = Counter()
        retry_success = 0
        retry_total = 0
        
        for trace_info in all_traces:
            events = self._read_jsonl(Path(trace_info["file"]))
            
            for event in events:
                if event.get("type") == "STEP_END":
                    total_steps += 1
                    status = event.get("status", "UNKNOWN")
                    
                    if status == "SUCCESS":
                        success_count += 1
                    elif status == "FAIL":
                        fail_count += 1
                    elif status == "BLOCKED":
                        blocked_count += 1
                    
                    tool = event.get("tool")
                    if tool:
                        tool_counts[tool] += 1
                    
                    error = event.get("error", {})
                    if error:
                        code = error.get("code")
                        if code:
                            error_codes[code] += 1
                    
                    # Track retry attempts
                    attempt = event.get("attempt", 1)
                    if attempt > 1:
                        retry_total += 1
                        if status == "SUCCESS":
                            retry_success += 1
        
        return {
            "total_steps": total_steps,
            "success_count": success_count,
            "fail_count": fail_count,
            "blocked_count": blocked_count,
            "success_rate": success_count / total_steps if total_steps > 0 else 0,
            "retry_success_rate": retry_success / retry_total if retry_total > 0 else 0,
            "top_tools": dict(tool_counts.most_common(10)),
            "error_codes": dict(error_codes.most_common(10)),
        }


def main():
    """CLI entry point"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m failcore.cli.trace_viewer <command> [args]")
        print("\nCommands:")
        print("  list                 - List all traces")
        print("  view <trace_id>      - View a specific trace")
        print("  metrics              - Show aggregated metrics")
        return
    
    command = sys.argv[1]
    viewer = TraceViewer()
    
    if command == "list":
        traces = viewer.list_traces()
        print(f"\nFound {len(traces)} traces:")
        for trace in traces[:20]:  # Show latest 20
            print(f"  {trace['name']} ({trace['size']} bytes)")
    
    elif command == "view":
        if len(sys.argv) < 3:
            print("Error: trace_id required")
            return
        trace_id = sys.argv[2]
        viewer.display_trace(trace_id)
    
    elif command == "metrics":
        metrics = viewer.get_metrics()
        print("\n" + "="*70)
        print("Aggregated Metrics")
        print("="*70)
        print(f"\nTotal Steps: {metrics['total_steps']}")
        print(f"Success: {metrics['success_count']} ({metrics['success_rate']*100:.1f}%)")
        print(f"Failed: {metrics['fail_count']}")
        print(f"Blocked: {metrics['blocked_count']}")
        print(f"Retry Success Rate: {metrics['retry_success_rate']*100:.1f}%")
        
        if metrics['top_tools']:
            print(f"\nTop Tools:")
            for tool, count in list(metrics['top_tools'].items())[:5]:
                print(f"  {tool}: {count}")
        
        if metrics['error_codes']:
            print(f"\nError Codes:")
            for code, count in list(metrics['error_codes'].items())[:5]:
                print(f"  {code}: {count}")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()


__all__ = ["TraceViewer"]
