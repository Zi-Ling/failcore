# failcore/core/validate/builtin/pre/network.py
"""
Network security validators for SSRF prevention.

This module focuses on preventing:
1) Unsafe protocols (scheme allowlist)
2) Access to internal networks (loopback/private/link-local/reserved IPs)
3) Domain allowlist enforcement (optional)
4) Port allowlist enforcement (optional)

IMPORTANT LIMITATION:
- This implementation does NOT resolve DNS for hostnames.
  It blocks literal IP hostnames and localhost variants, but cannot fully prevent
  DNS rebinding attacks. If you need stronger protection, add optional DNS
  resolution with caching and strict timeouts at the application layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse
import ipaddress

from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, DecisionOutcome, RiskLevel


_DEFAULT_URL_PARAM_NAMES: Tuple[str, ...] = ("url", "uri", "endpoint", "host")


def _find_first_param(params: Dict[str, Any], names: Sequence[str]) -> Tuple[Optional[str], Any]:
    """Find first parameter that exists in params"""
    for name in names:
        if name in params:
            return name, params[name]
    return None, None


def _match_domain_allowlist(hostname: str, allowlist: Sequence[str]) -> bool:
    """
    Match hostname against allowlist.
    
    Supports:
    - Exact domain match: "api.github.com"
    - Wildcard suffix: "*.openai.com"
    - IP addresses with optional port: "127.0.0.1", "127.0.0.1:8080"
    - CIDR notation: "127.0.0.0/8"
    """
    host = hostname.strip(".").lower()
    
    for allowed in allowlist:
        a = allowed.strip().strip(".").lower()
        if not a:
            continue
        
        # Check if allowed pattern is CIDR notation
        if "/" in a:
            try:
                network = ipaddress.ip_network(a, strict=False)
                # Try to parse hostname as IP
                try:
                    ip = ipaddress.ip_address(host.split(":")[0])  # Strip port if present
                    if ip in network:
                        return True
                except ValueError:
                    # Not an IP, continue
                    pass
            except ValueError:
                # Not a valid CIDR, treat as literal
                pass
        
        # Check if allowed pattern is IP:port
        if ":" in a and not a.startswith("["):  # Not IPv6
            allowed_host_port = a.split(":", 1)
            if len(allowed_host_port) == 2:
                allowed_host, allowed_port = allowed_host_port
                # Match host:port exactly
                if host == a:
                    return True
                # Also match just the host part (port-agnostic)
                if host == allowed_host:
                    return True
                continue
        
        # Wildcard suffix match
        if a.startswith("*."):
            suffix = a[2:]
            if host == suffix or host.endswith("." + suffix):
                return True
        # Exact match
        elif host == a:
            return True
    
    return False


def _block_internal_host(hostname: str) -> Optional[Decision]:
    """
    Check if hostname should be blocked (internal network).
    
    Returns Decision if blocked, None if allowed.
    """
    host = hostname.lower()

    # Common localhost variants
    if host in ("localhost", "localhost.localdomain"):
        return Decision.block(
            code="FC_NET_SSRF_LOCALHOST",
            validator_id="network_ssrf",
            message=f"Access to localhost is blocked: {hostname}",
            evidence={"hostname": hostname, "reason": "localhost"},
        )

    # Literal IP check
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return None

    if ip.is_loopback:
        return Decision.block(
            code="FC_NET_SSRF_LOOPBACK",
            validator_id="network_ssrf",
            message=f"Access to loopback address is blocked: {hostname}",
            evidence={"ip": str(ip), "reason": "loopback"},
        )
    if ip.is_private:
        return Decision.block(
            code="FC_NET_SSRF_PRIVATE",
            validator_id="network_ssrf",
            message=f"Access to private IP is blocked: {hostname}",
            evidence={"ip": str(ip), "reason": "private"},
        )
    if ip.is_link_local:
        return Decision.block(
            code="FC_NET_SSRF_LINK_LOCAL",
            validator_id="network_ssrf",
            message=f"Access to link-local IP is blocked: {hostname}",
            evidence={"ip": str(ip), "reason": "link_local"},
        )
    if ip.is_reserved:
        return Decision.block(
            code="FC_NET_SSRF_RESERVED",
            validator_id="network_ssrf",
            message=f"Access to reserved IP is blocked: {hostname}",
            evidence={"ip": str(ip), "reason": "reserved"},
        )

    # ip.is_multicast / ip.is_unspecified are also suspicious in SSRF contexts
    if getattr(ip, "is_multicast", False):
        return Decision.block(
            code="FC_NET_SSRF_MULTICAST",
            validator_id="network_ssrf",
            message=f"Access to multicast IP is blocked: {hostname}",
            evidence={"ip": str(ip), "reason": "multicast"},
        )
    if getattr(ip, "is_unspecified", False):
        return Decision.block(
            code="FC_NET_SSRF_UNSPECIFIED",
            validator_id="network_ssrf",
            message=f"Access to unspecified IP is blocked: {hostname}",
            evidence={"ip": str(ip), "reason": "unspecified"},
        )

    return None


class NetworkSSRFValidator(BaseValidator):
    """
    Composite SSRF protection validator.
    
    This combines:
    - Scheme allowlist
    - Optional internal host/IP blocking
    - Optional domain allowlist
    - Port allowlist
    """
    
    @property
    def id(self) -> str:
        return "network_ssrf"
    
    @property
    def domain(self) -> str:
        return "network"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """JSON schema for validator configuration"""
        return {
            "type": "object",
            "properties": {
                "url_params": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "URL parameter names (url, uri, endpoint, host)",
                },
                "allowlist": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Domain allowlist (exact or *.suffix)",
                },
                "block_internal": {
                    "type": "boolean",
                    "description": "Whether to block internal networks (default: true)",
                },
                "allowed_schemes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Allowed URL schemes (default: http, https)",
                },
                "allowed_ports": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Allowed ports (default: 80, 443)",
                },
                "forbid_userinfo": {
                    "type": "boolean",
                    "description": "Block URLs containing credentials (default: true)",
                },
            },
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        return {
            "url_params": ["url", "uri", "endpoint"],
            "allowlist": None,
            "block_internal": True,
            "allowed_schemes": ["http", "https"],
            "allowed_ports": [80, 443],
            "forbid_userinfo": True,
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate SSRF protection validation
        
        Args:
            context: Validation context (tool, params, etc.)
            config: Validator configuration
            
        Returns:
            List of Decision objects (empty if validation passes)
        """
        decisions: List[Decision] = []
        
        # Get configuration
        cfg = self._get_config(config)
        url_params = cfg.get("url_params", ["url", "uri", "endpoint"])
        allowlist = cfg.get("allowlist")
        block_internal = cfg.get("block_internal", True)
        allowed_schemes = set(cfg.get("allowed_schemes", ["http", "https"]))
        allowed_ports = set(cfg.get("allowed_ports", [80, 443]))
        forbid_userinfo = cfg.get("forbid_userinfo", True)
        
        # Find first existing URL parameter
        found_param, url = _find_first_param(context.params, url_params)
        
        if found_param is None:
            # No URL parameter found, skip check
            return []
        
        if not isinstance(url, str):
            return [
                Decision.block(
                    code="FC_NET_SSRF_PARAM_TYPE",
                    validator_id=self.id,
                    message=f"URL parameter '{found_param}' must be a string",
                    evidence={
                        "param": found_param,
                        "got": type(url).__name__,
                    },
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            return [
                Decision.block(
                    code="FC_NET_SSRF_INVALID_URL",
                    validator_id=self.id,
                    message=f"Invalid URL: {e}",
                    evidence={"url": url, "error": str(e)},
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        scheme = (parsed.scheme or "").lower()
        if not scheme:
            return [
                Decision.block(
                    code="FC_NET_SSRF_NO_SCHEME",
                    validator_id=self.id,
                    message=f"URL '{url}' has no scheme",
                    evidence={"url": url, "allowed_schemes": sorted(allowed_schemes)},
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        if scheme not in allowed_schemes:
            return [
                Decision.block(
                    code="FC_NET_SSRF_UNSAFE_PROTOCOL",
                    validator_id=self.id,
                    message=f"Protocol '{scheme}' is not allowed. Allowed: {', '.join(sorted(allowed_schemes))}",
                    evidence={
                        "url": url,
                        "scheme": scheme,
                        "allowed_schemes": sorted(allowed_schemes),
                    },
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        hostname = parsed.hostname
        if not hostname:
            return [
                Decision.block(
                    code="FC_NET_SSRF_NO_HOSTNAME",
                    validator_id=self.id,
                    message=f"URL '{url}' has no hostname",
                    evidence={"url": url},
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        if forbid_userinfo and (parsed.username or parsed.password):
            return [
                Decision.block(
                    code="FC_NET_SSRF_USERINFO",
                    validator_id=self.id,
                    message="URLs with embedded credentials are not allowed",
                    evidence={"url": url, "reason": "userinfo"},
                    tool=context.tool,
                    step_id=context.step_id,
                )
            ]
        
        # Check domain allowlist FIRST - allowlist overrides internal IP blocking
        domain_allowlist = list(allowlist) if allowlist else []
        if domain_allowlist:
            if _match_domain_allowlist(hostname, domain_allowlist):
                # Explicitly allowed - skip internal IP check
                pass
            else:
                # Not in allowlist - deny
                return [
                    Decision.block(
                        code="FC_NET_SSRF_DOMAIN_NOT_ALLOWED",
                        validator_id=self.id,
                        message=f"Domain '{hostname}' is not allowed",
                        evidence={
                            "url": url,
                            "domain": hostname,
                            "allowed": domain_allowlist,
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
        elif block_internal:
            # No allowlist configured - apply internal IP blocking
            blocked = _block_internal_host(hostname)
            if blocked is not None:
                # Update evidence with URL and tool context
                blocked.evidence["url"] = url
                blocked.tool = context.tool
                blocked.step_id = context.step_id
                return [blocked]
        
        # Determine port
        port = parsed.port
        if port is None:
            if scheme == "http":
                port = 80
            elif scheme == "https":
                port = 443
        
        # Port check: skip if domain allowlist is configured and matched
        # (allowlist can include port-specific entries like "127.0.0.1:8080")
        if not domain_allowlist:
            if port is not None and port not in allowed_ports:
                return [
                    Decision.block(
                        code="FC_NET_SSRF_PORT_NOT_ALLOWED",
                        validator_id=self.id,
                        message=f"Port {port} is not allowed. Allowed: {sorted(allowed_ports)}",
                        evidence={
                            "url": url,
                            "port": port,
                            "allowed": sorted(allowed_ports),
                        },
                        tool=context.tool,
                        step_id=context.step_id,
                    )
                ]
        
        # All checks passed
        return []
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default


__all__ = [
    "NetworkSSRFValidator",
]
