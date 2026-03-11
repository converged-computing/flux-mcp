import json
from typing import Annotated, Any, Dict, List

import yaml
from flux.job.Jobspec import validate_jobspec
from rich.console import Console

import flux_mcp.validate.prompts as prompts
from flux_mcp.validate.validate import Validator

# Define custom types for MCP agent schema clarity
AgentPromptResponse = Annotated[
    Dict[str, Any],
    "A dictionary containing a list of messages formatted for an LLM agent chat session.",
]
ValidationResult = Annotated[
    Dict[str, Any],
    "A structured result containing the 'jobspec' (str or object), a list of 'errors' (list of strings), and a 'valid' boolean status.",
]
ResourceAnalysisResult = Annotated[
    Dict[str, Any],
    "A dictionary containing validation status, errors, the jobspec object, a counts mapping, and an optional status message.",
]


def flux_validate_jobspec_persona(
    script: Annotated[str, "Batch script or job specification"],
) -> AgentPromptResponse:
    """
    Generates a specialized system/user prompt to guide an LLM agent in
    validating and improving a Flux job specification.

    This function wraps the provided script in a specific persona context,
    instructing the agent to look for common HPC mistakes, resource
    under-utilization, or syntax errors in the job description.

    Args:
        script: The raw text of the batch script (with #FLUX directives) or
            the jobspec (JSON/YAML) that the agent needs to analyze.

    Returns:
        A dictionary structured for an LLM chat interface, containing a
        list of messages that establish the validation task and persona.
    """
    prompt_text = prompts.get_validation_text(script)
    return {"messages": [{"role": "user", "content": {"type": "text", "text": prompt_text}}]}


def flux_validate_batch_jobspec(
    content: Annotated[str, "Loaded jobspec content string"],
) -> ValidationResult:
    """
    Performs a deep-dive validation of a shell-based Flux batch script.

    Unlike general jobspec validation, this function specifically targets shell scripts
    containing '#FLUX' header directives. It uses the Validator service to check
    for valid flag usage, shell syntax compatibility, and RFC compliance within
    the script headers.

    Args:
        content: The raw string content of the shell script to be validated.

    Returns:
        A dictionary containing:
            - 'valid' (bool): True if no header or syntax errors were found.
            - 'errors' (list): A list of strings detailing every identified
              validation failure.
            - 'jobspec' (str): The original content string, returned to maintain
              a record of the checked input.
    """
    errors = []
    validator = Validator("batch")
    try:
        # Setting fail fast to False means we will get ALL errors at once
        validator.validate(content, fail_fast=False)
    except Exception as e:
        display_error(content, str(e))
        errors.append(str(e))

    return {"jobspec": content, "errors": errors, "valid": not errors}


def internal_validate(content):
    """
    Internal validate of a jobspec, returns the Flux canonical jobspec
    """
    errors = []
    jobspec = None

    # Cut out early if the content is empty
    if not content.strip():
        errors.append("The provided jobspec is an empty string.")
        return {"jobspec": jobspec, "errors": errors, "valid": not errors}
    try:
        yaml_content = yaml.safe_load(content)
        json_content = json.dumps(yaml_content)
    except Exception as e:
        errors.append(str(e))
        return {"jobspec": jobspec, "errors": errors, "valid": not errors}

    if not isinstance(yaml_content, dict):
        validator = Validator("batch")
        try:
            # Setting fail fast to False means we will get ALL errors at once
            validator.validate(content, fail_fast=False)
        except Exception as e:
            display_error(content, str(e))
            errors.append(str(e))
    else:
        try:
            _, jobspec = validate_jobspec(json_content)
        except Exception as e:
            display_error(content, str(e))
            errors.append(str(e))
    return {"jobspec": jobspec, "errors": errors, "valid": not errors}


def flux_validate_jobspec(
    content: Annotated[str, "Loaded jobspec content string (YAML, JSON, or script)"],
) -> ValidationResult:
    """
    Validates the provided content as a Flux job specification or batch script.

    This function serves as a universal entry point for checking the syntax and
    structural correctness of various Flux job submission formats. It supports:
    1. Structured Jobspecs: Native Flux JSON or YAML files (checked via RFC compliance).
    2. Batch Scripts: Shell scripts containing #FLUX directives (checked via the 'batch' validator).

    The function intelligently determines the format: if the content can be parsed as a
    JSON/YAML dictionary, it uses native Flux validation logic. Otherwise, it treats
    the content as a shell-based batch script.

    Args:
        content: The raw string content to be validated (JSON, YAML, or Shell script).

    Returns:
        A dictionary containing:
            - 'valid' (bool): True if the content passed all validation checks.
            - 'errors' (list): A list of strings describing encountered issues. Empty if valid.
            - 'jobspec' (object or None): If structured data was provided, this returns
              the internal Flux Jobspec object for further analysis.
    """
    result = internal_validate(content)

    # Ensure if we have a flux jobspec type, we return to dict
    try:
        result["jobspec"] = result["jobspec"].jobspec
    except:
        pass
    return result


def flux_count_jobspec_resources(
    content: Annotated[str, "String value of the jobspec to analyze"],
) -> ResourceAnalysisResult:
    """
    Analyzes a jobspec string to validate its structure and count total requested resources.

    This function first attempts to validate the provided content (JSON, YAML, or script).
    If valid, it traverses the resource graph to aggregate total counts for each resource
    type (e.g., cores, GPUs, slots).

    Args:
        content: The raw string content of the jobspec or batch script to be analyzed.

    Returns:
        A dictionary containing:
            - 'valid' (bool): True if the jobspec was successfully parsed and validated.
            - 'jobspec' (object or None): The internal Flux Jobspec object if valid.
            - 'errors' (list): A list of strings describing any validation or parsing failures.
            - 'counts' (dict): A mapping of resource types to their total integer counts.
            - 'message' (str, optional): A descriptive message explaining why counting failed.
    """
    # We need to get a jobspecV1c back here
    result = internal_validate(content)
    result["counts"] = {}

    if not result["valid"]:
        result["message"] = "The jobspec is not valid and resources cannot be counted"
        return result

    jobspec = result["jobspec"]
    counts = {}

    # resource_walk returns (depth, metadata, count) for each node in the resource graph
    for res in jobspec.resource_walk():
        res_type = res[1].get("type", "unknown")
        print(type(res_type))
        res_count = res[2]
        print(type(res_count))
        print(f"Type: {res_type}, count: {res_count}")
        counts[res_type] = res_count

    result["counts"] = counts
    print(counts)
    # Turn it back into dictionary
    result["jobspec"] = jobspec.jobspec
    print(result)
    return result


def display_error(content: str, issue: str) -> None:
    """
    Displays a custom error message inside a red box in the terminal (stderr).
    """
    console = Console(stderr=True)
    content_display = (
        f"[bold]Flux Batch Validation Failed:[/bold]\n[yellow]"
        + content
        + "[/yellow]\n\n[red]"
        + issue
        + "[/red]"
    )
    console.print(content_display)
