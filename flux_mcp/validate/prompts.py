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
You MUST return a JSON structure with fields for 'valid' (bool) and a list of string 'reasons'. You MAY optionally add a field `issues` with a list of debugging or critique of any code.

### INSTRUCTIONS
1. Analyze the provided script above.
2. Use a validation tool (if one is available) OR use your knowledge.
3. Determine validity based on the resource section ONLY
4. The 'reasons' should ONLY be specific to resources
5. If the script includes problematic code, please include in 'issues'
6. Return a json structure with 'valid' and 'reasons' (if not valid) and 'issues'
"""
