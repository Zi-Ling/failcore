"""
Tests for Execution Receipt (P2-2)

Must:
- Auto-generate receipt after tool call
- Support deterministic replay
- Include receipt_id in trace
"""

import pytest
import tempfile
from pathlib import Path
from failcore.core.receipt.receipt import Receipt, ReceiptStore
from failcore.core.step.step import StepResult, StepError, StepStatus


class TestReceiptGeneration:
    """Test automatic receipt generation"""
    
    def test_create_receipt_from_success(self):
        """Should create receipt from successful tool call"""
        
        from failcore.core.step.step import StepOutput, OutputKind
        
        # Mock a successful StepResult
        step_result = StepResult(
            step_id="s0001",
            tool="write_file",
            status=StepStatus.OK,  # OK, not SUCCESS
            output=StepOutput(kind=OutputKind.TEXT, value="Wrote 10 bytes"),
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:00:01Z",
            duration_ms=1000
        )
        
        step_params = {"path": "test.txt", "content": "hello"}
        
        context = {
            "sandbox": "./workspace",
            "policy_version": "1.0",
            "policy_decision": "ALLOWED"
        }
        
        receipt = Receipt.from_step_result(step_result, "run-001", step_params, context)
        
        # Verify receipt structure
        assert receipt.run_id == "run-001"
        assert receipt.step_id == "s0001"
        assert receipt.tool_name == "write_file"
        assert "OK" in receipt.status or "ok" in receipt.status  # StepStatus.OK
        assert receipt.params_hash is not None
        assert len(receipt.params_hash) == 64  # SHA256
        assert receipt.output_hash is not None
        assert receipt.sandbox == "./workspace"
        assert receipt.error_code is None
    
    def test_create_receipt_from_error(self):
        """Should create receipt from failed tool call with error structure"""
        
        # Mock a failed StepResult with FailCoreError
        from failcore.core.errors import codes
        
        error = StepError(
            error_code=codes.SANDBOX_VIOLATION,
            message="Path traversal detected",
            detail={
                "suggestion": "Use relative paths within sandbox",
                "remediation": {
                    "action": "fix_path",
                    "template": "{sandbox}/{basename}",
                    "vars": {"sandbox": "./workspace", "basename": "file.txt"}
                }
            }
        )
        
        step_result = StepResult(
            step_id="s0002",
            tool="write_file",
            status=StepStatus.BLOCKED,
            error=error,
            started_at="2024-01-01T00:00:02Z",
            finished_at="2024-01-01T00:00:03Z",
            duration_ms=50
        )
        
        step_params = {"path": "../evil.txt"}
        
        receipt = Receipt.from_step_result(step_result, "run-001", step_params, {})
        
        # Verify error structure in receipt
        assert "BLOCKED" in receipt.status or "blocked" in receipt.status
        assert receipt.error_code == codes.SANDBOX_VIOLATION
        assert receipt.error_message == "Path traversal detected"
        assert receipt.error_suggestion == "Use relative paths within sandbox"
        assert receipt.error_remediation is not None
        assert "action" in receipt.error_remediation
        assert receipt.output_hash is None  # No output on error


class TestReceiptStore:
    """Test receipt storage and retrieval"""
    
    def test_save_and_load_receipt(self):
        """Should save receipt to disk and load it back"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReceiptStore(storage_path=tmpdir)
            
            # Create a receipt
            receipt = Receipt(
                receipt_id="rcpt_001",
                run_id="run-001",
                step_id="s0001",
                tool_name="test_tool",
                params_hash="abc123",
                params_summary={"arg": "value"},
                sandbox="./workspace",
                policy_version="1.0",
                policy_decision="ALLOWED",
                started_at="2024-01-01T00:00:00Z",
                finished_at="2024-01-01T00:00:01Z",
                duration_ms=1000,
                status="SUCCESS"
            )
            
            # Save
            store.save(receipt)
            
            # Verify file exists
            receipt_file = Path(tmpdir) / "run-001" / "s0001.json"
            assert receipt_file.exists()
            
            # Load back
            loaded = store.load("run-001", "s0001")
            assert loaded is not None
            assert loaded.receipt_id == "rcpt_001"
            assert loaded.tool_name == "test_tool"
            assert loaded.status == "SUCCESS"
    
    def test_list_receipts_for_run(self):
        """Should list all receipts for a run"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReceiptStore(storage_path=tmpdir)
            
            # Create multiple receipts
            for i in range(3):
                receipt = Receipt(
                    receipt_id=f"rcpt_{i:03d}",
                    run_id="run-001",
                    step_id=f"s{i:04d}",
                    tool_name=f"tool_{i}",
                    params_hash=f"hash_{i}",
                    params_summary={},
                    sandbox="./workspace",
                    policy_version="1.0",
                    policy_decision="ALLOWED",
                    started_at="2024-01-01T00:00:00Z",
                    finished_at="2024-01-01T00:00:01Z",
                    duration_ms=1000,
                    status="SUCCESS"
                )
                store.save(receipt)
            
            # List receipts
            receipts = store.list_for_run("run-001")
            assert len(receipts) == 3
            assert all(r.run_id == "run-001" for r in receipts)


class TestDeterministicReplay:
    """Test replay from receipt"""
    
    def test_enable_replay(self):
        """Should enable deterministic replay on receipt"""
        
        receipt = Receipt(
            receipt_id="rcpt_replay",
            run_id="run-001",
            step_id="s0001",
            tool_name="expensive_tool",
            params_hash="abc123",
            params_summary={"input": "data"},
            sandbox="./workspace",
            policy_version="1.0",
            policy_decision="ALLOWED",
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:00:01Z",
            duration_ms=5000,
            status="SUCCESS",
            output_hash="def456"
        )
        
        # Enable replay with cached result
        cached_result = {"data": "cached output"}
        receipt.enable_replay(cached_result)
        
        assert receipt.replay_enabled is True
        assert receipt.replay_result == cached_result
    
    def test_can_replay(self):
        """Should check if receipt can be replayed"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReceiptStore(storage_path=tmpdir)
            
            # Receipt without replay enabled
            receipt1 = Receipt(
                receipt_id="rcpt_no_replay",
                run_id="run-001",
                step_id="s0001",
                tool_name="tool",
                params_hash="hash",
                params_summary={},
                sandbox="./workspace",
                policy_version="1.0",
                policy_decision="ALLOWED",
                started_at="2024-01-01T00:00:00Z",
                finished_at="2024-01-01T00:00:01Z",
                duration_ms=1000,
                status="SUCCESS"
            )
            
            assert not store.can_replay(receipt1)
            
            # Receipt with replay enabled
            receipt2 = Receipt(
                receipt_id="rcpt_with_replay",
                run_id="run-001",
                step_id="s0002",
                tool_name="tool",
                params_hash="hash",
                params_summary={},
                sandbox="./workspace",
                policy_version="1.0",
                policy_decision="ALLOWED",
                started_at="2024-01-01T00:00:00Z",
                finished_at="2024-01-01T00:00:01Z",
                duration_ms=1000,
                status="SUCCESS"
            )
            receipt2.enable_replay({"result": "cached"})
            
            assert store.can_replay(receipt2)
    
    def test_find_last_success_for_resume(self):
        """Should find last successful step for workflow resume"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReceiptStore(storage_path=tmpdir)
            
            # Create a workflow with multiple steps
            statuses = ["SUCCESS", "SUCCESS", "FAIL", "SUCCESS"]
            for i, status in enumerate(statuses):
                receipt = Receipt(
                    receipt_id=f"rcpt_{i:03d}",
                    run_id="run-001",
                    step_id=f"s{i:04d}",
                    tool_name=f"tool_{i}",
                    params_hash=f"hash_{i}",
                    params_summary={},
                    sandbox="./workspace",
                    policy_version="1.0",
                    policy_decision="ALLOWED",
                    started_at="2024-01-01T00:00:00Z",
                    finished_at="2024-01-01T00:00:01Z",
                    duration_ms=1000,
                    status=status
                )
                store.save(receipt)
            
            # Find last success
            last_success = store.find_last_success("run-001")
            assert last_success is not None
            assert last_success.step_id == "s0003"  # Last success
            assert last_success.status == "SUCCESS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
