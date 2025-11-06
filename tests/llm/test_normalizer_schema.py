"""Tests for normalizer schema validation."""

import pytest
from youtube_processor.llm.normalizer_schema import validate_normalized


def test_valid_schema():
    """Test that valid output passes schema validation."""
    valid_output = {
        "video_id": "test123",
        "units": [{
            "id": "unit-0-450",
            "type": "technique",
            "name": "Test Technique",
            "summary": "A test summary that is concise",
            "confidence": 0.85
        }]
    }
    is_valid, errors = validate_normalized(valid_output)
    assert is_valid, f"Expected valid, got errors: {errors}"
    assert errors == []


def test_invalid_missing_required_field():
    """Test that missing required field fails validation."""
    invalid_output = {
        "video_id": "test123",
        "units": [{
            "id": "unit-0-450",
            "type": "technique"
            # Missing name, summary, confidence
        }]
    }
    is_valid, errors = validate_normalized(invalid_output)
    assert not is_valid, "Expected invalid due to missing fields"
    assert len(errors) > 0


def test_invalid_wrong_type_enum():
    """Test that invalid type enum fails validation."""
    invalid_output = {
        "video_id": "test123",
        "units": [{
            "id": "unit-0-450",
            "type": "invalid-type",  # Not in taxonomy
            "name": "Test",
            "summary": "Test summary",
            "confidence": 0.85
        }]
    }
    is_valid, errors = validate_normalized(invalid_output)
    assert not is_valid, "Expected invalid due to wrong type"


def test_invalid_confidence_out_of_range():
    """Test that confidence outside [0,1] fails validation."""
    invalid_output = {
        "video_id": "test123",
        "units": [{
            "id": "unit-0-450",
            "type": "technique",
            "name": "Test",
            "summary": "Test summary",
            "confidence": 1.5  # Outside valid range
        }]
    }
    is_valid, errors = validate_normalized(invalid_output)
    assert not is_valid, "Expected invalid due to confidence > 1.0"


def test_invalid_additional_properties():
    """Test that additional properties fail validation."""
    invalid_output = {
        "video_id": "test123",
        "units": [{
            "id": "unit-0-450",
            "type": "technique",
            "name": "Test",
            "summary": "Test summary",
            "confidence": 0.85,
            "extra_field": "not allowed"  # Additional property
        }]
    }
    is_valid, errors = validate_normalized(invalid_output)
    assert not is_valid, "Expected invalid due to additional property"


def test_valid_multiple_units():
    """Test that multiple valid units pass validation."""
    valid_output = {
        "video_id": "test123",
        "units": [
            {
                "id": "unit-0-450",
                "type": "technique",
                "name": "First Technique",
                "summary": "First summary",
                "confidence": 0.85
            },
            {
                "id": "unit-450-900",
                "type": "pattern",
                "name": "Second Pattern",
                "summary": "Second summary",
                "confidence": 0.92
            }
        ]
    }
    is_valid, errors = validate_normalized(valid_output)
    assert is_valid, f"Expected valid, got errors: {errors}"
