from typing import Annotated, Any, Dict, List, Optional

import flux_mcp.transformer.prompts as prompts

from .registry import detect_transformer, get_transformer

AgentPromptResponse = Annotated[
    Dict[str, Any],
    "A dictionary containing a list of messages formatted for an LLM agent chat session.",
]

TransformationResult = Annotated[
    Dict[str, Any],
    "A structured result containing the 'status' (SUCCESS/FAILURE), 'error' (str or None), and the converted 'jobspec' string.",
]


def transform_jobspec_persona(
    script: Annotated[str, "The batch script or job specification content to be converted."],
    from_manager: Annotated[
        str, "The name of the workload manager to convert FROM (e.g., 'slurm', 'lsf')."
    ],
    to_manager: Annotated[str, "The name of the workload manager to convert TO (e.g., 'flux')."],
    fmt: Annotated[
        str,
        "The output format: 'batch' for a shell script with directives, or 'jobspec' for a canonical Flux JSON/YAML.",
    ] = "batch",
) -> AgentPromptResponse:
    """
    Generates a specialized prompt to guide an LLM agent in transforming a job
    specification from one workload manager format to another.

    This is useful for preparing instructions that help an agent understand how
    to map resource requests (like nodes, tasks, and partitions) between
    different scheduler syntaxes.

    Args:
        script: The raw text of the batch script or job specification to convert.
        from_manager: The name of the manager to convert FROM.
        to_manager: The name of the job manager to convert TO.
        fmt: The desired format of the conversion; defaults to 'batch'.

    Returns:
        A dictionary structured for an LLM chat interface, established with the
        transformation task and context.
    """
    prompt_text = prompts.get_transform_text(script, to_manager, from_manager, fmt="batch")
    return {"messages": [{"role": "user", "content": {"type": "text", "text": prompt_text}}]}


def transform_jobspec(
    batch_job: Annotated[str, "The raw batch job script or jobspec content to convert."],
    to_format: Annotated[str, "The target format identifier (e.g., 'flux')."],
    from_format: Annotated[
        Optional[str],
        "The source format identifier. If not provided, the system will attempt to auto-detect.",
    ] = None,
) -> TransformationResult:
    """
    Programmatically converts a batch job specification from one scheduler format to another.

    This function utilizes internal transformers to parse directives (like #SBATCH or #FLUX)
    and map them to a normalized internal representation before converting them to
    the target format.

    Args:
        batch_job: The raw string content of the jobspec or script to be converted.
        to_format: The format identifier for the target manager.
        from_format: Optional source format identifier. If None, detection logic
            is triggered based on the content of the batch_job.

    Returns:
        A dictionary containing:
            - 'status' (str): Either 'SUCCESS' or 'FAILURE'.
            - 'error' (str or None): A descriptive error message if status is FAILURE.
            - 'jobspec' (str or None): The resulting converted script or JSON string.
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
