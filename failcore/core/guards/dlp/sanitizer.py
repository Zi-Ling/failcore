"""
DLP Structured Sanitizer

Structured redaction for sensitive data with:
- Evidence-only summaries (hash/last4/token-class)
- Structured path-based redaction (JSON key paths)
- Category-specific masking (email/cc/keys)
- Irreversible sanitization
- Usability-preserving options (keep domain, keep last4)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

from . import PatternCategory


class RedactionMode(str, Enum):
    """Redaction mode for sanitization"""
    FULL = "full"  # Full redaction (irreversible)
    PARTIAL = "partial"  # Partial redaction (preserve usability)
    SUMMARY = "summary"  # Summary only (for evidence)


class StructuredSanitizer:
    """
    Structured sanitizer for DLP data redaction
    
    Features:
    - Evidence summaries (hash/last4/token-class) - never contains full data
    - Structured path-based redaction (JSON key paths)
    - Category-specific masking
    - Irreversible sanitization
    - Usability-preserving options
    """
    
    def __init__(
        self,
        preserve_usability: bool = False,
        preserve_domain: bool = True,
        preserve_last4: bool = True,
    ):
        """
        Initialize structured sanitizer
        
        Args:
            preserve_usability: Preserve usability (keep domain, last4, etc.)
            preserve_domain: Preserve email domain (e.g., user@***.com)
            preserve_last4: Preserve last 4 digits (e.g., ****1234)
        """
        self.preserve_usability = preserve_usability
        self.preserve_domain = preserve_domain
        self.preserve_last4 = preserve_last4
    
    def create_evidence_summary(
        self,
        value: str,
        category: PatternCategory,
        pattern_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create evidence summary (never contains full sensitive data)
        
        Args:
            value: Sensitive value
            category: Pattern category
            pattern_name: Pattern name (if available)
            
        Returns:
            Evidence summary dict with hash/last4/token-class
        """
        summary = {
            "category": category.value,
            "pattern": pattern_name or "unknown",
            "length": len(value),
            "hash": self._compute_hash(value),
        }
        
        # Add category-specific summaries
        if category == PatternCategory.PII_EMAIL:
            summary["domain"] = self._extract_email_domain(value) if self.preserve_domain else None
            summary["local_part_hash"] = self._compute_hash(value.split("@")[0] if "@" in value else value)
        
        elif category == PatternCategory.PAYMENT_CARD:
            summary["last4"] = value[-4:] if len(value) >= 4 and self.preserve_last4 else None
            summary["bin"] = value[:6] if len(value) >= 6 else None  # First 6 digits (BIN)
        
        elif category in (PatternCategory.API_KEY, PatternCategory.SECRET_TOKEN, PatternCategory.PRIVATE_KEY):
            summary["prefix"] = value[:4] if len(value) >= 4 else None  # First 4 chars
            summary["suffix"] = value[-4:] if len(value) >= 4 and self.preserve_last4 else None
            summary["token_class"] = self._classify_token(value)
        
        elif category == PatternCategory.PII_PHONE:
            summary["last4"] = value[-4:] if len(value) >= 4 and self.preserve_last4 else None
            summary["area_code"] = value[:3] if len(value) >= 3 else None
        
        elif category == PatternCategory.PII_SSN:
            summary["last4"] = value[-4:] if len(value) >= 4 and self.preserve_last4 else None
        
        return summary
    
    def sanitize_value(
        self,
        value: str,
        category: PatternCategory,
        mode: RedactionMode = RedactionMode.FULL,
    ) -> str:
        """
        Sanitize a single value based on category
        
        Args:
            value: Value to sanitize
            category: Pattern category
            mode: Redaction mode
            
        Returns:
            Sanitized value
        """
        if mode == RedactionMode.SUMMARY:
            # Summary mode: return placeholder
            return f"[{category.value.upper()}_REDACTED]"
        
        if mode == RedactionMode.PARTIAL and self.preserve_usability:
            # Partial mode with usability preservation
            if category == PatternCategory.PII_EMAIL:
                if "@" in value:
                    local, domain = value.split("@", 1)
                    if self.preserve_domain:
                        return f"{self._mask_string(local)}@{domain}"
                    else:
                        return f"{self._mask_string(local)}@{self._mask_string(domain)}"
                else:
                    return self._mask_string(value)
            
            elif category == PatternCategory.PAYMENT_CARD:
                # Preserve last 4 digits
                if len(value) >= 4 and self.preserve_last4:
                    return f"{'*' * (len(value) - 4)}{value[-4:]}"
                else:
                    return "*" * len(value)
            
            elif category in (PatternCategory.API_KEY, PatternCategory.SECRET_TOKEN):
                # Preserve prefix and suffix
                if len(value) >= 8:
                    prefix_len = min(4, len(value) // 4)
                    suffix_len = min(4, len(value) // 4) if self.preserve_last4 else 0
                    middle_len = len(value) - prefix_len - suffix_len
                    return f"{value[:prefix_len]}{'*' * middle_len}{value[-suffix_len:] if suffix_len > 0 else ''}"
                else:
                    return "*" * len(value)
            
            elif category == PatternCategory.PII_PHONE:
                # Preserve last 4 digits
                if len(value) >= 4 and self.preserve_last4:
                    return f"{'*' * (len(value) - 4)}{value[-4:]}"
                else:
                    return "*" * len(value)
            
            elif category == PatternCategory.PII_SSN:
                # Preserve last 4 digits
                if len(value) >= 4 and self.preserve_last4:
                    return f"***-**-{value[-4:]}"
                else:
                    return "***-**-****"
        
        # Full mode: complete redaction
        return "*" * min(len(value), 20)  # Cap at 20 chars for readability
    
    def sanitize_structured(
        self,
        data: Any,
        paths: List[str],
        category: PatternCategory,
        mode: RedactionMode = RedactionMode.FULL,
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Sanitize structured data using JSON key paths
        
        Args:
            data: Data structure (dict/list)
            paths: List of JSON key paths (e.g., ["user.email", "payment.card"])
            category: Pattern category
            mode: Redaction mode
            
        Returns:
            Tuple of (sanitized_data, evidence_summaries)
            evidence_summaries: Dict mapping path -> evidence summary
        """
        evidence_summaries = {}
        sanitized = self._sanitize_recursive(data, paths, category, mode, "", evidence_summaries)
        return sanitized, evidence_summaries
    
    def _sanitize_recursive(
        self,
        data: Any,
        paths: List[str],
        category: PatternCategory,
        mode: RedactionMode,
        current_path: str,
        evidence_summaries: Dict[str, Any],
    ) -> Any:
        """Recursively sanitize data structure"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                new_path = f"{current_path}.{key}" if current_path else key
                
                # Check if this path should be sanitized
                if self._path_matches(new_path, paths):
                    if isinstance(value, str):
                        # Create evidence summary
                        evidence_summaries[new_path] = self.create_evidence_summary(value, category)
                        # Sanitize value
                        result[key] = self.sanitize_value(value, category, mode)
                    else:
                        # Recursively sanitize nested structure
                        result[key] = self._sanitize_recursive(
                            value, paths, category, mode, new_path, evidence_summaries
                        )
                else:
                    # Not in paths, keep as-is or recurse
                    if isinstance(value, (dict, list)):
                        result[key] = self._sanitize_recursive(
                            value, paths, category, mode, new_path, evidence_summaries
                        )
                    else:
                        result[key] = value
            
            return result
        
        elif isinstance(data, list):
            result = []
            for i, item in enumerate(data):
                new_path = f"{current_path}[{i}]"
                result.append(
                    self._sanitize_recursive(
                        item, paths, category, mode, new_path, evidence_summaries
                    )
                )
            return result
        
        else:
            # Primitive value
            if self._path_matches(current_path, paths) and isinstance(data, str):
                evidence_summaries[current_path] = self.create_evidence_summary(data, category)
                return self.sanitize_value(data, category, mode)
            return data
    
    def _path_matches(self, path: str, target_paths: List[str]) -> bool:
        """Check if path matches any target path (supports wildcards)"""
        for target in target_paths:
            # Exact match
            if path == target:
                return True
            
            # Prefix match (e.g., "user.*" matches "user.email")
            if target.endswith(".*"):
                prefix = target[:-2]
                if path.startswith(prefix + "."):
                    return True
            
            # Wildcard match (e.g., "*.email" matches "user.email")
            if target.startswith("*."):
                suffix = target[2:]
                if path.endswith("." + suffix) or path == suffix:
                    return True
        
        return False
    
    def _compute_hash(self, value: str) -> str:
        """Compute SHA256 hash of value"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]  # First 16 chars
    
    def _extract_email_domain(self, email: str) -> Optional[str]:
        """Extract email domain"""
        if "@" in email:
            return email.split("@", 1)[1]
        return None
    
    def _classify_token(self, token: str) -> str:
        """Classify token type based on prefix/pattern"""
        if token.startswith("sk-"):
            return "openai_api_key"
        elif token.startswith("AKIA"):
            return "aws_access_key"
        elif token.startswith("ghp_") or token.startswith("ghs_"):
            return "github_token"
        elif "-----BEGIN" in token:
            return "private_key"
        else:
            return "generic_token"
    
    def _mask_string(self, s: str, mask_char: str = "*", keep_chars: int = 0) -> str:
        """Mask string, optionally keeping some characters"""
        if keep_chars > 0 and len(s) > keep_chars:
            return mask_char * (len(s) - keep_chars) + s[-keep_chars:]
        return mask_char * len(s)


__all__ = [
    "StructuredSanitizer",
    "RedactionMode",
]
