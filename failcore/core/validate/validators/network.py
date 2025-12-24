# failcore/core/validate/validators/network.py
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

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse
import ipaddress

from ..validator import PreconditionValidator, ValidationResult


_DEFAULT_URL_PARAM_NAMES: Tuple[str, ...] = ("url", "uri", "endpoint", "host")


def _find_first_param(params: Dict[str, Any], names: Sequence[str]) -> Tuple[Optional[str], Any]:
    for name in names:
        if name in params:
            return name, params[name]
    return None, None


def _match_domain_allowlist(hostname: str, allowlist: Sequence[str]) -> bool:
    host = hostname.strip(".").lower()
    for allowed in allowlist:
        a = allowed.strip().strip(".").lower()
        if not a:
            continue
        if a.startswith("*."):
            suffix = a[2:]
            if host == suffix or host.endswith("." + suffix):
                return True
        else:
            if host == a:
                return True
    return False


def _block_internal_host(hostname: str) -> Optional[ValidationResult]:
    host = hostname.lower()

    # Common localhost variants
    if host in ("localhost", "localhost.localdomain"):
        return ValidationResult.failure(
            message=f"Access to localhost is blocked: {hostname}",
            code="SSRF_BLOCKED",
            details={"hostname": hostname, "reason": "localhost"},
        )

    # Literal IP check
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return None

    if ip.is_loopback:
        return ValidationResult.failure(
            message=f"Access to loopback address is blocked: {hostname}",
            code="SSRF_BLOCKED",
            details={"ip": str(ip), "reason": "loopback"},
        )
    if ip.is_private:
        return ValidationResult.failure(
            message=f"Access to private IP is blocked: {hostname}",
            code="SSRF_BLOCKED",
            details={"ip": str(ip), "reason": "private"},
        )
    if ip.is_link_local:
        return ValidationResult.failure(
            message=f"Access to link-local IP is blocked: {hostname}",
            code="SSRF_BLOCKED",
            details={"ip": str(ip), "reason": "link_local"},
        )
    if ip.is_reserved:
        return ValidationResult.failure(
            message=f"Access to reserved IP is blocked: {hostname}",
            code="SSRF_BLOCKED",
            details={"ip": str(ip), "reason": "reserved"},
        )

    # ip.is_multicast / ip.is_unspecified are also suspicious in SSRF contexts
    if getattr(ip, "is_multicast", False):
        return ValidationResult.failure(
            message=f"Access to multicast IP is blocked: {hostname}",
            code="SSRF_BLOCKED",
            details={"ip": str(ip), "reason": "multicast"},
        )
    if getattr(ip, "is_unspecified", False):
        return ValidationResult.failure(
            message=f"Access to unspecified IP is blocked: {hostname}",
            code="SSRF_BLOCKED",
            details={"ip": str(ip), "reason": "unspecified"},
        )

    return None


def url_safe_precondition(
    *param_names: str,
    allowed_schemes: Optional[Set[str]] = None,
    forbid_userinfo: bool = True,
) -> PreconditionValidator:
    """
    URL scheme allowlist validator.

    Args:
        *param_names: Parameter names that may contain the URL.
        allowed_schemes: Allowed schemes (default: {"http", "https"}).
        forbid_userinfo: If True, blocks URLs containing credentials (user:pass@host).

    Returns:
        PreconditionValidator
    """
    names = param_names or _DEFAULT_URL_PARAM_NAMES
    schemes = {s.lower() for s in (allowed_schemes or {"http", "https"})}

    def check(ctx: Dict[str, Any]) -> ValidationResult:
        params = ctx.get("params", {})
        found, url = _find_first_param(params, list(names))

        if found is None:
            return ValidationResult.success(message="No URL parameter found", code="URL_CHECK_SKIPPED")

        if not isinstance(url, str):
            return ValidationResult.failure(
                message=f"URL parameter '{found}' must be a string",
                code="PARAM_TYPE_MISMATCH",
                details={"param": found, "got": type(url).__name__},
            )

        try:
            parsed = urlparse(url)
        except Exception as e:
            return ValidationResult.failure(
                message=f"Invalid URL: {e}",
                code="PARAM_INVALID",
                details={"url": url, "error": str(e)},
            )

        scheme = (parsed.scheme or "").lower()
        if not scheme:
            return ValidationResult.failure(
                message=f"URL '{url}' has no scheme",
                code="UNSAFE_PROTOCOL",
                details={"url": url, "allowed_schemes": sorted(schemes)},
            )

        if scheme not in schemes:
            return ValidationResult.failure(
                message=f"Protocol '{scheme}' is not allowed. Allowed: {', '.join(sorted(schemes))}",
                code="UNSAFE_PROTOCOL",
                details={"url": url, "scheme": scheme, "allowed_schemes": sorted(schemes)},
            )

        if not parsed.hostname:
            return ValidationResult.failure(
                message=f"URL '{url}' has no hostname",
                code="PARAM_INVALID",
                details={"url": url},
            )

        if forbid_userinfo and (parsed.username or parsed.password):
            return ValidationResult.failure(
                message="URLs with embedded credentials are not allowed",
                code="UNSAFE_URL",
                details={"url": url, "reason": "userinfo"},
            )

        return ValidationResult.success(message=f"URL scheme is allowed: {scheme}", code="URL_SCHEME_OK")

    return PreconditionValidator(
        name=f"url_safe({'|'.join(names)})",
        condition=check,
        message="URL scheme validation",
        code="UNSAFE_PROTOCOL",
    )


def internal_ip_block_precondition(
    *param_names: str,
) -> PreconditionValidator:
    """
    Blocks internal network targets (SSRF mitigation).

    This blocks:
    - localhost variants
    - literal IP hostnames that are loopback/private/link-local/reserved/multicast/unspecified

    Args:
        *param_names: Parameter names that may contain the URL.

    Returns:
        PreconditionValidator
    """
    names = param_names or _DEFAULT_URL_PARAM_NAMES

    def check(ctx: Dict[str, Any]) -> ValidationResult:
        params = ctx.get("params", {})
        found, url = _find_first_param(params, list(names))

        if found is None:
            return ValidationResult.success(message="No URL parameter found", code="SSRF_CHECK_SKIPPED")

        if not isinstance(url, str):
            return ValidationResult.failure(
                message=f"URL parameter '{found}' must be a string",
                code="PARAM_TYPE_MISMATCH",
                details={"param": found, "got": type(url).__name__},
            )

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
        except Exception as e:
            return ValidationResult.failure(
                message=f"Invalid URL: {e}",
                code="PARAM_INVALID",
                details={"url": url, "error": str(e)},
            )

        if not hostname:
            return ValidationResult.failure(
                message=f"URL '{url}' has no hostname",
                code="PARAM_INVALID",
                details={"url": url},
            )

        blocked = _block_internal_host(hostname)
        if blocked is not None:
            blocked.details = dict(blocked.details or {})
            blocked.details["url"] = url
            return blocked

        return ValidationResult.success(message=f"Hostname is allowed: {hostname}", code="SSRF_HOST_OK")

    return PreconditionValidator(
        name=f"internal_ip_block({'|'.join(names)})",
        condition=check,
        message="Internal IP blocking",
        code="SSRF_BLOCKED",
    )


def domain_whitelist_precondition(
    *param_names: str,
    allowed_domains: Optional[Sequence[str]] = None,
) -> PreconditionValidator:
    """
    Domain allowlist validator.

    Supports:
    - Exact match: "api.github.com"
    - Wildcard suffix: "*.openai.com"

    If allowed_domains is empty/None, this validator will skip.

    Args:
        *param_names: Parameter names that may contain the URL.
        allowed_domains: Allowed domain patterns.

    Returns:
        PreconditionValidator
    """
    names = param_names or _DEFAULT_URL_PARAM_NAMES
    allowlist = list(allowed_domains or [])

    def check(ctx: Dict[str, Any]) -> ValidationResult:
        if not allowlist:
            return ValidationResult.success(message="No domain allowlist configured, skipping", code="DOMAIN_CHECK_SKIPPED")

        params = ctx.get("params", {})
        found, url = _find_first_param(params, list(names))

        if found is None:
            return ValidationResult.success(message="No URL parameter found", code="DOMAIN_CHECK_SKIPPED")

        if not isinstance(url, str):
            return ValidationResult.failure(
                message=f"URL parameter '{found}' must be a string",
                code="PARAM_TYPE_MISMATCH",
                details={"param": found, "got": type(url).__name__},
            )

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
        except Exception as e:
            return ValidationResult.failure(
                message=f"Invalid URL: {e}",
                code="PARAM_INVALID",
                details={"url": url, "error": str(e)},
            )

        if not hostname:
            return ValidationResult.failure(
                message=f"URL '{url}' has no hostname",
                code="PARAM_INVALID",
                details={"url": url},
            )

        if _match_domain_allowlist(hostname, allowlist):
            return ValidationResult.success(
                message=f"Domain '{hostname}' is allowed",
                code="DOMAIN_OK",
                details={"domain": hostname},
            )

        return ValidationResult.failure(
            message=f"Domain '{hostname}' is not allowed",
            code="DOMAIN_NOT_ALLOWED",
            details={"url": url, "domain": hostname, "allowed": allowlist},
        )

    return PreconditionValidator(
        name=f"domain_whitelist({'|'.join(names)})",
        condition=check,
        message="Domain allowlist validation",
        code="DOMAIN_NOT_ALLOWED",
    )


def port_range_precondition(
    *param_names: str,
    allowed_ports: Optional[Set[int]] = None,
) -> PreconditionValidator:
    """
    Port allowlist validator.

    If URL has no explicit port, inferred from scheme:
    - http -> 80
    - https -> 443

    Args:
        *param_names: Parameter names that may contain the URL.
        allowed_ports: Allowed ports (default: {80, 443}).

    Returns:
        PreconditionValidator
    """
    names = param_names or _DEFAULT_URL_PARAM_NAMES
    ports = set(allowed_ports or {80, 443})

    def check(ctx: Dict[str, Any]) -> ValidationResult:
        params = ctx.get("params", {})
        found, url = _find_first_param(params, list(names))

        if found is None:
            return ValidationResult.success(message="No URL parameter found", code="PORT_CHECK_SKIPPED")

        if not isinstance(url, str):
            return ValidationResult.failure(
                message=f"URL parameter '{found}' must be a string",
                code="PARAM_TYPE_MISMATCH",
                details={"param": found, "got": type(url).__name__},
            )

        try:
            parsed = urlparse(url)
        except Exception as e:
            return ValidationResult.failure(
                message=f"Invalid URL: {e}",
                code="PARAM_INVALID",
                details={"url": url, "error": str(e)},
            )

        scheme = (parsed.scheme or "").lower()
        port = parsed.port

        if port is None:
            if scheme == "http":
                port = 80
            elif scheme == "https":
                port = 443
            else:
                return ValidationResult.success(
                    message=f"Cannot infer port for scheme '{scheme}', skipping",
                    code="PORT_CHECK_SKIPPED",
                    details={"url": url, "scheme": scheme},
                )

        if port not in ports:
            return ValidationResult.failure(
                message=f"Port {port} is not allowed. Allowed: {sorted(ports)}",
                code="PORT_NOT_ALLOWED",
                details={"url": url, "port": port, "allowed": sorted(ports)},
            )

        return ValidationResult.success(message=f"Port is allowed: {port}", code="PORT_OK", details={"port": port})

    return PreconditionValidator(
        name=f"port_range({'|'.join(names)})",
        condition=check,
        message="Port allowlist validation",
        code="PORT_NOT_ALLOWED",
    )


def ssrf_precondition(
    *param_names: str,
    allowlist: Optional[Sequence[str]] = None,
    block_internal: bool = True,
    allowed_schemes: Optional[Set[str]] = None,
    allowed_ports: Optional[Set[int]] = None,
    forbid_userinfo: bool = True,
) -> PreconditionValidator:
    """
    Composite SSRF protection validator.

    This combines:
    - Scheme allowlist
    - Optional internal host/IP blocking
    - Optional domain allowlist
    - Port allowlist

    Args:
        *param_names: URL parameter names.
        allowlist: Optional domain allowlist (exact or "*.suffix").
        block_internal: Whether to block internal networks (default True).
        allowed_schemes: Allowed URL schemes (default {"http","https"}).
        allowed_ports: Allowed ports (default {80,443}).
        forbid_userinfo: Block URLs containing credentials.

    Returns:
        PreconditionValidator
    """
    names = param_names or _DEFAULT_URL_PARAM_NAMES
    schemes = {s.lower() for s in (allowed_schemes or {"http", "https"})}
    ports = set(allowed_ports or {80, 443})
    domain_allowlist = list(allowlist or [])

    def check(ctx: Dict[str, Any]) -> ValidationResult:
        params = ctx.get("params", {})
        found, url = _find_first_param(params, list(names))

        if found is None:
            return ValidationResult.success(message="No URL parameter found", code="SSRF_CHECK_SKIPPED")

        if not isinstance(url, str):
            return ValidationResult.failure(
                message=f"URL parameter '{found}' must be a string",
                code="PARAM_TYPE_MISMATCH",
                details={"param": found, "got": type(url).__name__},
            )

        try:
            parsed = urlparse(url)
        except Exception as e:
            return ValidationResult.failure(
                message=f"Invalid URL: {e}",
                code="PARAM_INVALID",
                details={"url": url, "error": str(e)},
            )

        scheme = (parsed.scheme or "").lower()
        if not scheme:
            return ValidationResult.failure(
                message=f"URL '{url}' has no scheme",
                code="UNSAFE_PROTOCOL",
                details={"url": url, "allowed_schemes": sorted(schemes)},
            )
        if scheme not in schemes:
            return ValidationResult.failure(
                message=f"Protocol '{scheme}' is not allowed. Allowed: {', '.join(sorted(schemes))}",
                code="UNSAFE_PROTOCOL",
                details={"url": url, "scheme": scheme, "allowed_schemes": sorted(schemes)},
            )

        hostname = parsed.hostname
        if not hostname:
            return ValidationResult.failure(
                message=f"URL '{url}' has no hostname",
                code="PARAM_INVALID",
                details={"url": url},
            )

        if forbid_userinfo and (parsed.username or parsed.password):
            return ValidationResult.failure(
                message="URLs with embedded credentials are not allowed",
                code="UNSAFE_URL",
                details={"url": url, "reason": "userinfo"},
            )

        if block_internal:
            blocked = _block_internal_host(hostname)
            if blocked is not None:
                blocked.details = dict(blocked.details or {})
                blocked.details["url"] = url
                return blocked

        if domain_allowlist:
            if not _match_domain_allowlist(hostname, domain_allowlist):
                return ValidationResult.failure(
                    message=f"Domain '{hostname}' is not allowed",
                    code="DOMAIN_NOT_ALLOWED",
                    details={"url": url, "domain": hostname, "allowed": domain_allowlist},
                )

        port = parsed.port
        if port is None:
            if scheme == "http":
                port = 80
            elif scheme == "https":
                port = 443

        if port is not None and port not in ports:
            return ValidationResult.failure(
                message=f"Port {port} is not allowed. Allowed: {sorted(ports)}",
                code="PORT_NOT_ALLOWED",
                details={"url": url, "port": port, "allowed": sorted(ports)},
            )

        return ValidationResult.success(
            message=f"SSRF checks passed for '{url}'",
            code="SSRF_CHECK_OK",
            details={"hostname": hostname, "scheme": scheme, "port": port},
        )

    return PreconditionValidator(
        name=f"ssrf_protection({'|'.join(names)})",
        condition=check,
        message="SSRF protection check",
        code="SSRF_BLOCKED",
    )


__all__ = [
    "url_safe_precondition",
    "domain_whitelist_precondition",
    "internal_ip_block_precondition",
    "port_range_precondition",
    "ssrf_precondition",
]
