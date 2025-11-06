"""JSON schema for normalized output validation."""

NORMALIZED_SCHEMA = {
    "type": "object",
    "properties": {
        "video_id": {"type": "string"},
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "technique", "pattern", "use-case", "capability",
                            "integration", "anti-pattern", "component",
                            "troubleshooting", "configuration", "code-snippet"
                        ]
                    },
                    "name": {"type": "string", "minLength": 1, "maxLength": 80},
                    "summary": {"type": "string", "minLength": 1, "maxLength": 300},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["id", "type", "name", "summary", "confidence"],
                "additionalProperties": False
            }
        }
    },
    "required": ["video_id", "units"],
    "additionalProperties": False
}


def validate_normalized(data: dict) -> tuple[bool, list[str]]:
    """
    Validate normalized output against schema.
    
    Args:
        data: Dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    import jsonschema
    
    try:
        jsonschema.validate(instance=data, schema=NORMALIZED_SCHEMA)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [str(e)]
    except jsonschema.SchemaError as e:
        return False, [f"Schema error: {e}"]
