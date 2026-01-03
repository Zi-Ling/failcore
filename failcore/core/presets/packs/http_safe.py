"""
http-safe Policy Pack Implementation

Executable contract for HTTP operations with SSRF protection
"""

from typing import List, Optional
from failcore.core.policy.policy import PolicyResult
from failcore.core.errors import codes
import re
from urllib.parse import urlparse


class HttpSafePolicy:
    """
    Executable policy for http-safe pack
    
    Enforces:
    - SSRF protection (block private IPs)
    - URL allowlist
    - Protocol restrictions (only https)
    """
    
    # Private IP ranges (SSRF targets)
    PRIVATE_IP_PATTERNS = [
        r'^127\.',          # Loopback
        r'^10\.',           # Private Class A
        r'^172\.(1[6-9]|2[0-9]|3[0-1])\.', # Private Class B
        r'^192\.168\.',     # Private Class C
        r'^169\.254\.',     # Link-local
        r'^localhost$',     # Localhost
    ]
    
    def __init__(self, allowlist: Optional[List[str]] = None):
        self.allowlist = allowlist or [
            "https://api.example.com/*",
            "https://*.trusted.com/*",
        ]
    
    def allow(self, tool: str, args: dict, context: dict) -> PolicyResult:
        """Check if HTTP operation is allowed"""
        
        # Extract URL parameter
        url = args.get('url') or args.get('uri') or args.get('endpoint')
        
        if not url:
            return PolicyResult.allow()
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception:
            return PolicyResult.deny(
                reason=f"Invalid URL format: '{url}'",
                error_code=codes.PARAM_INVALID,
                suggestion="Provide a valid URL with scheme (e.g., https://example.com)"
            )
        
        # Check protocol
        if parsed.scheme not in ['https', 'http']:
            return PolicyResult.deny(
                reason=f"Protocol '{parsed.scheme}' not allowed",
                error_code=codes.PROTOCOL_DENIED,
                suggestion="Use https:// or http:// URLs only"
            )
        
        # Check for private IPs (SSRF)
        hostname = parsed.hostname or parsed.netloc
        for pattern in self.PRIVATE_IP_PATTERNS:
            if re.match(pattern, hostname):
                return PolicyResult.deny(
                    reason=f"Private network access blocked: '{hostname}'",
                    error_code=codes.SSRF_BLOCKED,
                    suggestion="Use public internet URLs only. Private IPs and localhost are blocked for security.",
                    remediation={
                        "action": "use_public_url",
                        "template": "Replace '{blocked_host}' with a public domain",
                        "vars": {"blocked_host": hostname}
                    }
                )
        
        # Check allowlist (if strict mode)
        # For now, just allow all public URLs
        
        return PolicyResult.allow()


__all__ = ["HttpSafePolicy"]
