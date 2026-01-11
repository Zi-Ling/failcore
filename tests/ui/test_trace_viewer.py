"""
Tests for Trace Viewer (P1-3)

Must read real trace store, not mock metrics
"""

import pytest
from pathlib import Path
from failcore.cli.views.trace_viewer import TraceViewer


class TestTraceViewer:
    """Test trace viewer with golden trace"""
    
    def test_read_golden_trace(self):
        """Should read and parse golden trace file"""
        # Use golden trace from tests directory
        trace_dir = Path(__file__).parent
        viewer = TraceViewer(trace_dir=str(trace_dir))
        
        # Read golden trace
        events = viewer._read_jsonl(trace_dir / "golden_trace.jsonl")
        
        assert len(events) == 10  # 5 start + 5 end
        assert events[0]["type"] == "STEP_START"
        assert events[1]["type"] == "STEP_END"
    
    def test_compute_real_metrics(self):
        """Should compute metrics from real trace data"""
        trace_dir = Path(__file__).parent
        
        # Create a fake trace file in temp location for metrics
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Copy golden trace
            shutil.copy(
                trace_dir / "golden_trace.jsonl",
                tmpdir_path / "test_trace.jsonl"
            )
            
            viewer = TraceViewer(trace_dir=str(tmpdir))
            metrics = viewer.get_metrics()
            
            # Verify real computation (not mock)
            assert metrics["total_steps"] == 5
            assert metrics["success_count"] == 3  # s0001, s0004, s0005
            assert metrics["fail_count"] == 1     # s0002
            assert metrics["blocked_count"] == 1  # s0003
            
            # Check success rate
            expected_rate = 3 / 5  # 60%
            assert abs(metrics["success_rate"] - expected_rate) < 0.01
            
            # Check top tools
            assert "write_file" in metrics["top_tools"]
            assert metrics["top_tools"]["write_file"] == 3
            
            # Check error codes
            assert "FILE_NOT_FOUND" in metrics["error_codes"]
            assert "SANDBOX_VIOLATION" in metrics["error_codes"]
    
    def test_display_trace_output(self, capsys):
        """Test trace display output (snapshot test)"""
        trace_dir = Path(__file__).parent
        
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Copy golden trace with recognizable name
            shutil.copy(
                trace_dir / "golden_trace.jsonl",
                tmpdir_path / "trace_test-run-001.jsonl"
            )
            
            viewer = TraceViewer(trace_dir=str(tmpdir))
            viewer.display_trace("test-run-001")
            
            captured = capsys.readouterr()
            output = captured.out
            
            # Verify output contains expected elements
            assert "Trace: test-run-001" in output
            assert "Timeline" in output
            assert "Summary" in output
            assert "write_file" in output
            assert "SUCCESS" in output
            assert "FAIL" in output or "BLOCKED" in output
    
    def test_retry_success_rate(self):
        """Should correctly calculate retry success rate"""
        trace_dir = Path(__file__).parent
        
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            shutil.copy(
                trace_dir / "golden_trace.jsonl",
                tmpdir_path / "test.jsonl"
            )
            
            viewer = TraceViewer(trace_dir=str(tmpdir))
            metrics = viewer.get_metrics()
            
            # Golden trace has 1 retry (attempt 2 on s0004, which succeeds)
            # retry_success = 1, retry_total = 1
            assert metrics["retry_success_rate"] == 1.0  # 100%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
