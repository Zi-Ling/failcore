"""
DLP Pattern Registry

Defines sensitive data patterns for detection

NOTE: This module will be deprecated. New code should import from:
    from failcore.core.rules import DLPPatternRegistry, SensitivePattern, PatternCategory
"""

from __future__ import annotations

from typing import Dict, List, Pattern, Optional
from enum import Enum
from dataclasses import dataclass
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
    """
    name: str
    category: PatternCategory
    pattern: Pattern[str]
    severity: int
    description: str = ""


class DLPPatternRegistry:
    """
    DLP pattern registry
    
    Manages sensitive data patterns for detection
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
                description="OpenAI API key"
            ),
            "AWS_ACCESS_KEY": SensitivePattern(
                name="AWS_ACCESS_KEY",
                category=PatternCategory.API_KEY,
                pattern=re.compile(r"AKIA[0-9A-Z]{16}"),
                severity=10,
                description="AWS access key"
            ),
            "GITHUB_TOKEN": SensitivePattern(
                name="GITHUB_TOKEN",
                category=PatternCategory.SECRET_TOKEN,
                pattern=re.compile(r"gh[ps]_[A-Za-z0-9]{36}"),
                severity=10,
                description="GitHub personal access token"
            ),
            "PRIVATE_KEY": SensitivePattern(
                name="PRIVATE_KEY",
                category=PatternCategory.PRIVATE_KEY,
                pattern=re.compile(r"-----BEGIN (?:RSA|DSA|EC)? ?PRIVATE KEY-----"),
                severity=10,
                description="Private key header"
            ),
            "EMAIL": SensitivePattern(
                name="EMAIL",
                category=PatternCategory.PII_EMAIL,
                pattern=re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
                severity=6,
                description="Email address"
            ),
            "PHONE_US": SensitivePattern(
                name="PHONE_US",
                category=PatternCategory.PII_PHONE,
                pattern=re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
                severity=7,
                description="US phone number"
            ),
            "SSN": SensitivePattern(
                name="SSN",
                category=PatternCategory.PII_SSN,
                pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
                severity=10,
                description="US Social Security Number"
            ),
            "CREDIT_CARD": SensitivePattern(
                name="CREDIT_CARD",
                category=PatternCategory.PAYMENT_CARD,
                pattern=re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
                severity=9,
                description="Credit card number"
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
        self._custom_patterns[pattern.name] = pattern
    
    def get_pattern(self, name: str) -> Optional[SensitivePattern]:
        """
        Get pattern by name
        
        Args:
            name: Pattern name
        
        Returns:
            Pattern if found, None otherwise
        """
        return self._custom_patterns.get(name) or self.DEFAULT_PATTERNS.get(name)
    
    def get_all_patterns(self) -> Dict[str, SensitivePattern]:
        """
        Get all patterns (default + custom)
        
        Returns:
            All registered patterns
        """
        return {**self.DEFAULT_PATTERNS, **self._custom_patterns}
    
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
    
    def scan_text(self, text: str, min_severity: int = 1) -> List[tuple[str, SensitivePattern]]:
        """
        Scan text for sensitive patterns
        
        Args:
            text: Text to scan
            min_severity: Minimum severity level to report
        
        Returns:
            List of (matched_text, pattern) tuples
        """
        if not isinstance(text, str):
            return []
        
        matches = []
        all_patterns = self.get_all_patterns()
        
        for pattern in all_patterns.values():
            if pattern.severity < min_severity:
                continue
            
            for match in pattern.pattern.finditer(text):
                matches.append((match.group(), pattern))
        
        return matches


__all__ = [
    "PatternCategory",
    "SensitivePattern",
    "DLPPatternRegistry",
]
