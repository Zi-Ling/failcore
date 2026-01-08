"""
P1-2: Policy Pack Registry

Optimized: Uses existing presets system instead of separate packs directory

A "pack" is a versioned bundle of:
- Validation rules (preconditions/postconditions)
- Policy constraints (sandbox/allowlist)
- Risk metadata
- Error code mappings
- LLM-friendly suggestions

Users "mount" their tool implementations onto these security contracts.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from failcore.core.errors import codes


@dataclass
class PolicyPack:
    """
    Security contract for a category of tools
    
    Does NOT provide tool implementation, only the security/policy contract
    """
    name: str
    version: str
    description: str
    
    # Tool categories this pack applies to
    tool_categories: Set[str]
    
    # Default policy settings
    default_sandbox: Optional[str] = None
    network_allowlist: Optional[List[str]] = None
    max_file_size_mb: int = 50
    
    # Expected error codes
    error_codes: Set[str] = None
    
    # Audit fields to capture
    audit_fields: List[str] = None
    
    # Examples
    examples: Dict[str, str] = None
    
    def __post_init__(self):
        if self.error_codes is None:
            self.error_codes = set()
        if self.audit_fields is None:
            self.audit_fields = []
        if self.examples is None:
            self.examples = {}


class PackRegistry:
    """Registry of policy packs"""
    
    def __init__(self):
        self._packs: Dict[str, PolicyPack] = {}
        self._register_builtin_packs()
    
    def _register_builtin_packs(self):
        """Register built-in packs"""
        
        # Pack 1: filesystem-safe
        self.register(PolicyPack(
            name="filesystem-safe",
            version="1.0.0",
            description="Safe filesystem operations with sandbox enforcement",
            tool_categories={"fs", "file"},
            default_sandbox="./workspace",
            max_file_size_mb=50,
            error_codes={
                codes.PATH_TRAVERSAL,
                codes.SANDBOX_VIOLATION,
                codes.FILE_NOT_FOUND,
                codes.PERMISSION_DENIED,
                codes.RESOURCE_LIMIT_FILE,
            },
            audit_fields=["path", "size_bytes", "operation"],
            examples={
                "safe_write": "guard(write_file, risk='high', effect='fs')",
                "safe_read": "guard(read_file, risk='low', effect='fs')",
            }
        ))
        
        # Pack 2: http-safe (SSRF protection)
        self.register(PolicyPack(
            name="http-safe",
            version="1.0.0",
            description="HTTP operations with SSRF protection",
            tool_categories={"http", "network"},
            network_allowlist=[
                "https://api.example.com/*",
                "https://*.trusted.com/*",
            ],
            error_codes={
                codes.SSRF_BLOCKED,
                codes.PRIVATE_NETWORK_BLOCKED,
                codes.REMOTE_TIMEOUT,
                codes.REMOTE_UNREACHABLE,
            },
            audit_fields=["url", "method", "status_code"],
            examples={
                "safe_fetch": "guard(fetch_url, risk='medium', effect='network')",
            }
        ))
        
        # Pack 3: mcp-remote (Remote tool contract)
        self.register(PolicyPack(
            name="mcp-remote",
            version="1.0.0",
            description="MCP remote tool error contract with retry",
            tool_categories={"mcp", "remote"},
            error_codes={
                codes.REMOTE_TIMEOUT,
                codes.REMOTE_UNREACHABLE,
                codes.REMOTE_PROTOCOL_MISMATCH,
                codes.REMOTE_TOOL_NOT_FOUND,
                codes.REMOTE_INVALID_PARAMS,
                codes.REMOTE_SERVER_ERROR,
                codes.RETRY_EXHAUSTED,
            },
            audit_fields=["server_id", "tool_name", "attempt", "latency_ms"],
            examples={
                "mcp_tool": "Use ToolRuntime with McpTransport + RetryPolicy",
            }
        ))
    
    def register(self, pack: PolicyPack):
        """Register a pack"""
        self._packs[pack.name] = pack
    
    def get(self, name: str) -> Optional[PolicyPack]:
        """Get pack by name"""
        return self._packs.get(name)
    
    def list_packs(self) -> List[PolicyPack]:
        """List all registered packs"""
        return list(self._packs.values())
    
    def get_for_category(self, category: str) -> List[PolicyPack]:
        """Get packs for a tool category"""
        return [
            pack for pack in self._packs.values()
            if category in pack.tool_categories
        ]


# Global registry
_registry = PackRegistry()


def get_pack(name: str) -> Optional[PolicyPack]:
    """Get a policy pack by name"""
    return _registry.get(name)


def list_packs() -> List[PolicyPack]:
    """List all available packs"""
    return _registry.list_packs()


__all__ = [
    "PolicyPack",
    "PackRegistry",
    "get_pack",
    "list_packs",
]
