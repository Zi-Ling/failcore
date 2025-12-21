# failcore/cli/renderers/text.py
"""
Text renderer for Views - Plain text output (default, stable)
"""

from typing import Any
from ..views.replay_run import ReplayRunView, ReplayDecision
from ..views.replay_diff import ReplayDiffView
from ..views.trace_show import TraceShowView


class TextRenderer:
    """
    Plain text renderer for all view types
    
    This is the default, stable renderer that outputs clean,
    parseable text without dependencies on rich/colors/etc.
    """
    
    def render_replay_run(self, view: ReplayRunView) -> str:
        """Render ReplayRunView as plain text"""
        lines = []
        
        # Header
        lines.append("="*80)
        lines.append(f"Replay Run: {view.meta.mode}")
        lines.append("="*80)
        lines.append(f"Trace: {view.meta.trace_path}")
        if view.meta.run_id:
            lines.append(f"Run ID: {view.meta.run_id}")
        lines.append("")
        
        # Summary
        lines.append("Summary:")
        lines.append(f"  Total Steps: {view.summary.total_steps}")
        lines.append(f"  Hits: {view.summary.hits} ({view.summary.hit_rate})")
        lines.append(f"  Misses: {view.summary.misses} ({view.summary.miss_rate})")
        lines.append(f"  Diffs: {view.summary.diffs} ({view.summary.diff_rate})")
        if view.summary.policy_diffs > 0:
            lines.append(f"    Policy Diffs: {view.summary.policy_diffs}")
        if view.summary.output_diffs > 0:
            lines.append(f"    Output Diffs: {view.summary.output_diffs}")
        lines.append("")
        
        # Steps
        lines.append("Steps:")
        lines.append("-"*80)
        for step in view.steps:
            # Step header
            decision_marker = {
                ReplayDecision.HIT: "[HIT]",
                ReplayDecision.MISS: "[MISS]",
                ReplayDecision.SKIP: "[SKIP]",
                ReplayDecision.DIFF: "[DIFF]",
            }[step.replay_decision]
            
            lines.append(f"[{step.ordinal}] {step.step_id}")
            lines.append(f"    Tool: {step.tool}")
            lines.append(f"    Historical: {step.historical_status}")
            lines.append(f"    Replay: {decision_marker}")
            
            if step.replay_reason:
                lines.append(f"    Reason: {step.replay_reason}")
            
            if step.injected:
                lines.append(f"    Injected: Yes (output kind: {step.output_kind})")
            
            # Notes
            for note in step.notes:
                lines.append(f"    [{note.type}] {note.message}")
            
            lines.append("")
        
        # Footer
        if view.footer.next_action:
            lines.append("Next Action:")
            lines.append(f"  {view.footer.next_action}")
            lines.append("")
        
        if view.footer.hints:
            lines.append("Hints:")
            for hint in view.footer.hints:
                lines.append(f"  - {hint}")
            lines.append("")
        
        return "\n".join(lines)
    
    def render_replay_diff(self, view: ReplayDiffView) -> str:
        """Render ReplayDiffView as plain text"""
        lines = []
        
        # Header
        lines.append("="*80)
        lines.append("Replay Diff Analysis")
        lines.append("="*80)
        lines.append(f"Trace: {view.meta.trace_path}")
        lines.append(f"Compare: {view.meta.compare_target}")
        lines.append("")
        
        # Summary
        lines.append("Summary:")
        lines.append(f"  Total Steps: {view.summary.total_steps}")
        lines.append(f"  Policy Denied: {view.summary.policy_denied_count}")
        lines.append(f"  Policy Diffs: {view.summary.policy_diff_count}")
        lines.append(f"  Output Mismatches: {view.summary.output_mismatch_count}")
        lines.append(f"  Fingerprint Misses: {view.summary.fingerprint_miss_count}")
        lines.append("")
        
        # Policy denied steps
        if view.policy_denied_steps:
            lines.append("Policy Denied Steps:")
            for step in view.policy_denied_steps[:10]:
                rule = f" [{step.rule_id}]" if step.rule_id else ""
                lines.append(f"  {step.step_id:20s} {step.tool:20s}{rule}")
                lines.append(f"    Reason: {step.reason}")
            
            if len(view.policy_denied_steps) > 10:
                lines.append(f"  ... and {len(view.policy_denied_steps) - 10} more")
            lines.append("")
        
        # Output mismatch steps
        if view.output_mismatch_steps:
            lines.append("Output Mismatch Steps:")
            for step in view.output_mismatch_steps[:10]:
                lines.append(f"  {step.step_id:20s} {step.tool:20s}")
                lines.append(f"    Expected: {step.expected_kind}, Got: {step.observed_kind}")
                if step.sample:
                    lines.append(f"    Sample: {step.sample}")
            
            if len(view.output_mismatch_steps) > 10:
                lines.append(f"  ... and {len(view.output_mismatch_steps) - 10} more")
            lines.append("")
        
        # Counterfactual diffs
        if view.diffs:
            lines.append("Counterfactual Diffs:")
            for diff in view.diffs:
                lines.append(f"  [{diff.type}] {diff.step_id} ({diff.tool})")
                lines.append(f"    Before: {diff.before}")
                lines.append(f"    After: {diff.after}")
                if diff.reason:
                    lines.append(f"    Reason: {diff.reason}")
                lines.append("")
        
        return "\n".join(lines)
    
    def render_trace_show(self, view: TraceShowView) -> str:
        """Render TraceShowView as plain text"""
        lines = []
        
        # Header
        lines.append("="*80)
        lines.append("Trace Display")
        lines.append("="*80)
        lines.append(f"Trace: {view.meta.trace_path}")
        if view.meta.run_id:
            lines.append(f"Run ID: {view.meta.run_id}")
        lines.append("")
        
        # Summary
        lines.append("Summary:")
        lines.append(f"  Total Steps: {view.summary.total_steps}")
        lines.append(f"  OK: {view.summary.ok}")
        lines.append(f"  FAIL: {view.summary.fail}")
        lines.append(f"  BLOCKED: {view.summary.blocked}")
        lines.append(f"  Total Duration: {view.summary.total_duration_ms}ms")
        lines.append("")
        
        # Steps
        lines.append("Steps:")
        lines.append("-"*80)
        for step in view.steps:
            status_marker = {
                "OK": "[OK]",
                "FAIL": "[FAIL]",
                "BLOCKED": "[BLOCKED]",
            }.get(step.status, f"[{step.status}]")
            
            lines.append(f"[{step.ordinal}] {step.step_id}")
            lines.append(f"    Tool: {step.tool}")
            lines.append(f"    Status: {status_marker}")
            lines.append(f"    Duration: {step.duration_ms}ms")
            
            if step.error_code:
                lines.append(f"    Error: {step.error_code} - {step.error_message}")
            
            if step.output_summary:
                lines.append(f"    Output: {step.output_summary}")
            
            lines.append("")
        
        return "\n".join(lines)
