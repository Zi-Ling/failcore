"""
Semantic Intent Parsers

Deterministic parsing for high-confidence semantic detection:
- Shell tokenization
- SQL keyword extraction
- URL/Path normalization
- Structured payload parsing

These parsers provide structured data for rule evaluation,
reducing false positives compared to regex-only matching.
"""

from __future__ import annotations

import re
import shlex
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from pathlib import Path


class ShellParser:
    """Parse shell commands into structured tokens"""
    
    @staticmethod
    def tokenize(command: str) -> Dict[str, Any]:
        """
        Tokenize shell command into structured components
        
        Args:
            command: Shell command string
            
        Returns:
            Dict with tokens, flags, args, etc.
        """
        try:
            # Use shlex for proper shell tokenization
            tokens = shlex.split(command, posix=True)
        except ValueError:
            # Fallback: simple split
            tokens = command.split()
        
        flags = []
        args = []
        program = tokens[0] if tokens else ""
        
        for token in tokens[1:]:
            if token.startswith("-"):
                flags.append(token)
            else:
                args.append(token)
        
        return {
            "program": program,
            "flags": flags,
            "args": args,
            "raw_tokens": tokens,
            "has_pipe": "|" in command,
            "has_redirect": ">" in command or "<" in command,
            "has_background": "&" in command,
        }
    
    @staticmethod
    def extract_dangerous_flags(tokens: Dict[str, Any]) -> List[str]:
        """Extract dangerous flag combinations"""
        dangerous = []
        flags = tokens.get("flags", [])
        program = tokens.get("program", "").lower()
        
        # Dangerous flag combinations
        if program in ("rm", "del", "remove"):
            if "-r" in flags or "-R" in flags or "--recursive" in flags:
                dangerous.append("recursive_delete")
            if "-f" in flags or "--force" in flags:
                dangerous.append("force_delete")
        
        if program == "chmod":
            # Check for dangerous permissions (777, 000)
            for arg in tokens.get("args", []):
                if arg in ("777", "000", "+x", "+w"):
                    dangerous.append("dangerous_permissions")
        
        if program in ("curl", "wget"):
            # Check for pipe to shell
            if tokens.get("has_pipe"):
                dangerous.append("download_and_execute")
        
        return dangerous


class SQLParser:
    """Parse SQL queries for injection patterns"""
    
    # SQL keywords that indicate injection attempts
    DANGEROUS_KEYWORDS = {
        "union", "select", "insert", "update", "delete", "drop",
        "alter", "create", "exec", "execute", "xp_", "sp_",
    }
    
    @staticmethod
    def extract_keywords(query: str) -> Dict[str, Any]:
        """
        Extract SQL keywords and structure
        
        Args:
            query: SQL query string
            
        Returns:
            Dict with keywords, structure, etc.
        """
        query_lower = query.lower()
        
        keywords = []
        for keyword in SQLParser.DANGEROUS_KEYWORDS:
            # Match whole words only
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, query_lower):
                keywords.append(keyword)
        
        # Check for comment patterns (SQL injection)
        has_comments = bool(re.search(r'--|/\*|\*/|#', query))
        
        # Check for stacked queries (semicolon)
        has_stacked = ";" in query and query.count(";") > 1
        
        # Check for union-based injection
        has_union = "union" in query_lower and "select" in query_lower
        
        return {
            "keywords": keywords,
            "has_comments": has_comments,
            "has_stacked": has_stacked,
            "has_union": has_union,
            "keyword_count": len(keywords),
        }
    
    @staticmethod
    def is_injection_likely(parsed: Dict[str, Any]) -> bool:
        """Check if SQL injection is likely based on parsed structure"""
        # Multiple dangerous keywords
        if parsed.get("keyword_count", 0) >= 2:
            return True
        
        # Stacked queries with comments
        if parsed.get("has_stacked") and parsed.get("has_comments"):
            return True
        
        # Union-based injection
        if parsed.get("has_union"):
            return True
        
        return False


class URLParser:
    """Parse and normalize URLs for SSRF/injection detection"""
    
    @staticmethod
    def parse(url: str) -> Dict[str, Any]:
        """
        Parse URL into structured components
        
        Args:
            url: URL string
            
        Returns:
            Dict with scheme, host, path, query, etc.
        """
        try:
            parsed = urlparse(url)
        except Exception:
            return {"valid": False, "raw": url}
        
        query_params = parse_qs(parsed.query) if parsed.query else {}
        
        return {
            "valid": True,
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "path": parsed.path,
            "query": parsed.query,
            "query_params": query_params,
            "fragment": parsed.fragment,
            "netloc": parsed.netloc,
            "is_internal": URLParser._is_internal_host(parsed.hostname),
        }
    
    @staticmethod
    def _is_internal_host(hostname: Optional[str]) -> bool:
        """Check if hostname is internal/private"""
        if not hostname:
            return False
        
        # Private IP ranges
        internal_patterns = [
            r'^127\.',  # localhost
            r'^10\.',  # 10.0.0.0/8
            r'^172\.(1[6-9]|2[0-9]|3[01])\.',  # 172.16.0.0/12
            r'^192\.168\.',  # 192.168.0.0/16
            r'^169\.254\.',  # link-local
            r'^localhost$',
            r'^\.local$',
        ]
        
        for pattern in internal_patterns:
            if re.match(pattern, hostname, re.IGNORECASE):
                return True
        
        return False


class PathParser:
    """Parse and normalize file paths for traversal detection"""
    
    @staticmethod
    def normalize(path: str) -> Dict[str, Any]:
        """
        Normalize path and detect traversal patterns
        
        Args:
            path: File path string
            
        Returns:
            Dict with normalized path, traversal info, etc.
        """
        # Count ../ sequences
        parent_count = path.count("../") + path.count("..\\")
        
        # Check for absolute paths to sensitive locations
        sensitive_paths = [
            "/etc/passwd", "/etc/shadow", "/etc/hosts",
            "C:\\Windows\\System32", "C:\\Windows\\config",
        ]
        
        is_sensitive = any(
            path.lower().startswith(sp.lower()) for sp in sensitive_paths
        )
        
        # Normalize path
        try:
            normalized = str(Path(path).resolve())
        except Exception:
            normalized = path
        
        return {
            "original": path,
            "normalized": normalized,
            "parent_count": parent_count,
            "has_traversal": parent_count > 0,
            "is_sensitive": is_sensitive,
            "is_absolute": Path(path).is_absolute() if path else False,
        }


class PayloadParser:
    """Parse structured payloads (JSON, XML, etc.) for injection"""
    
    @staticmethod
    def parse_json(payload: str) -> Dict[str, Any]:
        """
        Parse JSON payload and extract structure
        
        Args:
            payload: JSON string
            
        Returns:
            Dict with parsed structure, paths, etc.
        """
        try:
            import json
            data = json.loads(payload)
        except Exception:
            return {"valid": False, "raw": payload}
        
        # Extract all string values and their paths
        string_paths = PayloadParser._extract_string_paths(data)
        
        return {
            "valid": True,
            "data": data,
            "string_paths": string_paths,
            "string_count": len(string_paths),
        }
    
    @staticmethod
    def _extract_string_paths(data: Any, path: str = "") -> List[Tuple[str, str]]:
        """Extract all string values with their JSON paths"""
        paths = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                paths.extend(PayloadParser._extract_string_paths(value, new_path))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                paths.extend(PayloadParser._extract_string_paths(item, new_path))
        
        elif isinstance(data, str):
            paths.append((path, data))
        
        return paths


__all__ = [
    "ShellParser",
    "SQLParser",
    "URLParser",
    "PathParser",
    "PayloadParser",
]
