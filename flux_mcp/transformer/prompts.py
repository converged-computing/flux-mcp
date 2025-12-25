PERSONA = "You are a job specification generation expert."

CONTEXT = "We need to convert between workload manager job specification formats."


def get_transform_text(script, to_manager, from_manager, fmt="batch"):
    """
    Get prompt text for an initial build.
    """
    return f"""
### PERSONA
{PERSONA}

### CONTEXT
{CONTEXT}

### GOAL
I need to convert the provided job specification from '{from_manager}' to '{to_manager}'.
The desired output format is a '{fmt}' script.

### REQUIREMENTS & CONSTRAINTS
You MUST not make up directives that do not exist.
You MUST preserve as many options as possible from the original.

### INSTRUCTIONS
1. Analyze the provided script below.
2. Write a new script and return in a json structure with a "jobspec"

{script}
"""
