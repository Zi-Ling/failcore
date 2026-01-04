# failcore/web/services/anomaly/rules.py
"""
Anomaly Rules - rule definitions for parameter anomaly detection

Defines rules for detecting suspicious patterns in tool arguments.
"""

from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import re
from urllib.parse import urlparse


class RuleSeverity(str, Enum):
    """Rule severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleRiskType(str, Enum):
    """Risk type categories"""
    PATH_TRAVERSAL = "path_traversal"
    DANGEROUS_COMMAND = "dangerous_command"
    SSRF = "ssrf"
    MAGNITUDE = "magnitude"
    OVERLY_LONG = "overly_long"
    OTHER = "other"


class AnomalyRule:
    """
    Anomaly detection rule
    
    A rule consists of:
    - A predicate function that checks if the rule applies
    - Metadata (severity, risk_type, explanation)
    """
    
    def __init__(
        self,
        name: str,
        predicate: Callable[[str, Dict[str, Any], Optional[Dict[str, Any]]], bool],
        field_path: str,
        severity: RuleSeverity,
        risk_type: RuleRiskType,
        reason: str,
        explanation: str,
    ):
        """
        Initialize anomaly rule
        
        Args:
            name: Rule name
            predicate: Function (tool, args, metadata) -> bool
            field_path: Field path in args (e.g., "path", "command", "url")
            severity: Rule severity
            risk_type: Risk type category
            reason: Technical reason
            explanation: Human-readable explanation
        """
        self.name = name
        self.predicate = predicate
        self.field_path = field_path
        self.severity = severity
        self.risk_type = risk_type
        self.reason = reason
        self.explanation = explanation
    
    def check(self, tool: str, args: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if rule applies"""
        try:
            return self.predicate(tool, args, metadata)
        except Exception:
            return False


# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",  # ../
    r"\.\.\\",  # ..\
    r"\.\.",  # ..
    r"\.\./\.\./",  # ../../
    r"\.\.\\\.\.\\",  # ..\..\
    r"^/\.\./",  # /../
    r"^\\\.\.\\",  # \..\
]


def check_path_traversal(tool: str, args: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Check for path traversal patterns in path-like arguments"""
    path_fields = ["path", "file", "filepath", "file_path", "src", "dst", "source", "destination", "dir", "directory"]
    
    for field in path_fields:
        value = args.get(field)
        if isinstance(value, str):
            for pattern in PATH_TRAVERSAL_PATTERNS:
                if re.search(pattern, value):
                    return True
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    for pattern in PATH_TRAVERSAL_PATTERNS:
                        if re.search(pattern, item):
                            return True
    
    return False


# Dangerous command flags
DANGEROUS_FLAGS = {
    "rm": ["-rf", "-r", "-f", "--force"],
    "rmdir": ["--ignore-fail-on-non-empty"],
    "del": ["/f", "/s", "/q"],
    "format": ["/y", "/q"],
    "shutdown": ["/s", "/f", "/t", "0"],
    "chmod": ["777", "000"],
    "chown": ["root"],
}


def check_dangerous_command(tool: str, args: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Check for dangerous command flags"""
    command = args.get("command") or args.get("cmd") or args.get("command_line")
    if not isinstance(command, str):
        return False
    
    # Check if command starts with dangerous tool
    for dangerous_tool, flags in DANGEROUS_FLAGS.items():
        if command.startswith(dangerous_tool) or f" {dangerous_tool} " in command:
            for flag in flags:
                if flag in command:
                    return True
    
    return False


# Private network IP ranges
PRIVATE_IP_RANGES = [
    (10, 0, 0, 0, 8),  # 10.0.0.0/8
    (172, 16, 0, 0, 12),  # 172.16.0.0/12
    (192, 168, 0, 0, 16),  # 192.168.0.0/16
    (127, 0, 0, 0, 8),  # 127.0.0.0/8 (localhost)
]


def is_private_ip(ip: str) -> bool:
    """Check if IP address is in private range"""
    try:
        parts = [int(x) for x in ip.split(".")]
        if len(parts) != 4:
            return False
        
        for base_parts, mask in PRIVATE_IP_RANGES:
            if mask == 8:
                if parts[0] == base_parts[0]:
                    return True
            elif mask == 12:
                if parts[0] == base_parts[0] and parts[1] >= base_parts[1] and parts[1] <= 31:
                    return True
            elif mask == 16:
                if parts[0] == base_parts[0] and parts[1] == base_parts[1]:
                    return True
    except Exception:
        pass
    
    return False


def check_ssrf(tool: str, args: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Check for SSRF (Server-Side Request Forgery) risks"""
    url_fields = ["url", "endpoint", "uri", "address", "host"]
    
    for field in url_fields:
        value = args.get(field)
        if isinstance(value, str):
            try:
                parsed = urlparse(value)
                host = parsed.hostname
                if host:
                    # Check for private IP
                    if is_private_ip(host):
                        return True
                    # Check for localhost variants
                    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                        return True
                    # Check for private domain
                    if host.endswith(".local") or host.endswith(".internal"):
                        return True
            except Exception:
                pass
    
    return False


def check_magnitude(tool: str, args: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Check for magnitude anomalies (unusually large numbers)"""
    numeric_fields = ["count", "limit", "size", "timeout", "delay", "retries"]
    
    for field in numeric_fields:
        value = args.get(field)
        if isinstance(value, (int, float)):
            # Flag if count/limit > 1000
            if field in ("count", "limit") and value > 1000:
                return True
            # Flag if timeout/delay > 3600 (1 hour)
            if field in ("timeout", "delay") and value > 3600:
                return True
            # Flag if retries > 10
            if field == "retries" and value > 10:
                return True
    
    return False


def check_overly_long(tool: str, args: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Check for overly long string values"""
    MAX_LENGTH = 10000  # 10KB
    
    for key, value in args.items():
        if isinstance(value, str) and len(value) > MAX_LENGTH:
            return True
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str) and len(item) > MAX_LENGTH:
                    return True
    
    return False


# Rule registry
DEFAULT_RULES = [
    AnomalyRule(
        name="path_traversal",
        predicate=check_path_traversal,
        field_path="path",
        severity=RuleSeverity.HIGH,
        risk_type=RuleRiskType.PATH_TRAVERSAL,
        reason="Path traversal pattern detected (../ or ..\\)",
        explanation="This path contains traversal sequences that could escape the intended directory.",
    ),
    AnomalyRule(
        name="dangerous_command",
        predicate=check_dangerous_command,
        field_path="command",
        severity=RuleSeverity.CRITICAL,
        risk_type=RuleRiskType.DANGEROUS_COMMAND,
        reason="Dangerous command flag detected",
        explanation="This command includes flags that can cause data loss or system damage.",
    ),
    AnomalyRule(
        name="ssrf_private_ip",
        predicate=check_ssrf,
        field_path="url",
        severity=RuleSeverity.HIGH,
        risk_type=RuleRiskType.SSRF,
        reason="Private network IP or localhost in URL",
        explanation="This URL points to a private network address, which could be used for SSRF attacks.",
    ),
    AnomalyRule(
        name="magnitude_anomaly",
        predicate=check_magnitude,
        field_path="count",
        severity=RuleSeverity.MEDIUM,
        risk_type=RuleRiskType.MAGNITUDE,
        reason="Unusually large numeric value",
        explanation="This value is unusually large and may indicate an error or malicious input.",
    ),
    AnomalyRule(
        name="overly_long_string",
        predicate=check_overly_long,
        field_path="*",
        severity=RuleSeverity.LOW,
        risk_type=RuleRiskType.OVERLY_LONG,
        reason="String value exceeds maximum length",
        explanation="This string is extremely long and may cause performance issues or buffer overflows.",
    ),
]


__all__ = [
    "AnomalyRule",
    "RuleSeverity",
    "RuleRiskType",
    "DEFAULT_RULES",
    "check_path_traversal",
    "check_dangerous_command",
    "check_ssrf",
    "check_magnitude",
    "check_overly_long",
]
