from typing import Annotated, Optional

import flux_mcp.transformer.prompts as prompts

from .registry import detect_transformer, get_transformer


def transform_jobspec_prompt(script: str, from_manager: str, to_manager: str, fmt: str = "batch"):
    """
    Generate a prompt to transform FROM a particular workload manager TO a particular workload manager.
    A 'fmt' should be the jobspec format, where jobspec is the refererring to the Flux canonical JSON/YAML
    representation, and batch is a typical batch script.

    Arguments
    =========
    script (str): The batch or job specification to convert.
    from_manager (str): The name of the manager to convert FROM.
    to_manager (str): The name of the job manager to convert TO.
    fmt (str): one of "batch" or "jobspec" for a Flux canonical jobspec (in json)
    """
    prompt_text = prompts.get_transform_text(script, to_manager, from_manager, fmt="batch")
    return {"messages": [{"role": "user", "content": {"type": "text", "text": prompt_text}}]}


def transform_jobspec(batch_job: str, to_format: str, from_format: Optional[str] = None):
    """
    Convert a batch jobspec from one format to another
    """

    # If no from transformer defined, try to detect
    try:
        from_format = from_format or detect_transformer(batch_job)
    except Exception as e:
        return {"status": "FAILURE", "error": str(e), "jobspec": None}

    # We are always converting to Flux from whatever
    try:
        from_transformer = get_transformer(from_format)
        to_transformer = get_transformer(to_format)
    except Exception as e:
        return {"status": "FAILURE", "error": str(e), "jobspec": None}

    try:
        normalized_jobspec = from_transformer.parse(batch_job)
        converted_jobspec = to_transformer.convert(normalized_jobspec)

    except Exception as e:
        return {"status": "FAILURE", "error": str(e), "jobspec": None}
    return {"status": "SUCCESS", "error": None, "jobspec": converted_jobspec}
