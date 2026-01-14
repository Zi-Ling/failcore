# failcore/core/guards/cache.py
"""
Scan Cache - Run-scoped cache for scanner results

Provides:
- Cache key: (payload_fingerprint, scanner_id) -> ScanResult
- Run-scoped isolation (no global cache)
- Step association: step_id -> set[CacheKey]
- TTL and capacity limits (LRU eviction)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone


# Scanner ID enum (fixed values to avoid typos)
class ScannerID(str):
    """Scanner identifier (fixed enum values)"""
    DLP = "dlp"
    SEMANTIC = "semantic"
    TAINT = "taint"


@dataclass(frozen=True)
class CacheKey:
    """
    Cache key: (payload_fingerprint, scanner_id)
    
    Immutable key for cache entries to prevent accidental modification.
    """
    payload_fingerprint: str
    scanner_id: str
    
    def __str__(self) -> str:
        return f"{self.scanner_id}:{self.payload_fingerprint}"


@dataclass
class ScanResult:
    """
    Cached scan result
    
    Stable structure for scanner results that can be serialized to trace.
    """
    cache_key: CacheKey
    timestamp: str
    results: Dict[str, Any]  # Scanner-specific results
    evidence: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "cache_key": str(self.cache_key),
            "scanner_id": self.cache_key.scanner_id,
            "payload_fingerprint": self.cache_key.payload_fingerprint,
            "timestamp": self.timestamp,
            "results": self.results,
            "evidence": self.evidence,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScanResult":
        """Create from dict"""
        cache_key = CacheKey(
            payload_fingerprint=data["payload_fingerprint"],
            scanner_id=data["scanner_id"],
        )
        return cls(
            cache_key=cache_key,
            timestamp=data["timestamp"],
            results=data["results"],
            evidence=data.get("evidence", {}),
            metadata=data.get("metadata", {}),
        )


class ScanCache:
    """
    Run-scoped scan cache for scanner results
    
    Design principles:
    - Run-scoped only (no global cache, no context dict lookup)
    - Cache key: (payload_fingerprint, scanner_id) -> ScanResult
    - Step association: step_id -> set[CacheKey]
    - Scanners are the ONLY producers (Gate/Enricher only read)
    """
    
    def __init__(
        self,
        run_id: str,
        max_size: int = 1000,
        ttl_seconds: Optional[int] = None,
    ):
        """
        Initialize scan cache
        
        Args:
            run_id: Run ID (required for isolation)
            max_size: Maximum cache size (LRU eviction)
            ttl_seconds: Optional TTL for cache entries
        """
        if not run_id:
            raise ValueError("run_id is required for cache isolation")
        
        self.run_id = run_id
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        
        # CacheKey -> ScanResult
        self._cache: Dict[CacheKey, ScanResult] = {}
        
        # step_id -> set[CacheKey] (for trace association)
        self._step_keys: Dict[str, Set[CacheKey]] = {}
        
        # LRU tracking: list of CacheKeys in access order
        self._access_order: List[CacheKey] = []
    
    def compute_fingerprint(self, payload: Any) -> str:
        """
        Compute fingerprint for payload
        
        Args:
            payload: Payload to fingerprint (dict, list, str, etc.)
            
        Returns:
            SHA256 fingerprint (first 16 chars)
        """
        # Serialize payload to JSON string
        try:
            payload_str = json.dumps(payload, sort_keys=True)
        except (TypeError, ValueError):
            # Fallback: string representation
            payload_str = str(payload)
        
        # Compute hash
        hash_obj = hashlib.sha256(payload_str.encode())
        return hash_obj.hexdigest()[:16]
    
    def store_result(
        self,
        payload: Any,
        scanner_id: str,
        results: Dict[str, Any],
        evidence: Optional[Dict[str, Any]] = None,
        step_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CacheKey:
        """
        Store scan result in cache (called by scanners only)
        
        Args:
            payload: Scanned payload
            scanner_id: Scanner ID (e.g., "dlp", "semantic", "taint")
            results: Scan results
            evidence: Evidence dict
            step_id: Optional step ID for trace association
            metadata: Optional metadata
            
        Returns:
            CacheKey for the stored result
        """
        payload_fingerprint = self.compute_fingerprint(payload)
        cache_key = CacheKey(
            payload_fingerprint=payload_fingerprint,
            scanner_id=scanner_id,
        )
        
        # Check capacity and evict if needed
        if len(self._cache) >= self.max_size:
            self._evict_lru()
        
        result = ScanResult(
            cache_key=cache_key,
            timestamp=datetime.now(timezone.utc).isoformat(),
            results=results,
            evidence=evidence or {},
            metadata=(metadata or {}) | {"run_id": self.run_id},
        )
        
        self._cache[cache_key] = result
        
        # Update LRU access order
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)
        
        # Associate with step if provided
        if step_id:
            if step_id not in self._step_keys:
                self._step_keys[step_id] = set()
            self._step_keys[step_id].add(cache_key)
        
        return cache_key
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry"""
        if not self._access_order:
            return
        
        # Remove oldest entry
        oldest_key = self._access_order.pop(0)
        if oldest_key in self._cache:
            del self._cache[oldest_key]
        
        # Clean up step associations
        for step_id, keys in list(self._step_keys.items()):
            if oldest_key in keys:
                keys.remove(oldest_key)
                if not keys:
                    del self._step_keys[step_id]
    
    def get_result(
        self,
        payload: Any,
        scanner_id: str,
    ) -> Optional[ScanResult]:
        """
        Get cached scan result (must provide scanner_id)
        
        Args:
            payload: Payload to look up
            scanner_id: Scanner ID (required)
            
        Returns:
            ScanResult if found, None otherwise
        """
        payload_fingerprint = self.compute_fingerprint(payload)
        cache_key = CacheKey(
            payload_fingerprint=payload_fingerprint,
            scanner_id=scanner_id,
        )
        
        if cache_key not in self._cache:
            return None
        
        result = self._cache[cache_key]
        
        # Check TTL
        if self.ttl_seconds:
            try:
                result_time = datetime.fromisoformat(result.timestamp.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - result_time).total_seconds()
                if age > self.ttl_seconds:
                    # Expired, remove from cache
                    del self._cache[cache_key]
                    if cache_key in self._access_order:
                        self._access_order.remove(cache_key)
                    return None
            except Exception:
                pass  # If timestamp parsing fails, keep result
        
        # Update LRU access order
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)
        
        return result
    
    def get_step_results(
        self,
        step_id: str,
        scanner_id: Optional[str] = None,
    ) -> List[ScanResult]:
        """
        Get all scan results for a step (optionally filtered by scanner_id)
        
        Args:
            step_id: Step ID
            scanner_id: Optional scanner ID filter
            
        Returns:
            List of ScanResult objects
        """
        keys = self._step_keys.get(step_id, set())
        results = []
        
        for cache_key in keys:
            # Filter by scanner_id if specified
            if scanner_id and cache_key.scanner_id != scanner_id:
                continue
            
            if cache_key in self._cache:
                results.append(self._cache[cache_key])
        
        return results
    
    def has_result(
        self,
        payload: Any,
        scanner_id: str,
    ) -> bool:
        """
        Check if result exists in cache
        
        Args:
            payload: Payload to check
            scanner_id: Scanner ID (required)
            
        Returns:
            True if result exists
        """
        return self.get_result(payload, scanner_id) is not None
    
    def clear(self) -> None:
        """Clear all cached results"""
        self._cache.clear()
        self._step_keys.clear()
        self._access_order.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dict with cache stats
        """
        scanner_counts = {}
        for cache_key in self._cache.keys():
            scanner_counts[cache_key.scanner_id] = scanner_counts.get(cache_key.scanner_id, 0) + 1
        
        return {
            "run_id": self.run_id,
            "total_results": len(self._cache),
            "total_steps": len(self._step_keys),
            "by_scanner": scanner_counts,
        }


__all__ = [
    "ScannerID",
    "CacheKey",
    "ScanResult",
    "ScanCache",
]
