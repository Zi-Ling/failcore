"""
Tests for guard_tool context binding and async support

These are the 5 必须有的测试 (critical tests) that prove context isolation works.
"""

import pytest
import asyncio
from failcore import run, guard
from failcore.core.errors import FailCoreError, codes


def write_file(path: str, content: str) -> str:
    """Simple write function for testing"""
    with open(path, 'w') as f:
        f.write(content)
    return f"Wrote {len(content)} bytes"


async def async_write_file(path: str, content: str) -> str:
    """Async write function for testing"""
    # Simulate async operation
    await asyncio.sleep(0.001)
    with open(path, 'w') as f:
        f.write(content)
    return f"Wrote {len(content)} bytes (async)"


class TestGuardToolContext:
    """Test suite for guard_tool context handling"""
    
    def test_no_active_context_error(self):
        """
        Test 1: NoActiveContext
        Calling guard_tool outside run() should raise PRECONDITION_FAILED
        """
        try:
            from failcore.adapters.langchain import guard_tool
        except ImportError:
            pytest.skip("langchain-core not installed")
        
        # Create tool facade outside run()
        lc_tool = guard_tool("write_file", description="Write files")
        
        # Try to call without active context - should fail
        with pytest.raises(FailCoreError) as exc_info:
            lc_tool.invoke({"path": "test.txt", "content": "hello"})
        
        error = exc_info.value
        assert error.error_code == codes.PRECONDITION_FAILED
        assert error.error_type == "CONTEXT_ERROR"
        assert error.details["reason"] == "no_active_context"
        assert "run()" in error.message
    
    def test_tool_not_registered_error(self):
        """
        Test 2: ToolNotRegistered
        Calling unregistered tool inside run() should raise TOOL_NOT_FOUND
        """
        try:
            from failcore.adapters.langchain import guard_tool
        except ImportError:
            pytest.skip("langchain-core not installed")
        
        with run(policy="fs_safe", sandbox="./test_sandbox") as ctx:
            # Create tool facade but DON'T register the actual tool
            lc_tool = guard_tool("nonexistent_tool", description="Ghost tool")
            
            # Try to call unregistered tool - should fail
            with pytest.raises(FailCoreError) as exc_info:
                lc_tool.invoke({"param": "value"})
            
            error = exc_info.value
            assert error.error_code == codes.TOOL_NOT_FOUND
            assert error.error_type == "REGISTRY_ERROR"
            assert "nonexistent_tool" in error.message
            assert "guard()" in error.message
    
    def test_context_mismatch_strict_mode(self):
        """
        Test 3: ContextMismatch
        bind_context=True should reject cross-context calls
        """
        try:
            from failcore.adapters.langchain import guard_tool
        except ImportError:
            pytest.skip("langchain-core not installed")
        
        # Create tool in first context with bind_context=True
        with run(policy="fs_safe", sandbox="./test_sandbox1") as ctx1:
            guard(write_file, risk="high", effect="fs")
            lc_tool = guard_tool("write_file", bind_context=True)
            
            # Should work in same context
            result = lc_tool.invoke({"path": "test1.txt", "content": "hello"})
            assert "Wrote" in result
        
        # Try to use in different context - should fail
        with run(policy="fs_safe", sandbox="./test_sandbox2") as ctx2:
            guard(write_file, risk="high", effect="fs")
            
            with pytest.raises(FailCoreError) as exc_info:
                lc_tool.invoke({"path": "test2.txt", "content": "hello"})
            
            error = exc_info.value
            assert error.error_code == codes.PRECONDITION_FAILED
            assert error.details["reason"] == "context_mismatch"
            assert "bind_context=False" in error.message
    
    def test_flexible_mode_cross_context_reuse(self):
        """
        Test: bind_context=False should allow cross-context reuse
        """
        try:
            from failcore.adapters.langchain import guard_tool
        except ImportError:
            pytest.skip("langchain-core not installed")
        
        # Create tool facade outside any context
        lc_tool = guard_tool("write_file", bind_context=False)
        
        # Use in first context
        with run(policy="fs_safe", sandbox="./test_sandbox1") as ctx1:
            guard(write_file, risk="high", effect="fs")
            result1 = lc_tool.invoke({"path": "test1.txt", "content": "hello1"})
            assert "Wrote" in result1
        
        # Use in second context - should still work
        with run(policy="fs_safe", sandbox="./test_sandbox2") as ctx2:
            guard(write_file, risk="high", effect="fs")
            result2 = lc_tool.invoke({"path": "test2.txt", "content": "hello2"})
            assert "Wrote" in result2
    
    @pytest.mark.asyncio
    async def test_async_path_routing(self):
        """
        Test 4: async path
        Async agent calls should route to ctx.acall() correctly
        """
        try:
            from failcore.adapters.langchain import guard_tool
        except ImportError:
            pytest.skip("langchain-core not installed")
        
        with run(policy="fs_safe", sandbox="./test_sandbox_async") as ctx:
            guard(write_file, risk="high", effect="fs")
            lc_tool = guard_tool("write_file")
            
            # Call via async interface
            result = await lc_tool.ainvoke({"path": "test_async.txt", "content": "hello async"})
            assert "Wrote" in result
    
    @pytest.mark.asyncio
    async def test_concurrent_contexts_no_leak(self):
        """
        Test 5: concurrency
        Two run() contexts in parallel should have isolated tool registries
        """
        try:
            from failcore.adapters.langchain import guard_tool
        except ImportError:
            pytest.skip("langchain-core not installed")
        
        results = []
        errors = []
        
        async def worker1():
            """Worker 1: Only registers write_file"""
            try:
                with run(policy="fs_safe", sandbox="./test_concurrent1") as ctx:
                    guard(write_file, risk="high", effect="fs")
                    lc_tool = guard_tool("write_file")
                    
                    # Should succeed
                    result = await lc_tool.ainvoke({"path": "file1.txt", "content": "worker1"})
                    results.append(("worker1", "write_file", "success", result))
                    
                    # Try to call tool only in worker2 - should fail
                    lc_tool2 = guard_tool("async_write_file")
                    try:
                        await lc_tool2.ainvoke({"path": "file1.txt", "content": "x"})
                        results.append(("worker1", "async_write_file", "unexpected_success", None))
                    except FailCoreError as e:
                        # Expected: tool not registered in this context
                        assert e.error_code == codes.TOOL_NOT_FOUND
                        results.append(("worker1", "async_write_file", "expected_error", e.error_code))
            except Exception as e:
                errors.append(("worker1", e))
        
        async def worker2():
            """Worker 2: Only registers async_write_file"""
            try:
                with run(policy="fs_safe", sandbox="./test_concurrent2") as ctx:
                    guard(async_write_file, risk="high", effect="fs")
                    lc_tool = guard_tool("async_write_file")
                    
                    # Should succeed
                    result = await lc_tool.ainvoke({"path": "file2.txt", "content": "worker2"})
                    results.append(("worker2", "async_write_file", "success", result))
                    
                    # Try to call tool only in worker1 - should fail
                    lc_tool2 = guard_tool("write_file")
                    try:
                        await lc_tool2.ainvoke({"path": "file2.txt", "content": "x"})
                        results.append(("worker2", "write_file", "unexpected_success", None))
                    except FailCoreError as e:
                        # Expected: tool not registered in this context
                        assert e.error_code == codes.TOOL_NOT_FOUND
                        results.append(("worker2", "write_file", "expected_error", e.error_code))
            except Exception as e:
                errors.append(("worker2", e))
        
        # Run both workers concurrently
        await asyncio.gather(worker1(), worker2())
        
        # No unexpected errors
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        
        # Verify results
        assert len(results) == 4, f"Expected 4 results, got {len(results)}: {results}"
        
        # Each worker succeeded with their own tool
        assert any(r[0] == "worker1" and r[1] == "write_file" and r[2] == "success" for r in results)
        assert any(r[0] == "worker2" and r[1] == "async_write_file" and r[2] == "success" for r in results)
        
        # Each worker failed with the other's tool (proof of isolation)
        assert any(r[0] == "worker1" and r[1] == "async_write_file" and r[2] == "expected_error" for r in results)
        assert any(r[0] == "worker2" and r[1] == "write_file" and r[2] == "expected_error" for r in results)
        
        print("\n✅ Context isolation verified: concurrent run() contexts don't leak tools")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
