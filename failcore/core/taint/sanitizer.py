"""
Taint Tracking - Sanitizer

Data sanitization/anonymization for DLP
"""

import re
from typing import Any, Dict


class DataSanitizer:
    """
    Sanitize sensitive data before leakage
    
    Supports:
    - PII masking (email, phone, SSN)
    - Secret redaction (API keys, tokens, passwords)
    - Custom pattern matching
    """
    
    # Common PII patterns
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'
    CREDIT_CARD_PATTERN = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    
    # Secret patterns
    API_KEY_PATTERN = r'(api[_-]?key|apikey)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})'
    TOKEN_PATTERN = r'(token|auth)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})'
    PASSWORD_PATTERN = r'(password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\']{8,})'
    
    def __init__(self):
        self.patterns = {
            "email": self.EMAIL_PATTERN,
            "phone": self.PHONE_PATTERN,
            "ssn": self.SSN_PATTERN,
            "credit_card": self.CREDIT_CARD_PATTERN,
            "api_key": self.API_KEY_PATTERN,
            "token": self.TOKEN_PATTERN,
            "password": self.PASSWORD_PATTERN,
        }
    
    def sanitize(
        self,
        data: Any,
        mask_pii: bool = True,
        mask_secrets: bool = True,
        replacement: str = "***REDACTED***"
    ) -> Any:
        """
        Sanitize data by masking sensitive information
        
        Args:
            data: Data to sanitize
            mask_pii: Mask PII (email, phone, SSN)
            mask_secrets: Mask secrets (API keys, tokens)
            replacement: Replacement string
        
        Returns:
            Sanitized data
        """
        if isinstance(data, str):
            return self._sanitize_string(data, mask_pii, mask_secrets, replacement)
        
        elif isinstance(data, dict):
            return {
                key: self.sanitize(value, mask_pii, mask_secrets, replacement)
                for key, value in data.items()
            }
        
        elif isinstance(data, list):
            return [
                self.sanitize(item, mask_pii, mask_secrets, replacement)
                for item in data
            ]
        
        else:
            return data
    
    def _sanitize_string(
        self,
        text: str,
        mask_pii: bool,
        mask_secrets: bool,
        replacement: str
    ) -> str:
        """Sanitize string by masking patterns"""
        result = text
        
        # Mask PII
        if mask_pii:
            result = re.sub(self.EMAIL_PATTERN, replacement, result)
            result = re.sub(self.PHONE_PATTERN, replacement, result)
            result = re.sub(self.SSN_PATTERN, replacement, result)
            result = re.sub(self.CREDIT_CARD_PATTERN, replacement, result)
        
        # Mask secrets
        if mask_secrets:
            result = re.sub(self.API_KEY_PATTERN, r'\1=' + replacement, result, flags=re.IGNORECASE)
            result = re.sub(self.TOKEN_PATTERN, r'\1=' + replacement, result, flags=re.IGNORECASE)
            result = re.sub(self.PASSWORD_PATTERN, r'\1=' + replacement, result, flags=re.IGNORECASE)
        
        return result
    
    def detect_sensitive_patterns(self, data: Any) -> Dict[str, int]:
        """
        Detect sensitive patterns in data (without sanitizing)
        
        Returns:
            Dict of pattern_name -> count
        """
        counts = {}
        
        if isinstance(data, str):
            for pattern_name, pattern in self.patterns.items():
                matches = re.findall(pattern, data, flags=re.IGNORECASE)
                if matches:
                    counts[pattern_name] = len(matches)
        
        elif isinstance(data, dict):
            for value in data.values():
                sub_counts = self.detect_sensitive_patterns(value)
                for pattern_name, count in sub_counts.items():
                    counts[pattern_name] = counts.get(pattern_name, 0) + count
        
        elif isinstance(data, list):
            for item in data:
                sub_counts = self.detect_sensitive_patterns(item)
                for pattern_name, count in sub_counts.items():
                    counts[pattern_name] = counts.get(pattern_name, 0) + count
        
        return counts


__all__ = ["DataSanitizer"]
