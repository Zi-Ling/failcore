# tests/audit/test_side_effect_boundary.py
"""
Side-Effect Boundary Tests - test deterministic boundary crossing detection

Tests three key scenarios:
1. Boundary-in side-effect → no crossing
2. Boundary-out side-effect → crossing + BLOCK
3. Crossing detection is deterministic (no randomness, no ML)
"""

import pytest

from failcore.core.audit.side_effect_auditor import SideEffectAuditor, CrossingRecord
from failcore.core.audit.boundary import SideEffectBoundary
from failcore.core.audit.side_effects import SideEffectType, SideEffectCategory
from failcore.core.config.boundaries import get_boundary


def test_boundary_allows_side_effect():
    """
    Test: Side-effect within boundary → no crossing
    
    Scenario: Filesystem read is allowed by "read_only" boundary
    Expected: No crossing detected
    """
    # Get read_only boundary (allows FILESYSTEM read only)
    boundary = get_boundary("read_only")
    auditor = SideEffectAuditor(boundary)
    
    # Check filesystem read (should be allowed)
    crossing = auditor.check_crossing(SideEffectType.FS_READ)
    assert not crossing, "FS_READ should be allowed by read_only boundary"
    
    # Check filesystem write (should be blocked)
    crossing = auditor.check_crossing(SideEffectType.FS_WRITE)
    assert crossing, "FS_WRITE should be blocked by read_only boundary"


def test_boundary_blocks_side_effect():
    """
    Test: Side-effect outside boundary → crossing + BLOCK
    
    Scenario: Filesystem write is blocked by "read_only" boundary
    Expected: Crossing detected
    """
    # Get read_only boundary (allows FILESYSTEM read only)
    boundary = get_boundary("read_only")
    auditor = SideEffectAuditor(boundary)
    
    # Check filesystem write (should be blocked)
    crossing = auditor.check_crossing(SideEffectType.FS_WRITE)
    assert crossing, "FS_WRITE should be blocked by read_only boundary"
    
    # Check filesystem delete (should be blocked)
    crossing = auditor.check_crossing(SideEffectType.FS_DELETE)
    assert crossing, "FS_DELETE should be blocked by read_only boundary"


def test_strict_boundary_blocks_most_side_effects():
    """
    Test: Strict boundary blocks most side-effects (only allows FS_READ)
    
    Scenario: "strict" boundary only allows FS_READ, blocks everything else
    Expected: Only FS_READ is allowed, all others are blocked
    """
    # Get strict boundary (only allows FS_READ)
    boundary = get_boundary("strict")
    auditor = SideEffectAuditor(boundary)
    
    # FS_READ should be allowed (it's explicitly allowed)
    assert not auditor.check_crossing(SideEffectType.FS_READ), "FS_READ should be allowed by strict boundary"
    
    # All other side-effects should be blocked
    assert auditor.check_crossing(SideEffectType.FS_WRITE), "FS_WRITE should be blocked by strict boundary"
    assert auditor.check_crossing(SideEffectType.FS_DELETE), "FS_DELETE should be blocked by strict boundary"
    assert auditor.check_crossing(SideEffectType.NET_EGRESS), "NET_EGRESS should be blocked by strict boundary"
    assert auditor.check_crossing(SideEffectType.EXEC_COMMAND), "EXEC_COMMAND should be blocked by strict boundary"


def test_permissive_boundary_allows_filesystem_and_network():
    """
    Test: Permissive boundary allows filesystem and network, blocks exec
    
    Scenario: "permissive" boundary allows FS_READ, FS_WRITE, NET_EGRESS, but blocks EXEC
    Expected: Filesystem and network operations are allowed, exec is blocked
    """
    # Get permissive boundary (allows filesystem and network, blocks exec)
    boundary = get_boundary("permissive")
    auditor = SideEffectAuditor(boundary)
    
    # Filesystem operations should be allowed
    assert not auditor.check_crossing(SideEffectType.FS_READ), "FS_READ should be allowed by permissive boundary"
    assert not auditor.check_crossing(SideEffectType.FS_WRITE), "FS_WRITE should be allowed by permissive boundary"
    
    # Network operations should be allowed
    assert not auditor.check_crossing(SideEffectType.NET_EGRESS), "NET_EGRESS should be allowed by permissive boundary"
    
    # Exec operations should be blocked
    assert auditor.check_crossing(SideEffectType.EXEC_COMMAND), "EXEC_COMMAND should be blocked by permissive boundary"
    assert auditor.check_crossing(SideEffectType.EXEC_SUBPROCESS), "EXEC_SUBPROCESS should be blocked by permissive boundary"


def test_detect_crossings_from_events():
    """
    Test: detect_crossings returns list of crossing records
    
    Scenario: Multiple side-effect events, some within boundary, some outside
    Expected: Only boundary-crossing events are returned
    """
    from failcore.core.executor.side_effect_probe import SideEffectEvent
    
    # Get read_only boundary
    boundary = get_boundary("read_only")
    auditor = SideEffectAuditor(boundary)
    
    # Create side-effect events
    events = [
        SideEffectEvent(
            type=SideEffectType.FS_READ,
            target="/tmp/test.txt",
            tool="read_file",
            step_id="step_1",
        ),
        SideEffectEvent(
            type=SideEffectType.FS_WRITE,
            target="/tmp/output.txt",
            tool="write_file",
            step_id="step_2",
        ),
        SideEffectEvent(
            type=SideEffectType.FS_READ,
            target="/tmp/test2.txt",
            tool="read_file",
            step_id="step_3",
        ),
    ]
    
    # Detect crossings
    crossings = auditor.detect_crossings(events)
    
    # Should only detect FS_WRITE as crossing (FS_READ is allowed)
    assert len(crossings) == 1, "Should detect exactly one crossing"
    assert crossings[0].crossing_type == SideEffectType.FS_WRITE, "Crossing should be FS_WRITE"
    assert crossings[0].tool == "write_file", "Crossing tool should be write_file"
    assert crossings[0].target == "/tmp/output.txt", "Crossing target should be /tmp/output.txt"


def test_crossing_record_structure():
    """
    Test: CrossingRecord has correct structure
    
    Scenario: Crossing record is created correctly
    Expected: All fields are populated correctly
    """
    from failcore.core.executor.side_effect_probe import SideEffectEvent
    
    # Get read_only boundary
    boundary = get_boundary("read_only")
    auditor = SideEffectAuditor(boundary)
    
    # Create side-effect event that will cross boundary
    event = SideEffectEvent(
        type=SideEffectType.FS_WRITE,
        target="/tmp/output.txt",
        tool="write_file",
        step_id="step_1",
    )
    
    # Detect crossings
    crossings = auditor.detect_crossings([event])
    
    # Verify crossing record structure
    assert len(crossings) == 1, "Should detect exactly one crossing"
    crossing = crossings[0]
    
    assert crossing.crossing_type == SideEffectType.FS_WRITE, "crossing_type should be FS_WRITE"
    assert crossing.boundary == boundary, "boundary should match"
    assert crossing.target == "/tmp/output.txt", "target should match"
    assert crossing.tool == "write_file", "tool should match"
    assert crossing.step_id == "step_1", "step_id should match"
    # observed_category is lowercase (e.g., "filesystem")
    assert crossing.observed_category.lower() == "filesystem", f"observed_category should be filesystem (got {crossing.observed_category})"
    # allowed_categories contains category values (which are lowercase)
    assert any("filesystem" in cat.lower() for cat in crossing.allowed_categories), f"FILESYSTEM should be in allowed_categories (got {crossing.allowed_categories})"
    
    # Verify to_dict works
    crossing_dict = crossing.to_dict()
    assert crossing_dict["crossing_type"] == "filesystem.write", "crossing_type should serialize correctly"
    assert crossing_dict["target"] == "/tmp/output.txt", "target should serialize correctly"
    assert crossing_dict["tool"] == "write_file", "tool should serialize correctly"
