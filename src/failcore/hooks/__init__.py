# failcore/hooks/__init__.py
"""
Hooks - Monkey-patch standard libraries to emit EgressEvent

All hooks generate EgressEvent and route through EgressEngine.
This ensures unified audit/policy for "AI touching reality".

Available hooks:
- httpx_patch: HTTP requests (httpx library)
- requests_patch: HTTP requests (requests library)
- subprocess_patch: Subprocess execution
- os_patch: File system operations
"""

from .httpx_patch import patch_httpx, unpatch_httpx
from .requests_patch import patch_requests, unpatch_requests
from .subprocess_patch import patch_subprocess, unpatch_subprocess
from .os_patch import patch_os, unpatch_os


def enable_all_hooks(egress_engine):
    """
    Enable all hooks with egress engine
    
    Args:
        egress_engine: EgressEngine instance for event routing
    """
    patch_httpx(egress_engine)
    patch_requests(egress_engine)
    patch_subprocess(egress_engine)
    patch_os(egress_engine)


def disable_all_hooks():
    """Disable all hooks"""
    unpatch_httpx()
    unpatch_requests()
    unpatch_subprocess()
    unpatch_os()


__all__ = [
    "patch_httpx",
    "unpatch_httpx",
    "patch_requests",
    "unpatch_requests",
    "patch_subprocess",
    "unpatch_subprocess",
    "patch_os",
    "unpatch_os",
    "enable_all_hooks",
    "disable_all_hooks",
]
