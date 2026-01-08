# failcore/web/services/artifacts_service.py
"""
Artifact management service.

Artifacts are outputs (reports, audits, exports, diffs, etc.)
Unified handling for preview and download.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, List
from failcore.utils.paths import get_failcore_root


ArtifactType = Literal[
    "report_html",
    "report_json",
    "audit_json",
    "audit_html",
    "trace_export",
    "diff_json",
]

PreviewMode = Literal["html_embed", "json_viewer", "download_only", "text"]


@dataclass
class Artifact:
    """
    Represents an output file/resource.
    
    Artifacts unify all outputs (reports, audits, etc.) into
    a consistent display and download model.
    """
    artifact_id: str
    type: ArtifactType
    path: Path
    mime: str
    size: int
    created_at: float
    preview_mode: PreviewMode
    metadata: dict = None


class ArtifactsService:
    """
    Artifact registry and access.
    """
    
    def __init__(self):
        self._artifacts_dir = get_failcore_root() / "artifacts"
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID (placeholder)."""
        # TODO: Implement artifact lookup
        return None
    
    def list_artifacts_for_job(self, job_id: str) -> List[Artifact]:
        """List artifacts produced by a job."""
        # TODO: Implement job artifact lookup
        return []
    
    def get_preview(self, artifact_id: str) -> Optional[str]:
        """Get artifact preview content."""
        artifact = self.get_artifact(artifact_id)
        if not artifact or not artifact.path.exists():
            return None
        
        if artifact.preview_mode == "download_only":
            return None
        
        # Read and return content
        try:
            return artifact.path.read_text(encoding='utf-8')
        except:
            return None


# Global singleton
_service = ArtifactsService()


def get_artifacts_service() -> ArtifactsService:
    """Get the global artifacts service."""
    return _service


__all__ = ["Artifact", "ArtifactsService", "get_artifacts_service", "ArtifactType"]
