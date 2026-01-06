# failcore/core/replay/execution.py
"""
Replay Execution Hook - pure decision logic without trace dependencies

This module provides ReplayExecutionHook which only makes replay decisions
without recording trace events. Event recording is handled by the calling stage.

Design principle (adopts suggestion 2):
- Hook makes decisions, Stage records events
- Replay module does not depend on trace schema
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .replayer import Replayer, ReplayResult, ReplayHitType
from .fingerprint import compute_fingerprint


@dataclass
class ReplayDecision:
    """
    Replay decision result (no trace events)
    
    Contains all information needed by the calling stage to:
    1. Decide whether to continue execution
    2. Record appropriate trace events
    3. Inject historical output if applicable
    """
    hit_type: ReplayHitType
    injected: bool
    step_result: Optional[Any] = None  # StepResult if injected
    match_info: Optional[Any] = None  # MatchInfo from matcher
    diff_details: Optional[Dict[str, Any]] = None
    fingerprint: Dict[str, Any] = None  # Fingerprint for event recording
    message: Optional[str] = None


class ReplayExecutionHook:
    """
    Pure replay decision logic (no trace recording)
    
    This hook only makes decisions about whether to replay a step.
    It does NOT record trace events - that's the responsibility of the calling stage.
    
    Design (adopts suggestion 2):
    - Hook returns ReplayDecision
    - Stage (replay.py) records events based on decision
    - Replay module stays independent of trace schema
    """
    
    def __init__(self, replayer: Optional[Replayer]):
        """
        Initialize hook
        
        Args:
            replayer: Replayer instance (None if replay disabled)
        """
        self.replayer = replayer
    
    def execute(
        self,
        step_id: str,
        tool: str,
        params: Dict[str, Any],
        policy_result: Optional[Tuple[bool, str]] = None,
    ) -> Optional[ReplayDecision]:
        """
        Execute replay decision logic
        
        Args:
            step_id: Current step ID
            tool: Tool name
            params: Tool parameters
            policy_result: Optional (allowed, reason) tuple from policy check
        
        Returns:
            ReplayDecision if replay is enabled, None otherwise
        
        Note:
            - Returns decision only, does NOT record events
            - Calling stage should record events based on decision
        """
        if not self.replayer:
            return None
        
        # Compute fingerprint
        fingerprint = compute_fingerprint(tool, params)
        
        # Call replayer
        replay_result = self.replayer.replay_step(
            step_id=step_id,
            tool=tool,
            params=params,
            fingerprint=fingerprint,
            current_policy_decision=policy_result,
        )
        
        # Convert ReplayResult to ReplayDecision
        return ReplayDecision(
            hit_type=replay_result.hit_type,
            injected=replay_result.injected,
            step_result=replay_result.step_result,
            match_info=replay_result.match_info,
            diff_details=replay_result.diff_details,
            fingerprint=fingerprint,
            message=replay_result.message,
        )


__all__ = [
    "ReplayDecision",
    "ReplayExecutionHook",
]
