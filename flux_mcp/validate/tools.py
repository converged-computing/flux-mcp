import json
import sys
from typing import Annotated

import yaml
from flux.job.Jobspec import validate_jobspec
from rich.console import Console

# This will pretty print all exceptions in rich
from flux_mcp.validate.validate import Validator


def flux_validate_jobspec(content: Annotated[str, "Loaded jobspec"]):
    """
    Validate a batch.sh, jobspec.yaml, or jobspec.json.
    """
    errors = []
    jobspec = None

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


def flux_count_jobspec_resources(content: Annotated[str, "String value of jobspec"]):
    """
    Count job resources. This also assumes.
    """
    result = flux_validate_jobspec(content)
    if not result["valid"]:
        return {}
    jobspec = result["jobspec"]
    counts = {}
    if jobspec is not None:
        print(
            "The jobspec is valid! Here are the total resource"
            " counts per type requested by the provided jobspec:"
        )
        for res in jobspec.resource_walk():
            print(f"Type: {res[1]['type']}, count: {res[2]}")
            counts[res[1]["type"]] = res[2]
    return counts


def display_error(content, issue):
    """
    Displays a custom error message inside a red box.
    """
    console = Console(stderr=True)
    content = (
        f"[bold]Flux Batch Validation Failed:[/bold]\n[yellow]"
        + content
        + "[/yellow]\n\n[red]"
        + issue
        + "[/red]"
    )
    console.print(content)
