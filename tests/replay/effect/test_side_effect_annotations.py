# tests/replay/effect/test_side_effect_annotations.py
"""
Side-Effect Annotations Tests - test replay annotation generation from crossings

Tests that side-effect crossings are correctly converted to replay annotations:
- Crossing can be converted to annotation
- Annotation has correct structure (badge, severity, summary, etc.)
- Annotation can be serialized to dict

Note: This tests the annotation conversion logic.
For integration tests (gate blocking, two-phase tracking), see test_side_effect_integration.py
"""

from failcore.core.replay.annotations import SideEffectCrossingAnnotation
from failcore.core.guards.effects.side_effect_auditor import CrossingRecord
from failcore.core.guards.effects.side_effects import SideEffectType
from failcore.core.config.boundaries import get_boundary


def build_test_crossing_record() -> CrossingRecord:
    """Build a test crossing record"""
    boundary = get_boundary("read_only")
    
    return CrossingRecord(
        crossing_type=SideEffectType.FS_WRITE,
        boundary=boundary,
        step_seq=1,
        ts="2024-01-01T00:00:00Z",
        target="/tmp/output.txt",
        tool="write_file",
        step_id="step_1",
        observed_category="FILESYSTEM",
        allowed_categories=["FILESYSTEM"],  # read_only allows FILESYSTEM but blocks write
    )


def test_annotation_from_crossing_record():
    """
    Test: SideEffectCrossingAnnotation.from_crossing_record creates annotation correctly
    
    Scenario: Convert crossing record to annotation
    Expected: Annotation has correct structure
    """
    crossing = build_test_crossing_record()
    
    # Create annotation from crossing record
    annotation = SideEffectCrossingAnnotation.from_crossing_record(crossing)
    
    # Verify annotation structure
    assert annotation.badge == "CROSSING", "badge should be CROSSING"
    assert annotation.severity == "high", "severity should be high"
    assert annotation.crossing_type == "filesystem.write", "crossing_type should be filesystem.write"
    assert annotation.target == "/tmp/output.txt", "target should match"
    assert annotation.tool == "write_file", "tool should match"
    assert annotation.step_seq == 1, "step_seq should match"
    assert "FILESYSTEM" in annotation.allowed_categories, "allowed_categories should contain FILESYSTEM"
    assert "Boundary crossed" in annotation.summary, "summary should mention boundary crossed"
    assert "filesystem.write" in annotation.summary, "summary should mention crossing type"
    assert "/tmp/output.txt" in annotation.summary, "summary should mention target"


def test_annotation_to_dict():
    """
    Test: Annotation can be serialized to dict
    
    Scenario: Convert annotation to dictionary
    Expected: Dictionary has all required fields
    """
    crossing = build_test_crossing_record()
    annotation = SideEffectCrossingAnnotation.from_crossing_record(crossing)
    
    # Convert to dict
    annotation_dict = annotation.to_dict()
    
    # Verify dictionary structure
    assert annotation_dict["badge"] == "CROSSING", "badge should serialize correctly"
    assert annotation_dict["severity"] == "high", "severity should serialize correctly"
    assert annotation_dict["crossing_type"] == "filesystem.write", "crossing_type should serialize correctly"
    assert annotation_dict["target"] == "/tmp/output.txt", "target should serialize correctly"
    assert annotation_dict["tool"] == "write_file", "tool should serialize correctly"
    assert annotation_dict["step_seq"] == 1, "step_seq should serialize correctly"
    assert isinstance(annotation_dict["allowed_categories"], list), "allowed_categories should be a list"
    assert "FILESYSTEM" in annotation_dict["allowed_categories"], "allowed_categories should contain FILESYSTEM"
    assert "summary" in annotation_dict, "summary should be in dict"
    assert len(annotation_dict["summary"]) > 0, "summary should not be empty"


def test_annotation_summary_format():
    """
    Test: Annotation summary has correct format
    
    Scenario: Summary includes crossing type, target, and allowed categories
    Expected: Summary is human-readable and informative
    """
    # Test with target
    crossing = build_test_crossing_record()
    annotation = SideEffectCrossingAnnotation.from_crossing_record(crossing)
    
    summary = annotation.summary
    assert "Boundary crossed" in summary, "summary should mention boundary crossed"
    assert "filesystem.write" in summary, "summary should mention crossing type"
    assert "/tmp/output.txt" in summary, "summary should mention target"
    assert "Allowed" in summary, "summary should mention allowed categories"
    
    # Test without target
    crossing_no_target = CrossingRecord(
        crossing_type=SideEffectType.NET_EGRESS,
        boundary=get_boundary("strict"),
        step_seq=2,
        ts="2024-01-01T00:01:00Z",
        target=None,
        tool="http_request",
        step_id="step_2",
        observed_category="NETWORK",
        allowed_categories=[],
    )
    annotation_no_target = SideEffectCrossingAnnotation.from_crossing_record(crossing_no_target)
    
    summary_no_target = annotation_no_target.summary
    assert "Boundary crossed" in summary_no_target, "summary should mention boundary crossed"
    assert "network.egress" in summary_no_target, "summary should mention crossing type"
    assert "Allowed" in summary_no_target, "summary should mention allowed categories"


def test_annotation_multiple_crossings():
    """
    Test: Multiple crossings can be converted to annotations
    
    Scenario: Multiple crossing records
    Expected: Each crossing gets its own annotation
    """
    crossings = [
        CrossingRecord(
            crossing_type=SideEffectType.FS_WRITE,
            boundary=get_boundary("read_only"),
            step_seq=1,
            ts="2024-01-01T00:00:00Z",
            target="/tmp/output.txt",
            tool="write_file",
            step_id="step_1",
            observed_category="FILESYSTEM",
            allowed_categories=["FILESYSTEM"],
        ),
        CrossingRecord(
            crossing_type=SideEffectType.NET_EGRESS,
            boundary=get_boundary("read_only"),
            step_seq=2,
            ts="2024-01-01T00:01:00Z",
            target="https://example.com",
            tool="http_request",
            step_id="step_2",
            observed_category="NETWORK",
            allowed_categories=["FILESYSTEM"],
        ),
    ]
    
    # Convert all crossings to annotations
    annotations = [SideEffectCrossingAnnotation.from_crossing_record(c) for c in crossings]
    
    # Verify we have two annotations
    assert len(annotations) == 2, "Should have two annotations"
    
    # Verify first annotation
    assert annotations[0].crossing_type == "filesystem.write", "First annotation should be FS_WRITE"
    assert annotations[0].step_seq == 1, "First annotation step_seq should be 1"
    
    # Verify second annotation
    assert annotations[1].crossing_type == "network.egress", "Second annotation should be NET_EGRESS"
    assert annotations[1].step_seq == 2, "Second annotation step_seq should be 2"
