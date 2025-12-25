PERSONA = "You are a job validation expert."

CONTEXT = "We need to validate a job specification for correctness."


def get_validation_text(script):
    """
    Get prompt text for an initial build.
    """
    return f"""
### PERSONA
{PERSONA}

### CONTEXT
{CONTEXT}

### GOAL
I need to validate if the following job specification is correct:

```
{script}
```

### REQUIREMENTS & CONSTRAINTS
You MUST return a JSON structure with fields for 'valid' (bool) and a list of string 'reasons'.

### INSTRUCTIONS
1. Analyze the provided script above.
2. Use a validation tool (if one is available) OR use your knowledge.
2. Return a json structure with 'valid' and 'reasons' (if not valid)
"""
