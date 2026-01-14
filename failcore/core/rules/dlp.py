"""
DLP Rules - Neutral pattern definitions

Shared by both gates (for blocking decisions) and enrichers (for evidence tagging).

This is the single source of truth (SSOT) for DLP pattern definitions.
All guards and enrichers should import from here.
"""

from __future__ import annotations

from typing import Dict, List, Pattern, Optional
from enum import Enum
from dataclasses import dataclass, field
import re


class PatternCategory(str, Enum):
    """Pattern categories for sensitive data"""
    API_KEY = "api_key"
    SECRET_TOKEN = "secret_token"
    CREDENTIAL = "credential"
    PRIVATE_KEY = "private_key"
    PII_EMAIL = "pii_email"
    PII_PHONE = "pii_phone"
    PII_SSN = "pii_ssn"
    PAYMENT_CARD = "payment_card"
    INTERNAL_PATH = "internal_path"


@dataclass
class SensitivePattern:
    """
    Sensitive data pattern definition
    
    Attributes:
        name: Pattern name
        category: Pattern category
        pattern: Compiled regex pattern
        severity: Severity level (1-10)
        description: Pattern description
        source: Pattern source (builtin/community/local)
        version: Pattern version
        signature: Optional signature/checksum for verification
        trust_level: Trust level (trusted/untrusted/unknown)
    """
    name: str
    category: PatternCategory
    pattern: Pattern[str]
    severity: int
    description: str = ""
    source: str = "builtin"  # builtin, community, local
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[str] = None  # SHA256 checksum or signature
    trust_level: str = "trusted"  # trusted, untrusted, unknown


class DLPPatternRegistry:
    """
    DLP pattern registry
    
    Manages sensitive data patterns for detection.
    Supports versioning and source tracking (builtin/community/local).
    """
    
    # Default patterns
    DEFAULT_PATTERNS: Dict[str, SensitivePattern] = {}
    
    @classmethod
    def _init_default_patterns(cls):
        """Initialize default patterns"""
        if cls.DEFAULT_PATTERNS:
            return
        
        cls.DEFAULT_PATTERNS = {
            "OPENAI_API_KEY": SensitivePattern(
                name="OPENAI_API_KEY",
                category=PatternCategory.API_KEY,
                pattern=re.compile(r"sk-[A-Za-z0-9]{48}"),
                severity=10,
                description="OpenAI API key",
                source="builtin",
                version="1.0.0",
            ),
            "AWS_ACCESS_KEY": SensitivePattern(
                name="AWS_ACCESS_KEY",
                category=PatternCategory.API_KEY,
                pattern=re.compile(r"AKIA[0-9A-Z]{16}"),
                severity=10,
                description="AWS access key",
                source="builtin",
                version="1.0.0",
            ),
            "GITHUB_TOKEN": SensitivePattern(
                name="GITHUB_TOKEN",
                category=PatternCategory.SECRET_TOKEN,
                pattern=re.compile(r"gh[ps]_[A-Za-z0-9]{36}"),
                severity=10,
                description="GitHub personal access token",
                source="builtin",
                version="1.0.0",
            ),
            "PRIVATE_KEY": SensitivePattern(
                name="PRIVATE_KEY",
                category=PatternCategory.PRIVATE_KEY,
                pattern=re.compile(r"-----BEGIN (?:RSA|DSA|EC)? ?PRIVATE KEY-----"),
                severity=10,
                description="Private key header",
                source="builtin",
                version="1.0.0",
            ),
            "EMAIL": SensitivePattern(
                name="EMAIL",
                category=PatternCategory.PII_EMAIL,
                pattern=re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
                severity=6,
                description="Email address",
                source="builtin",
                version="1.0.0",
            ),
            "PHONE_US": SensitivePattern(
                name="PHONE_US",
                category=PatternCategory.PII_PHONE,
                pattern=re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
                severity=7,
                description="US phone number",
                source="builtin",
                version="1.0.0",
            ),
            "SSN": SensitivePattern(
                name="SSN",
                category=PatternCategory.PII_SSN,
                pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
                severity=10,
                description="US Social Security Number",
                source="builtin",
                version="1.0.0",
            ),
            "CREDIT_CARD": SensitivePattern(
                name="CREDIT_CARD",
                category=PatternCategory.PAYMENT_CARD,
                pattern=re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
                severity=9,
                description="Credit card number",
                source="builtin",
                version="1.0.0",
            ),
        }
    
    def __init__(self):
        """Initialize pattern registry"""
        # Ensure default patterns are initialized (class method)
        self._init_default_patterns()
        self._custom_patterns: Dict[str, SensitivePattern] = {}
        
        # Verify patterns are loaded
        if not self.DEFAULT_PATTERNS:
            # If somehow not initialized, force initialization
            DLPPatternRegistry._init_default_patterns()
    
    def register_pattern(self, pattern: SensitivePattern) -> None:
        """
        Register custom pattern
        
        Args:
            pattern: Pattern to register
        """
        # Override source if not set
        if pattern.source == "builtin":
            pattern.source = "local"
        self._custom_patterns[pattern.name] = pattern
    
    def get_pattern(self, name: str) -> Optional[SensitivePattern]:
        """
        Get pattern by name
        
        Args:
            name: Pattern name
            
        Returns:
            Pattern or None
        """
        # Check custom patterns first
        if name in self._custom_patterns:
            return self._custom_patterns[name]
        
        # Check default patterns
        return self.DEFAULT_PATTERNS.get(name)
    
    def get_all_patterns(self) -> Dict[str, SensitivePattern]:
        """
        Get all patterns (default + custom)
        
        Returns:
            Dictionary of all patterns
        """
        result = dict(self.DEFAULT_PATTERNS)
        result.update(self._custom_patterns)
        return result
    
    def get_patterns_by_category(self, category: PatternCategory) -> List[SensitivePattern]:
        """
        Get patterns by category
        
        Args:
            category: Pattern category
            
        Returns:
            List of patterns in category
        """
        all_patterns = self.get_all_patterns()
        return [p for p in all_patterns.values() if p.category == category]
    
    def get_patterns_by_source(self, source: str) -> List[SensitivePattern]:
        """
        Get patterns by source (builtin/community/local)
        
        Args:
            source: Pattern source
            
        Returns:
            List of patterns from source
        """
        all_patterns = self.get_all_patterns()
        return [p for p in all_patterns.values() if p.source == source]
    
    def scan_text(self, text: str, min_severity: int = 1) -> List[tuple[str, SensitivePattern]]:
        """
        Scan text for sensitive patterns
        
        Args:
            text: Text to scan
            min_severity: Minimum severity to report
            
        Returns:
            List of (matched_text, pattern) tuples
        """
        matches = []
        all_patterns = self.get_all_patterns()
        
        for pattern in all_patterns.values():
            if pattern.severity < min_severity:
                continue
            
            for match in pattern.pattern.finditer(text):
                matches.append((match.group(0), pattern))
        
        return matches


__all__ = [
    "DLPPatternRegistry",
    "SensitivePattern",
    "PatternCategory",
]
