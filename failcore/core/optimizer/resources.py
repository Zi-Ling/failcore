"""
Resource Identification and Mutation Detection

Extract resource IDs from tool parameters and detect mutations

Key correctness rules:
- Write barriers are PER-RESOURCE (not per-tool)
- Paths must be normalized (case, separators, relative)
- HTTP resources default to no barrier (external)
"""

from typing import Dict, Any, Optional, List
import re
from urllib.parse import urlparse
from pathlib import Path
import os

from .models import ResourceType, MutationType


class ResourceIdExtractor:
    """
    Extract resource IDs from tool parameters
    
    Converts paths, URLs, table names into canonical resource IDs:
    - file:///path/to/file
    - http://example.com/api
    - db://table_name
    """
    
    def __init__(self):
        # Tool patterns for resource extraction
        self.file_tools = {
            "read_file", "write_file", "delete_file", "append_file",
            "read_dir", "list_dir", "stat_file", "rename_file",
        }
        
        self.http_tools = {
            "http_get", "http_post", "http_put", "http_delete",
            "fetch_url", "api_call", "api_get", "api_post",
        }
        
        self.db_tools = {
            "db_query", "db_insert", "db_update", "db_delete",
            "db_fetch", "db_count",
        }
    
    def extract(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> List[str]:
        """
        Extract resource IDs from tool call
        
        Args:
            tool_name: Tool name
            params: Tool parameters
        
        Returns:
            List of resource IDs (may be multiple for batch operations)
        """
        resource_ids = []
        
        # File resources
        if tool_name in self.file_tools or "file" in tool_name.lower():
            file_id = self._extract_file_resource(params)
            if file_id:
                resource_ids.append(file_id)
        
        # HTTP resources
        elif tool_name in self.http_tools or any(k in tool_name.lower() for k in ["http", "url", "api"]):
            http_id = self._extract_http_resource(params)
            if http_id:
                resource_ids.append(http_id)
        
        # Database resources
        elif tool_name in self.db_tools or "db" in tool_name.lower():
            db_ids = self._extract_db_resource(params)
            resource_ids.extend(db_ids)
        
        # Fallback: try to extract from common parameter names
        if not resource_ids:
            fallback_id = self._extract_fallback_resource(params)
            if fallback_id:
                resource_ids.append(fallback_id)
        
        return resource_ids
    
    def _extract_file_resource(self, params: Dict[str, Any]) -> Optional[str]:
        """Extract file resource ID"""
        # Common file parameter names
        for key in ["path", "file", "filename", "filepath", "file_path"]:
            if key in params:
                path = str(params[key])
                # Normalize path and create resource ID
                return self._normalize_file_path(path)
        return None
    
    def _extract_http_resource(self, params: Dict[str, Any]) -> Optional[str]:
        """Extract HTTP resource ID"""
        for key in ["url", "endpoint", "uri"]:
            if key in params:
                url = str(params[key])
                return self._normalize_url(url)
        return None
    
    def _extract_db_resource(self, params: Dict[str, Any]) -> List[str]:
        """Extract database resource IDs"""
        resources = []
        
        # Direct table name
        if "table" in params:
            table = str(params["table"])
            resources.append(f"db://{table}")
        
        # Parse SQL for table names
        if "sql" in params:
            sql = str(params["sql"])
            tables = self._parse_sql_tables(sql)
            resources.extend([f"db://{t}" for t in tables])
        
        return resources
    
    def _extract_fallback_resource(self, params: Dict[str, Any]) -> Optional[str]:
        """Fallback extraction from any parameter"""
        for key, value in params.items():
            if isinstance(value, str):
                # Check if looks like a path
                if "/" in value or "\\" in value:
                    return self._normalize_file_path(value)
                # Check if looks like a URL
                if value.startswith(("http://", "https://")):
                    return self._normalize_url(value)
        return None
    
    def _normalize_file_path(self, path: str) -> str:
        """
        Normalize file path to resource ID
        
        Critical for correctness:
        - Handles Windows/Unix path separators
        - Case-insensitive on Windows
        - Resolves relative paths (./, ../)
        - Removes redundant separators
        """
        try:
            # Use pathlib for cross-platform normalization
            p = Path(path)
            
            # Normalize: resolve ./ and ../
            # Note: Don't use resolve() as it makes paths absolute
            normalized = p.as_posix()  # Convert to forward slashes
            
            # On Windows, lowercase for case-insensitive comparison
            if os.name == 'nt':
                normalized = normalized.lower()
            
            # Remove redundant slashes
            normalized = re.sub(r'/+', '/', normalized)
            
            # Remove leading ./ if present
            if normalized.startswith('./'):
                normalized = normalized[2:]
            
            # Create resource ID
            if normalized.startswith('/'):
                return f"file://{normalized}"
            else:
                return f"file:///{normalized}"
        except Exception:
            # Fallback: simple normalization
            normalized = path.replace("\\", "/")
            normalized = re.sub(r'/+', '/', normalized)
            if os.name == 'nt':
                normalized = normalized.lower()
            return f"file:///{normalized}"
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL to resource ID
        
        Note: We don't apply write barriers to HTTP by default
        (external resources are not under our control)
        """
        try:
            parsed = urlparse(url)
            # Normalize: lowercase host, remove fragment, normalize path
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            path = parsed.path or '/'
            
            # Remove trailing slash for consistency
            if path != '/' and path.endswith('/'):
                path = path[:-1]
            
            normalized = f"{scheme}://{netloc}{path}"
            
            # Include query for uniqueness (but not fragment)
            if parsed.query:
                normalized += f"?{parsed.query}"
            
            return normalized
        except Exception:
            return url.lower()
    
    def _parse_sql_tables(self, sql: str) -> List[str]:
        """Parse table names from SQL (simple heuristic)"""
        tables = []
        
        # Common SQL patterns
        patterns = [
            r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        ]
        
        sql_upper = sql.upper()
        for pattern in patterns:
            matches = re.finditer(pattern, sql_upper, re.IGNORECASE)
            for match in matches:
                table = match.group(1).lower()
                if table not in tables:
                    tables.append(table)
        
        return tables


class ResourceMutationDetector:
    """
    Detect resource mutations (write/delete/rename)
    
    This is critical for cache invalidation and write barriers
    """
    
    def __init__(self):
        # Mutation patterns by tool name
        self.mutation_patterns = {
            # Write operations
            MutationType.WRITE: {
                "write_file", "write", "save", "create_file", "put_file",
                "db_insert", "db_update", "insert", "update",
                "http_post", "http_put", "api_post", "api_put",
                "upload", "publish",
            },
            
            # Delete operations
            MutationType.DELETE: {
                "delete_file", "remove_file", "unlink", "delete",
                "db_delete", "drop",
                "http_delete", "api_delete",
            },
            
            # Rename/move operations
            MutationType.RENAME: {
                "rename_file", "move_file", "rename", "move",
            },
            
            # Append operations
            MutationType.APPEND: {
                "append_file", "append",
            },
        }
    
    def detect_mutation(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Optional[MutationType]:
        """
        Detect if tool call mutates resources
        
        Args:
            tool_name: Tool name
            params: Tool parameters
        
        Returns:
            Mutation type or None if read-only
        """
        tool_lower = tool_name.lower()
        
        # Check exact match first
        for mutation_type, patterns in self.mutation_patterns.items():
            if tool_name in patterns or tool_lower in patterns:
                return mutation_type
        
        # Check substring match (e.g., "my_write_tool" contains "write")
        for mutation_type, patterns in self.mutation_patterns.items():
            if any(pattern in tool_lower for pattern in patterns):
                return mutation_type
        
        # Special case: SQL mutations
        if "db" in tool_lower or "sql" in tool_lower:
            if "sql" in params:
                sql = str(params["sql"]).upper()
                if any(kw in sql for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]):
                    return MutationType.WRITE
        
        # Default: assume read-only
        return None
    
    def is_mutating(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """Check if tool call mutates resources"""
        return self.detect_mutation(tool_name, params) is not None
    
    def is_read_only(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """Check if tool call is read-only"""
        return not self.is_mutating(tool_name, params)


__all__ = [
    "ResourceIdExtractor",
    "ResourceMutationDetector",
]
