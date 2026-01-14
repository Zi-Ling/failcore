# failcore/adapters/mcp/egress.py
"""
MCP Egress Integration - Connect MCP tool calls to unified egress pipeline

All MCP tool executions flow through EgressEngine for unified audit/trace/cost.
"""

from typing import Any, Dict, Optional
import time

from failcore.core.egress import (
    EgressEngine,
    EgressEvent,
    EgressType,
    PolicyDecision,
    RiskLevel,
)


class McpEgressIntegration:
    """
    Egress integration for MCP sessions
    
    Responsibilities:
    - Generate EgressEvent for MCP tool calls
    - Route through EgressEngine for unified processing
    - Map MCP tool metadata to egress types
    
    Design:
    - Pre-call: emit NETWORK/FS/EXEC event based on tool metadata
    - Post-call: enrich with usage/output evidence
    - Fail-safe: errors don't block MCP execution
    """
    
    def __init__(self, egress_engine: Optional[EgressEngine] = None):
        self.egress_engine = egress_engine
    
    def emit_pre_call(
        self,
        method: str,
        params: Optional[Dict[str, Any]],
        run_id: str,
        step_id: str,
    ) -> Optional[str]:
        """
        Emit pre-call egress event
        
        Args:
            method: MCP method name
            params: Method parameters
            run_id: Run ID
            step_id: Step ID
        
        Returns:
            Event ID for correlation (or None if engine not configured)
        """
        if not self.egress_engine:
            return None
        
        try:
            # Infer egress type from method
            egress_type, action, target = self._infer_egress_info(method, params)
            
            event = EgressEvent(
                egress=egress_type,
                action=action,
                target=target,
                run_id=run_id,
                step_id=step_id,
                tool_name=method,
                decision=PolicyDecision.ALLOW,  # Pre-call, assume allow
                risk=RiskLevel.LOW,
                evidence={
                    "mcp_method": method,
                    "mcp_params": params,
                    "phase": "pre_call",
                },
            )
            
            self.egress_engine.emit(event)
            return step_id
        
        except Exception:
            # Egress emission must not break MCP flow
            return None
    
    def emit_post_call(
        self,
        method: str,
        result: Any,
        run_id: str,
        step_id: str,
        duration_ms: float,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit post-call egress event with enriched evidence
        
        Args:
            method: MCP method name
            result: Call result
            run_id: Run ID
            step_id: Step ID
            duration_ms: Call duration
            error: Error if failed
        """
        if not self.egress_engine:
            return
        
        try:
            egress_type, action, target = self._infer_egress_info(method, {})
            
            event = EgressEvent(
                egress=egress_type,
                action=action,
                target=target,
                run_id=run_id,
                step_id=step_id,
                tool_name=method,
                decision=PolicyDecision.ALLOW if not error else PolicyDecision.DENY,
                risk=RiskLevel.LOW if not error else RiskLevel.MEDIUM,
                evidence={
                    "mcp_method": method,
                    "mcp_result": result,
                    "duration_ms": duration_ms,
                    "phase": "post_call",
                    "error": error,
                    "tool_output": result,  # For UsageEnricher
                },
            )
            
            self.egress_engine.emit(event)
        
        except Exception:
            # Egress emission must not break MCP flow
            pass
    
    def _infer_egress_info(
        self,
        method: str,
        params: Optional[Dict[str, Any]],
    ) -> tuple[EgressType, str, str]:
        """
        Infer egress type from MCP method
        
        Returns:
            Tuple of (EgressType, action, target)
        """
        # Map common MCP methods to egress types
        if method.startswith("tools/call"):
            tool_name = params.get("name", "unknown") if params else "unknown"
            
            # Heuristic: infer from tool name
            if any(kw in tool_name.lower() for kw in ["file", "read", "write", "fs"]):
                return EgressType.FS, f"mcp.tools/call.{tool_name}", "filesystem"
            elif any(kw in tool_name.lower() for kw in ["http", "fetch", "api", "request"]):
                return EgressType.NETWORK, f"mcp.tools/call.{tool_name}", "network"
            elif any(kw in tool_name.lower() for kw in ["exec", "run", "command", "shell"]):
                return EgressType.EXEC, f"mcp.tools/call.{tool_name}", "subprocess"
            else:
                # Default: treat as network (most MCP tools are API calls)
                return EgressType.NETWORK, f"mcp.tools/call.{tool_name}", "mcp_tool"
        
        elif method.startswith("resources/"):
            return EgressType.NETWORK, f"mcp.{method}", "mcp_resource"
        
        elif method.startswith("prompts/"):
            return EgressType.NETWORK, f"mcp.{method}", "mcp_prompt"
        
        else:
            # Default: network egress
            return EgressType.NETWORK, f"mcp.{method}", "mcp_method"


__all__ = ["McpEgressIntegration"]
