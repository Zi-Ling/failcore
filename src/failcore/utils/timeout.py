# failcore/utils/timeout.py
"""
Timeout helpers for common I/O operations

Design Goal
Prioritize library-native timeout mechanisms (e.g., httpx.Timeout, subprocess timeout)
Use the outer-layer timeout of FailCore as the final safety fallback
Normalize library-level timeout exceptions into the STEP_TIMEOUT error code
"""

import subprocess
import sys
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


class TimeoutHelper:
    """
    Helper for normalizing timeout errors from different libraries
    
    Usage:
        try:
            result = safe_subprocess_run(...)
        except TimeoutError as e:
            # Already normalized to TimeoutError
            raise
    """
    
    @staticmethod
    def normalize_subprocess_timeout(e: Exception) -> TimeoutError:
        """
        Normalize subprocess.TimeoutExpired to TimeoutError
        
        Args:
            e: Original exception
            
        Returns:
            Normalized TimeoutError
        """
        if isinstance(e, subprocess.TimeoutExpired):
            return TimeoutError(
                f"subprocess timed out after {e.timeout}s: {e.cmd}"
            )
        return TimeoutError(str(e))
    
    @staticmethod
    def normalize_httpx_timeout(e: Exception) -> TimeoutError:
        """
        Normalize httpx timeout exceptions to TimeoutError
        
        Args:
            e: Original exception
            
        Returns:
            Normalized TimeoutError
        """
        # httpx may have different timeout exception types
        error_name = type(e).__name__
        if 'timeout' in error_name.lower():
            return TimeoutError(f"HTTP request timed out: {e}")
        return TimeoutError(str(e))


def safe_subprocess_run(
    cmd: Union[str, List[str]],
    timeout: Optional[float] = None,
    **kwargs
) -> subprocess.CompletedProcess:
    """
    Safe subprocess.run with timeout normalization
    
    步骤5：优先使用 subprocess 的原生 timeout
    
    Args:
        cmd: Command to run
        timeout: Timeout in seconds (uses subprocess's native timeout)
        **kwargs: Additional arguments for subprocess.run
        
    Returns:
        CompletedProcess result
        
    Raises:
        TimeoutError: Normalized timeout error (from subprocess.TimeoutExpired)
        
    Example:
        >>> result = safe_subprocess_run("sleep 10", timeout=5.0)
        TimeoutError: subprocess timed out after 5.0s: sleep 10
    """
    try:
        # 使用 subprocess 原生 timeout（库层优先）
        return subprocess.run(cmd, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired as e:
        # 归一化为 TimeoutError
        raise TimeoutHelper.normalize_subprocess_timeout(e)


def safe_httpx_get(
    url: str,
    timeout: Optional[float] = None,
    **kwargs
) -> Any:
    """
    Safe httpx.get with timeout normalization
    
    步骤5：优先使用 httpx 的原生 timeout
    
    Args:
        url: URL to request
        timeout: Timeout in seconds (uses httpx.Timeout)
        **kwargs: Additional arguments for httpx.get
        
    Returns:
        Response object
        
    Raises:
        TimeoutError: Normalized timeout error (from httpx timeout exceptions)
        ImportError: If httpx not available
        
    Example:
        >>> response = safe_httpx_get("https://api.example.com", timeout=10.0)
    """
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx is required for safe_httpx_get")
    
    try:
        # 构造 httpx.Timeout（库层优先）
        if timeout is not None:
            # 使用所有超时类型（connect、read、write、pool）
            timeout_config = httpx.Timeout(
                timeout,  # Total timeout
                connect=min(timeout / 2, 10.0),  # Connect timeout (max 10s)
                read=timeout,  # Read timeout
                write=timeout,  # Write timeout
                pool=timeout,  # Pool timeout
            )
            kwargs['timeout'] = timeout_config
        
        return httpx.get(url, **kwargs)
    
    except Exception as e:
        # 检查是否是超时异常
        if 'timeout' in type(e).__name__.lower() or 'timeout' in str(e).lower():
            raise TimeoutHelper.normalize_httpx_timeout(e)
        # 其他异常直接抛出
        raise


def safe_httpx_post(
    url: str,
    timeout: Optional[float] = None,
    **kwargs
) -> Any:
    """
    Safe httpx.post with timeout normalization
    
    Args:
        url: URL to request
        timeout: Timeout in seconds
        **kwargs: Additional arguments for httpx.post
        
    Returns:
        Response object
        
    Raises:
        TimeoutError: Normalized timeout error
        ImportError: If httpx not available
    """
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx is required for safe_httpx_post")
    
    try:
        if timeout is not None:
            timeout_config = httpx.Timeout(
                timeout,
                connect=min(timeout / 2, 10.0),
                read=timeout,
                write=timeout,
                pool=timeout,
            )
            kwargs['timeout'] = timeout_config
        
        return httpx.post(url, **kwargs)
    
    except Exception as e:
        if 'timeout' in type(e).__name__.lower() or 'timeout' in str(e).lower():
            raise TimeoutHelper.normalize_httpx_timeout(e)
        raise


# Convenience exports
__all__ = [
    "TimeoutHelper",
    "safe_subprocess_run",
    "safe_httpx_get",
    "safe_httpx_post",
]
