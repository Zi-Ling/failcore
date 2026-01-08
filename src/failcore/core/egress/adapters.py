# failcore/core/egress/adapters.py
"""
Adapters for integrating EgressEngine with existing systems

Provides backward-compatible wrappers for existing trace/cost infrastructure.
"""

from typing import Any, Optional
from failcore.core.trace.recorder import TraceRecorder
from .engine import EgressEngine
from .types import EgressEvent, EgressType, PolicyDecision, RiskLevel


class EgressTraceRecorder(TraceRecorder):
    """
    TraceRecorder adapter that routes through EgressEngine
    
    Provides backward compatibility with existing code while
    enabling unified egress event processing.
    
    Design:
    - Implements TraceRecorder interface
    - Converts TraceEvent → EgressEvent (where applicable)
    - Falls back to direct trace write for non-egress events
    """
    
    def __init__(
        self,
        primary_recorder: TraceRecorder,
        egress_engine: Optional[EgressEngine] = None,
    ):
        self.primary_recorder = primary_recorder
        self.egress_engine = egress_engine
    
    def record(self, event: Any) -> None:
        """
        Record trace event
        
        If event is egress-compatible and engine is available,
        route through EgressEngine. Otherwise, use primary recorder.
        
        Args:
            event: TraceEvent to record
        """
        # Always record to primary (authoritative trace)
        self.primary_recorder.record(event)
        
        # Additionally emit through egress engine if applicable
        if self.egress_engine:
            egress_event = self._try_convert_to_egress(event)
            if egress_event:
                try:
                    self.egress_engine.emit(egress_event)
                except Exception:
                    # Egress emission failures must not block trace write
                    pass
    
    def _try_convert_to_egress(self, event: Any) -> Optional[EgressEvent]:
        """
        Try to convert TraceEvent to EgressEvent
        
        Only certain event types map to egress:
        - SIDE_EFFECT_APPLIED → FS/NETWORK/EXEC egress
        - Cost-related events → COST egress
        
        Returns:
            EgressEvent if convertible, None otherwise
        """
        if not hasattr(event, 'to_dict'):
            return None
        
        event_dict = event.to_dict()
        event_data = event_dict.get('event', {})
        event_type = event_data.get('type')
        
        # Convert SIDE_EFFECT_APPLIED events
        if event_type == 'SIDE_EFFECT_APPLIED':
            return self._convert_side_effect(event_dict)
        
        # Other event types don't map to egress
        return None
    
    def _convert_side_effect(self, event_dict: dict) -> Optional[EgressEvent]:
        """Convert SIDE_EFFECT_APPLIED event to EgressEvent"""
        event_data = event_dict.get('event', {})
        step_data = event_data.get('step', {})
        side_effect_data = event_data.get('data', {}).get('side_effect', {})
        
        # Extract fields
        se_type = side_effect_data.get('type', '')
        target = side_effect_data.get('target', '')
        tool_name = side_effect_data.get('tool', '')
        step_id = side_effect_data.get('step_id', '')
        
        # Map side_effect type to egress type
        egress_type_map = {
            'filesystem.read': EgressType.FS,
            'filesystem.write': EgressType.FS,
            'filesystem.delete': EgressType.FS,
            'network.egress': EgressType.NETWORK,
            'network.ingress': EgressType.NETWORK,
            'exec.subprocess': EgressType.EXEC,
            'exec.shell': EgressType.EXEC,
        }
        
        egress_type = egress_type_map.get(se_type)
        if not egress_type:
            return None
        
        # Extract run context
        run_data = event_dict.get('run', {})
        run_id = run_data.get('run_id', '')
        
        return EgressEvent(
            egress=egress_type,
            action=se_type,
            target=target or 'unknown',
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            decision=PolicyDecision.ALLOW,  # Already allowed if applied
            risk=RiskLevel.LOW,
            evidence={'side_effect': side_effect_data},
        )
    
    def next_seq(self) -> int:
        """Delegate to primary recorder"""
        if hasattr(self.primary_recorder, 'next_seq'):
            return self.primary_recorder.next_seq()
        return 0
    
    def close(self) -> None:
        """Close both primary and egress engine"""
        if hasattr(self.primary_recorder, 'close'):
            self.primary_recorder.close()
        if self.egress_engine:
            self.egress_engine.close()


__all__ = ["EgressTraceRecorder"]
