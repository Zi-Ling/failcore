# failcore/core/janitor.py
"""
Resource Janitor - cleanup stale FailCore resources

Provides automatic cleanup of orphaned resources (sandboxes, processes, temp files)
left by crashed or interrupted sessions.

Design:
- Each session creates a manifest file with metadata (sandbox, pgid, timestamp)
- Janitor scans manifests and cleans up resources from dead sessions
- Safe cross-platform implementation with proper error handling
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from failcore.utils.process import pid_exists, cleanup_processes
from failcore.utils.paths import get_failcore_root

logger = logging.getLogger(__name__)


class SessionManifest:
    """Manifest file for a session's resources"""
    
    def __init__(
        self,
        session_id: str,
        sandbox_root: str,
        created_at: float,
        pgid: Optional[int] = None,
        pids: Optional[List[int]] = None,
        last_heartbeat: Optional[float] = None,
    ):
        self.session_id = session_id
        self.sandbox_root = sandbox_root
        self.created_at = created_at
        self.pgid = pgid
        self.pids = pids or []
        self.last_heartbeat = last_heartbeat or created_at
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "sandbox_root": self.sandbox_root,
            "created_at": self.created_at,
            "pgid": self.pgid,
            "pids": self.pids,
            "last_heartbeat": self.last_heartbeat,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionManifest":
        return cls(
            session_id=data["session_id"],
            sandbox_root=data["sandbox_root"],
            created_at=data["created_at"],
            pgid=data.get("pgid"),
            pids=data.get("pids", []),
            last_heartbeat=data.get("last_heartbeat"),
        )
    
    def save(self, manifest_dir: Path) -> None:
        """Save manifest to disk"""
        manifest_file = manifest_dir / f"{self.session_id}.json"
        try:
            with open(manifest_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session manifest: {e}")
    
    @classmethod
    def load(cls, manifest_file: Path) -> Optional["SessionManifest"]:
        """Load manifest from disk"""
        try:
            with open(manifest_file, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load manifest {manifest_file}: {e}")
            return None
    
    def is_stale(self, max_age_hours: float = 24.0, heartbeat_timeout_seconds: float = 300.0) -> bool:
        """
        Check if session is stale (likely dead)
        
        Args:
            max_age_hours: Maximum age in hours before considering stale
            heartbeat_timeout_seconds: Seconds since last heartbeat to consider dead
            
        Returns:
            True if session is stale
        """
        now = time.time()
        
        # Check if too old (absolute)
        age_hours = (now - self.created_at) / 3600
        if age_hours > max_age_hours:
            return True
        
        # Check if heartbeat timed out
        if self.last_heartbeat:
            since_heartbeat = now - self.last_heartbeat
            if since_heartbeat > heartbeat_timeout_seconds:
                return True
        
        return False


class ResourceJanitor:
    """
    Cleanup orphaned FailCore resources
    
    Scans session manifests and cleans up resources from dead/crashed sessions.
    Safe to run at startup or periodically.
    """
    
    def __init__(self, failcore_root: Optional[Path] = None):
        """
        Initialize janitor
        
        Args:
            failcore_root: FailCore root directory (default: from get_failcore_root())
        """
        self.failcore_root = failcore_root or get_failcore_root()
        self.manifest_dir = self.failcore_root / "sessions"
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
    
    def scan_manifests(self) -> List[SessionManifest]:
        """Scan all session manifests"""
        manifests = []
        
        try:
            for manifest_file in self.manifest_dir.glob("*.json"):
                manifest = SessionManifest.load(manifest_file)
                if manifest:
                    manifests.append(manifest)
        except Exception as e:
            logger.error(f"Error scanning manifests: {e}")
        
        return manifests
    
    def is_session_alive(self, manifest: SessionManifest) -> bool:
        """
        Check if session is still alive
        
        Strategy:
        1. Check if any registered PIDs exist
        2. Check if process group leader exists (if pgid available)
        
        Args:
            manifest: Session manifest
            
        Returns:
            True if session appears to be alive
        """
        # Check PIDs
        if manifest.pids:
            for pid in manifest.pids:
                if pid_exists(pid, timeout=1.0):
                    logger.debug(f"Session {manifest.session_id} has alive PID {pid}")
                    return True
        
        # Check PGID (process group leader)
        if manifest.pgid:
            if pid_exists(manifest.pgid, timeout=1.0):
                logger.debug(f"Session {manifest.session_id} has alive PGID {manifest.pgid}")
                return True
        
        return False
    
    def cleanup_session(self, manifest: SessionManifest) -> Dict[str, bool]:
        """
        Cleanup a single session's resources
        
        Args:
            manifest: Session manifest
            
        Returns:
            Dict with cleanup results: {
                "processes": bool,
                "sandbox": bool,
                "manifest": bool,
            }
        """
        results = {
            "processes": True,
            "sandbox": True,
            "manifest": True,
        }
        
        session_id = manifest.session_id
        logger.info(f"Cleaning up session {session_id}")
        
        # 1. Cleanup processes
        if manifest.pids:
            try:
                cleanup_results = cleanup_processes(manifest.pids, timeout=5.0)
                results["processes"] = all(cleanup_results.values())
                
                if not results["processes"]:
                    failed_pids = [pid for pid, ok in cleanup_results.items() if not ok]
                    logger.warning(f"Failed to cleanup PIDs {failed_pids} for session {session_id}")
            except Exception as e:
                logger.error(f"Error cleaning up processes for session {session_id}: {e}")
                results["processes"] = False
        
        # 2. Cleanup sandbox directory
        if manifest.sandbox_root:
            try:
                sandbox_path = Path(manifest.sandbox_root)
                
                # Safety check: only delete if within failcore_root
                if sandbox_path.exists():
                    # Check if sandbox is within failcore managed directories
                    try:
                        # This will raise ValueError if not relative
                        sandbox_path.resolve().relative_to(self.failcore_root.resolve())
                        
                        # Safe to delete
                        import shutil
                        shutil.rmtree(sandbox_path, ignore_errors=True)
                        logger.info(f"Deleted sandbox {sandbox_path} for session {session_id}")
                    except ValueError:
                        # Not within failcore_root, don't delete
                        logger.warning(f"Sandbox {sandbox_path} is outside failcore_root, skipping deletion")
                        results["sandbox"] = False
            except Exception as e:
                logger.error(f"Error cleaning up sandbox for session {session_id}: {e}")
                results["sandbox"] = False
        
        # 3. Remove manifest file
        try:
            manifest_file = self.manifest_dir / f"{session_id}.json"
            if manifest_file.exists():
                manifest_file.unlink()
                logger.debug(f"Deleted manifest for session {session_id}")
        except Exception as e:
            logger.error(f"Error deleting manifest for session {session_id}: {e}")
            results["manifest"] = False
        
        return results
    
    def cleanup_stale_sessions(
        self,
        max_age_hours: float = 24.0,
        force: bool = False
    ) -> Dict[str, Dict[str, bool]]:
        """
        Cleanup all stale sessions
        
        Args:
            max_age_hours: Maximum age in hours before considering stale
            force: If True, cleanup all sessions regardless of age/heartbeat
            
        Returns:
            Dict mapping session_id to cleanup results
        """
        logger.info(f"Starting janitor cleanup (max_age={max_age_hours}h, force={force})")
        
        manifests = self.scan_manifests()
        logger.info(f"Found {len(manifests)} session manifests")
        
        cleanup_results = {}
        
        for manifest in manifests:
            session_id = manifest.session_id
            
            # Check if should cleanup
            should_cleanup = force or manifest.is_stale(max_age_hours=max_age_hours)
            
            if should_cleanup:
                # Double-check if session is actually dead
                if not force and self.is_session_alive(manifest):
                    logger.info(f"Session {session_id} appears alive, skipping cleanup")
                    continue
                
                # Cleanup
                results = self.cleanup_session(manifest)
                cleanup_results[session_id] = results
            else:
                logger.debug(f"Session {session_id} is not stale, skipping")
        
        if cleanup_results:
            logger.info(f"Cleaned up {len(cleanup_results)} stale sessions")
        else:
            logger.info("No stale sessions found")
        
        return cleanup_results
    
    def register_session(self, manifest: SessionManifest) -> None:
        """Register a new session (save manifest)"""
        manifest.save(self.manifest_dir)
        logger.debug(f"Registered session {manifest.session_id}")
    
    def unregister_session(self, session_id: str) -> None:
        """Unregister a session (delete manifest)"""
        try:
            manifest_file = self.manifest_dir / f"{session_id}.json"
            if manifest_file.exists():
                manifest_file.unlink()
                logger.debug(f"Unregistered session {session_id}")
        except Exception as e:
            logger.error(f"Error unregistering session {session_id}: {e}")
    
    def update_heartbeat(self, session_id: str) -> None:
        """Update session heartbeat timestamp"""
        try:
            manifest_file = self.manifest_dir / f"{session_id}.json"
            if manifest_file.exists():
                manifest = SessionManifest.load(manifest_file)
                if manifest:
                    manifest.last_heartbeat = time.time()
                    manifest.save(self.manifest_dir)
        except Exception as e:
            logger.error(f"Error updating heartbeat for session {session_id}: {e}")


__all__ = [
    "SessionManifest",
    "ResourceJanitor",
]
